"""Workflow 4: image-analysis worker."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.storage import storage
from app.enums import PurchaseStatus
from app.integrations.openai_client import openai_client
from app.models import Job, Purchase


async def handle_image_analysis(db, job: Job, ctx: dict | None = None) -> dict:
    result = await db.execute(
        select(Purchase).options(selectinload(Purchase.images)).where(Purchase.id == job.purchase_id)
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
    characteristics = extraction.get("characteristics")
    if isinstance(characteristics, list):
        characteristics = "\n".join(str(c) for c in characteristics)

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

    purchase.status = PurchaseStatus.ANALYZED
    await db.flush()
    return {"extracted": mapping}
