"""Workflow 4: image-analysis worker."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.storage import storage
from app.enums import PurchaseStatus
from app.integrations.openai_client import openai_client
from app.models import Job, Purchase, PurchaseProduct


def _clean_characteristics(value) -> str | None:
    if isinstance(value, list):
        return "\n".join(str(c) for c in value)
    return value


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

    # Load image bytes from object storage (prioritise article/eye-catch image).
    images_sorted = sorted(purchase.images, key=lambda i: (i.image_type.value != "ARTICLE", i.sort_order))
    payloads: list[bytes] = []
    content_types: list[str] = []
    for img in images_sorted[:8]:  # cap number of images sent to the model
        payloads.append(await storage.download_bytes(img.storage_key))
        content_types.append(img.content_type or "image/jpeg")

    extraction = await openai_client.analyze_images(
        payloads, content_types, hint=purchase.manual_notes
    )

    # Persist raw extraction and only fill fields the user has not already set.
    purchase.ai_extraction = extraction
    characteristics = _clean_characteristics(extraction.get("characteristics"))

    mapping = {
        "manufacturer": extraction.get("manufacturer"),
        "product_name": extraction.get("product_name"),
        "model_number": extraction.get("model_number"),
        "category": extraction.get("category"),
        "condition": extraction.get("condition"),
        "characteristics": characteristics,
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
                    quantity=int(item["quantity"]) if str(item.get("quantity") or "").isdigit() else 1,
                    quantity_unit=item.get("quantity_unit") or "点",
                )
            )
            created += 1

    purchase.status = PurchaseStatus.ANALYZED
    await db.flush()
    return {"extracted": mapping, "products_detected": created}
