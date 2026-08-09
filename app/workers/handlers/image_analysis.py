"""Workflow 4: image-analysis worker."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.storage import storage
from app.enums import ImageType, PurchaseStatus
from app.integrations.openai_client import openai_client
from app.models import Job, Purchase, PurchaseImage, PurchaseProduct

MAX_IMAGES_PER_CALL = 8


def _clean_characteristics(value) -> str | None:
    if isinstance(value, list):
        return "\n".join(str(c) for c in value)
    return value


def _quantity(value) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return 1
    return parsed if parsed > 0 else 1


async def _load(images: list[PurchaseImage]) -> tuple[list[bytes], list[str]]:
    payloads: list[bytes] = []
    content_types: list[str] = []
    for img in images[:MAX_IMAGES_PER_CALL]:
        payloads.append(await storage.download_bytes(img.storage_key))
        content_types.append(img.content_type or "image/jpeg")
    return payloads, content_types


def _apply_to_product(product: PurchaseProduct, extraction: dict) -> None:
    """Fill blank product fields from an extraction payload (never overwrite staff input)."""
    values = {
        "manufacturer": extraction.get("manufacturer"),
        "product_name": extraction.get("product_name"),
        "model_number": extraction.get("model_number"),
        "category": extraction.get("category"),
        "condition": extraction.get("condition"),
        "characteristics": _clean_characteristics(extraction.get("characteristics")),
    }
    for field, value in values.items():
        if value and not getattr(product, field):
            setattr(product, field, value)
    if extraction.get("quantity") and product.quantity in (0, 1):
        product.quantity = _quantity(extraction.get("quantity"))
    if extraction.get("quantity_unit") and product.quantity_unit in ("", "点"):
        product.quantity_unit = extraction["quantity_unit"]


async def _analyze_per_product(db, purchase: Purchase) -> dict:
    """Each product block owns its detail images, so extract them one by one."""
    groups: dict[int, list[PurchaseImage]] = {}
    for img in purchase.images:
        if img.image_type == ImageType.DETAIL and img.product_index is not None:
            groups.setdefault(img.product_index, []).append(img)

    by_index = {p.sort_order: p for p in purchase.products}
    analysed = 0
    for index in sorted(groups):
        images = sorted(groups[index], key=lambda i: i.sort_order)
        payloads, content_types = await _load(images)
        if not payloads:
            continue
        extraction = await openai_client.analyze_images(
            payloads, content_types, hint=purchase.manual_notes
        )
        product = by_index.get(index)
        if product is None:
            product = PurchaseProduct(sort_order=index, quantity=1, quantity_unit="点")
            purchase.products.append(product)
            by_index[index] = product
        _apply_to_product(product, extraction)
        analysed += 1

    # The purchase-level columns mirror the first product so downstream
    # templates and the WordPress payload keep working unchanged.
    first = by_index.get(min(by_index)) if by_index else None
    if first:
        for field in ("manufacturer", "product_name", "model_number", "category", "condition"):
            if not getattr(purchase, field) and getattr(first, field):
                setattr(purchase, field, getattr(first, field))
    return {"mode": "per_product", "products_analyzed": analysed}


async def _analyze_combined(db, purchase: Purchase) -> dict:
    images_sorted = sorted(
        purchase.images, key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order)
    )
    payloads, content_types = await _load(images_sorted)
    extraction = await openai_client.analyze_images(
        payloads, content_types, hint=purchase.manual_notes
    )

    purchase.ai_extraction = extraction
    mapping = {
        "manufacturer": extraction.get("manufacturer"),
        "product_name": extraction.get("product_name"),
        "model_number": extraction.get("model_number"),
        "category": extraction.get("category"),
        "condition": extraction.get("condition"),
        "characteristics": _clean_characteristics(extraction.get("characteristics")),
    }
    for field, value in mapping.items():
        if value and not getattr(purchase, field):
            setattr(purchase, field, value)

    # When the model detects several distinct products, create product rows so
    # the article title/body can cover all of them. Only do this when the staff
    # has not already entered their own product list (don't overwrite manual work).
    detected = extraction.get("products")
    created = 0
    if isinstance(detected, list) and len(detected) >= 2 and not purchase.products:
        for idx, item in enumerate(detected):
            if not isinstance(item, dict):
                continue
            purchase.products.append(
                PurchaseProduct(
                    sort_order=idx,
                    manufacturer=item.get("manufacturer"),
                    product_name=item.get("product_name"),
                    model_number=item.get("model_number"),
                    category=item.get("category"),
                    condition=item.get("condition"),
                    characteristics=_clean_characteristics(item.get("characteristics")),
                    quantity=_quantity(item.get("quantity")),
                    quantity_unit=item.get("quantity_unit") or "点",
                )
            )
            created += 1
    return {"mode": "combined", "extracted": mapping, "products_detected": created}


async def handle_image_analysis(db, job: Job, ctx: dict | None = None) -> dict:
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.images), selectinload(Purchase.products))
        .where(Purchase.id == job.purchase_id)
    )
    purchase = result.scalar_one_or_none()
    if purchase is None:
        raise ValueError("Purchase not found for image analysis")
    if not purchase.images:
        raise ValueError("No images to analyze")

    purchase.status = PurchaseStatus.IMAGE_ANALYSIS_RUNNING
    await db.commit()

    grouped = any(
        img.image_type == ImageType.DETAIL and img.product_index is not None
        for img in purchase.images
    )
    outcome = (
        await _analyze_per_product(db, purchase)
        if grouped
        else await _analyze_combined(db, purchase)
    )

    purchase.status = PurchaseStatus.ANALYZED
    await db.flush()
    return outcome
