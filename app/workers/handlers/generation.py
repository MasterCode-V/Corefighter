"""Workflows 5, 6 & 8: article generation, validation and regeneration.

Articles follow the buyersbox.co.jp format: a fixed H2 heading + red "thank
you" line, an AI-written casual body, and a fixed footer. The title is built
deterministically from the product fields; only the body comes from the AI.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.enums import (
    ArticleStatus,
    ImageType,
    JobType,
    PurchaseStatus,
    RegenerationScope,
    ValidationOutcome,
)
from app.integrations.openai_client import openai_client
from app.models import Article, ArticleVersion, Job, Purchase
from app.services import article_service, article_template
from app.services.prompt_builder import (
    build_buyersbox_system_prompt,
    build_buyersbox_user_prompt,
)
from app.services.validation import validate_article


def _main_image_url(purchase: Purchase) -> str | None:
    if not purchase.images:
        return None
    images = sorted(
        purchase.images,
        key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order),
    )
    return images[0].url


async def _generate(db, job: Job, ctx, *, regeneration: bool) -> dict:
    article = await db.get(Article, job.article_id)
    if article is None:
        raise ValueError("Article not found")
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.images), selectinload(Purchase.products))
        .where(Purchase.id == article.purchase_id)
    )
    purchase = result.scalar_one_or_none()
    if purchase is None:
        raise ValueError("Purchase not found")

    if not regeneration:
        purchase.status = PurchaseStatus.GENERATION_RUNNING
        await db.commit()

    store, persona, rules = await article_service.load_generation_context(db, purchase)
    cfg = article_template.resolve_config(store)

    scope = None
    instruction = None
    previous_body = None
    if regeneration:
        scope = RegenerationScope(job.payload.get("scope", RegenerationScope.FULL.value))
        instruction = job.payload.get("instruction")
        if article.current_version_id:
            current = await db.get(ArticleVersion, article.current_version_id)
            previous_body = current.body if current else None

    # ---- Build prompts (title is deterministic, body is AI-written) ----
    system_prompt = build_buyersbox_system_prompt(cfg, persona)
    user_prompt = build_buyersbox_user_prompt(
        cfg, purchase, rules,
        persona=persona,
        user_instructions=job.payload.get("user_instructions"),
        regeneration_instruction=instruction,
        previous_body=previous_body,
    )
    generated = await openai_client.generate_article(system_prompt, user_prompt)

    title = article_template.build_title(cfg, purchase)
    heading = article_template.build_heading(cfg)
    ai_body = generated.get("body", "")
    rendered_html = article_template.assemble_html(
        cfg, heading, ai_body, main_image_url=_main_image_url(purchase)
    )

    data = {
        "title": title,
        "introduction": cfg.get("persona_intro", ""),
        "headings": [{"heading": heading, "content": ""}],
        "body": ai_body,                 # variable part only (similarity target)
        "rendered_html": rendered_html,  # full article for WordPress / preview
        "excerpt": generated.get("excerpt", ""),
        "category_suggestion": generated.get("category_suggestion") or purchase.category,
        "tag_suggestions": generated.get("tag_suggestions", []) or [],
    }

    version = await article_service.create_version(
        db, article,
        data=data,
        generated_by_job_id=job.id,
        regeneration_scope=scope.value if scope else None,
        regeneration_instruction=instruction,
    )

    # ---- Validation (workflow 6) ----
    validation = validate_article(version, rules)
    version.validation_outcome = validation["outcome"]
    version.validation_result = validation
    outcome = ValidationOutcome(validation["outcome"])

    if outcome == ValidationOutcome.FAILED:
        article.status = ArticleStatus.NEEDS_CORRECTION
        purchase.status = PurchaseStatus.ARTICLE_READY
        await db.flush()
        return {"version_no": version.version_no, "validation": validation, "next": "needs_correction"}

    # Validation passed or warning -> start similarity check (workflow 7).
    article.status = ArticleStatus.DRAFT
    purchase.status = PurchaseStatus.ARTICLE_READY
    await db.flush()

    arq = (ctx or {}).get("redis")
    if arq is not None:
        from app.services import job_service
        await job_service.create_job(
            db, arq, job_type=JobType.SIMILARITY_CHECK,
            article_id=article.id, created_by=job.created_by,
        )

    return {
        "version_no": version.version_no,
        "title": title,
        "validation": validation,
        "next": "similarity_check",
    }


async def handle_article_generation(db, job: Job, ctx: dict | None = None) -> dict:
    return await _generate(db, job, ctx, regeneration=False)


async def handle_regeneration(db, job: Job, ctx: dict | None = None) -> dict:
    return await _generate(db, job, ctx, regeneration=True)
