from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DBSession, ensure_store_access, get_arq
from app.core.storage import storage
from app.enums import ArticleStatus, ImageType, JobType, PurchaseStatus, UserRole
from app.models import Article, Persona, Purchase, PurchaseImage, PurchaseProduct
from app.schemas.job import JobCreatedResponse
from app.schemas.purchase import PurchaseCreate, PurchaseImageRead, PurchaseRead, PurchaseUpdate
from app.services import job_service

router = APIRouter()

ArqDep = Annotated[ArqRedis, Depends(get_arq)]
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_CONTENT = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _apply_products(purchase: Purchase, products: Optional[List[dict]]) -> None:
    """Attach product rows and mirror the first one onto the legacy columns so
    older code paths (and single-product titles) keep working."""
    if not products:
        return
    for idx, item in enumerate(products):
        item = dict(item)
        item["sort_order"] = idx
        purchase.products.append(PurchaseProduct(**item))
    first = products[0]
    for field in (
        "manufacturer", "product_name", "model_number",
        "category", "condition", "characteristics",
    ):
        if first.get(field) and not getattr(purchase, field, None):
            setattr(purchase, field, first[field])
    if first.get("quantity"):
        purchase.quantity = first["quantity"]
    if first.get("quantity_unit"):
        purchase.quantity_unit = first["quantity_unit"]


async def _get_purchase(db, purchase_id: uuid.UUID) -> Purchase:
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.images), selectinload(Purchase.products))
        .where(Purchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.post("", response_model=PurchaseRead, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    db: DBSession, current_user: CurrentUser, body: PurchaseCreate
) -> Purchase:
    """Workflow 3: store staff creates a purchase record (status UNSTARTED)."""
    ensure_store_access(current_user, body.store_id)
    if body.persona_id:
        persona = await db.get(Persona, body.persona_id)
        if not persona:
            raise HTTPException(status_code=400, detail="Persona not found")
    data = body.model_dump()
    products = data.pop("products", None)
    purchase = Purchase(created_by=current_user.id, **data)
    _apply_products(purchase, products)
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase, attribute_names=["images", "products"])
    return purchase


@router.get("", response_model=list[PurchaseRead])
async def list_purchases(
    db: DBSession,
    current_user: CurrentUser,
    store_id: Optional[uuid.UUID] = None,
    status_filter: Optional[PurchaseStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Purchase]:
    stmt = select(Purchase).options(
        selectinload(Purchase.images), selectinload(Purchase.products)
    )
    if current_user.role != UserRole.ADMIN and current_user.store_id:
        stmt = stmt.where(Purchase.store_id == current_user.store_id)
    elif store_id:
        stmt = stmt.where(Purchase.store_id == store_id)
    if status_filter:
        stmt = stmt.where(Purchase.status == status_filter)
    stmt = stmt.order_by(Purchase.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{purchase_id}", response_model=PurchaseRead)
async def get_purchase(db: DBSession, current_user: CurrentUser, purchase_id: uuid.UUID) -> Purchase:
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)
    return purchase


@router.patch("/{purchase_id}", response_model=PurchaseRead)
async def update_purchase(
    db: DBSession, current_user: CurrentUser, purchase_id: uuid.UUID, body: PurchaseUpdate
) -> Purchase:
    """Workflow 4 review step: correct AI-extracted product information."""
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)
    updates = body.model_dump(exclude_unset=True)
    products = updates.pop("products", None)
    for key, value in updates.items():
        setattr(purchase, key, value)
    if products is not None:
        purchase.products.clear()
        _apply_products(purchase, products)
    await db.commit()
    await db.refresh(purchase, attribute_names=["images", "products"])
    return purchase


@router.post("/{purchase_id}/images", response_model=PurchaseImageRead,
             status_code=status.HTTP_201_CREATED)
async def upload_image(
    db: DBSession,
    current_user: CurrentUser,
    purchase_id: uuid.UUID,
    file: UploadFile = File(...),
    image_type: ImageType = Form(ImageType.DETAIL),
    sort_order: int = Form(0),
) -> PurchaseImage:
    """Workflow 3: upload article (eye-catch) and detail images."""
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)

    if file.content_type not in ALLOWED_CONTENT:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15MB)")

    key = storage.build_key(f"purchases/{purchase_id}", file.filename or "image.jpg")
    url = await storage.upload_bytes(key, data, file.content_type)

    image = PurchaseImage(
        purchase_id=purchase_id,
        image_type=image_type,
        storage_key=key,
        url=url,
        filename=file.filename or "",
        content_type=file.content_type or "",
        size=len(data),
        sort_order=sort_order,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


@router.delete("/{purchase_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_model=None)
async def delete_image(
    db: DBSession, current_user: CurrentUser, purchase_id: uuid.UUID, image_id: uuid.UUID
):
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)
    image = await db.get(PurchaseImage, image_id)
    if image and image.purchase_id == purchase_id:
        try:
            await storage.delete(image.storage_key)
        except Exception:  # pragma: no cover - best effort
            pass
        await db.delete(image)
        await db.commit()


@router.post("/{purchase_id}/analyze", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def analyze_images(
    db: DBSession, current_user: CurrentUser, arq: ArqDep, purchase_id: uuid.UUID
) -> JobCreatedResponse:
    """Workflow 4: enqueue an IMAGE_ANALYSIS job."""
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)
    if not purchase.images:
        raise HTTPException(status_code=400, detail="No images uploaded for this purchase")

    job = await job_service.create_job(
        db, arq, job_type=JobType.IMAGE_ANALYSIS,
        purchase_id=purchase.id, created_by=current_user.id,
    )
    purchase.status = PurchaseStatus.IMAGE_ANALYSIS_QUEUED
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)


@router.post("/{purchase_id}/generate", response_model=JobCreatedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def generate_article(
    db: DBSession,
    current_user: CurrentUser,
    arq: ArqDep,
    purchase_id: uuid.UUID,
    user_instructions: Optional[str] = None,
) -> JobCreatedResponse:
    """Workflow 5: validate required info and enqueue ARTICLE_GENERATION."""
    purchase = await _get_purchase(db, purchase_id)
    ensure_store_access(current_user, purchase.store_id)

    if not purchase.product_name:
        raise HTTPException(
            status_code=400,
            detail="Product name is required before generating an article",
        )

    # Ensure a single Article per purchase exists.
    result = await db.execute(select(Article).where(Article.purchase_id == purchase.id))
    article = result.scalar_one_or_none()
    if article is None:
        article = Article(
            purchase_id=purchase.id, store_id=purchase.store_id, status=ArticleStatus.DRAFT
        )
        db.add(article)
        await db.flush()

    if user_instructions:
        purchase.user_instructions = user_instructions

    job = await job_service.create_job(
        db, arq, job_type=JobType.ARTICLE_GENERATION,
        purchase_id=purchase.id, article_id=article.id, created_by=current_user.id,
        payload={"user_instructions": user_instructions},
    )
    purchase.status = PurchaseStatus.GENERATION_QUEUED
    await db.commit()
    return JobCreatedResponse(job_id=job.id, job_type=job.job_type, status=job.status)
