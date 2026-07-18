"""Workflows 11-15: WordPress draft, update, publish and corpus sync."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import decrypt_secret
from app.core.storage import storage
from app.enums import ArticleStatus, ImageType
from app.integrations.openai_client import openai_client
from app.integrations.wordpress_client import WordPressClient
from app.models import (
    Article,
    ArticleVersion,
    CorpusEmbedding,
    Job,
    Purchase,
    PublishedCorpus,
    Store,
    WordPressSite,
)
from app.services import text_utils


async def _resolve_site(db, article: Article) -> WordPressSite:
    site: Optional[WordPressSite] = None
    if article.wordpress_site_id:
        site = await db.get(WordPressSite, article.wordpress_site_id)
    if site is None:
        result = await db.execute(
            select(WordPressSite).where(
                WordPressSite.store_id == article.store_id,
                WordPressSite.is_active.is_(True),
            ).limit(1)
        )
        site = result.scalar_one_or_none()
    if site is None:
        raise ValueError("No active WordPress site configured for this store")
    return site


def _client(site: WordPressSite) -> WordPressClient:
    return WordPressClient(site.base_url, site.username, decrypt_secret(site.encrypted_app_password))


def _render_content(version: ArticleVersion) -> str:
    # Preferred: the fully assembled article (heading + body + fixed footer).
    if getattr(version, "rendered_html", ""):
        return version.rendered_html
    parts: list[str] = []
    if version.introduction:
        parts.append(f"<p>{version.introduction}</p>")
    for heading in version.headings or []:
        if isinstance(heading, dict):
            title = heading.get("heading", "")
            content = heading.get("content", "")
            if title:
                parts.append(f"<h2>{title}</h2>")
            if content:
                parts.append(f"<p>{content}</p>")
    if version.body:
        parts.append(version.body)
    return "\n".join(parts)


async def _upload_featured_image(
    db, article: Article, client: WordPressClient
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Returns (wp_media_id, wp_source_url, local_url) for the main image."""
    result = await db.execute(
        select(Purchase).options(selectinload(Purchase.images)).where(Purchase.id == article.purchase_id)
    )
    purchase = result.scalar_one_or_none()
    if not purchase or not purchase.images:
        return None, None, None
    images = sorted(purchase.images, key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order))
    main = images[0]
    data = await storage.download_bytes(main.storage_key)
    media = await client.upload_media(data, main.filename or "image.jpg", main.content_type)
    main.wordpress_media_id = media["id"]
    await db.flush()
    return media["id"], media.get("source_url"), main.url


async def _build_payload(db, article: Article, version: ArticleVersion, client: WordPressClient,
                         status: str) -> dict:
    media_id, wp_url, local_url = await _upload_featured_image(db, article, client)

    content = _render_content(version)
    # Replace the local MinIO image URL with the uploaded WordPress URL so the
    # published post shows an accessible image.
    if local_url and wp_url and local_url in content:
        content = content.replace(local_url, wp_url)

    payload: dict = {
        "title": version.title,
        "content": content,
        "excerpt": version.excerpt,
        "status": status,
    }
    if version.category_suggestion:
        try:
            payload["categories"] = [await client.ensure_category(version.category_suggestion)]
        except Exception:  # pragma: no cover - taxonomy is best effort
            pass
    if version.tag_suggestions:
        try:
            payload["tags"] = await client.ensure_tags(list(version.tag_suggestions))
        except Exception:  # pragma: no cover
            pass
    if media_id:
        payload["featured_media"] = media_id
    return payload


async def _load_article_version(db, job: Job) -> tuple[Article, ArticleVersion]:
    article = await db.get(Article, job.article_id)
    if article is None:
        raise ValueError("Article not found")
    if not article.current_version_id:
        raise ValueError("Article has no current version")
    version = await db.get(ArticleVersion, article.current_version_id)
    if version is None:
        raise ValueError("Current version missing")
    return article, version


# --------------------------------------------------------------------------
# Workflow 11: create draft
# --------------------------------------------------------------------------
async def handle_wordpress_draft(db, job: Job, ctx: dict | None = None) -> dict:
    article, version = await _load_article_version(db, job)
    site = await _resolve_site(db, article)
    client = _client(site)

    # Idempotency: if a post already exists, update it instead of creating a second.
    if article.wordpress_post_id and await client.get_post(article.wordpress_post_id):
        payload = await _build_payload(db, article, version, client, status="draft")
        post = await client.update_post(article.wordpress_post_id, payload)
    else:
        payload = await _build_payload(db, article, version, client, status="draft")
        post = await client.create_post(payload)
        article.wordpress_post_id = post["id"]

    article.wordpress_site_id = site.id
    article.status = ArticleStatus.WORDPRESS_DRAFT
    await db.flush()
    return {"wordpress_post_id": article.wordpress_post_id, "status": "draft"}


# --------------------------------------------------------------------------
# Workflow 12: update existing draft
# --------------------------------------------------------------------------
async def handle_wordpress_update(db, job: Job, ctx: dict | None = None) -> dict:
    article, version = await _load_article_version(db, job)
    if not article.wordpress_post_id:
        raise ValueError("No WordPress post to update")
    site = await _resolve_site(db, article)
    client = _client(site)
    payload = await _build_payload(db, article, version, client, status="draft")
    await client.update_post(article.wordpress_post_id, payload)
    await db.flush()
    return {"wordpress_post_id": article.wordpress_post_id, "updated": True}


# --------------------------------------------------------------------------
# Workflow 13: publish
# --------------------------------------------------------------------------
async def handle_wordpress_publish(db, job: Job, ctx: dict | None = None) -> dict:
    article, version = await _load_article_version(db, job)
    if not article.wordpress_post_id:
        raise ValueError("No WordPress draft to publish")
    site = await _resolve_site(db, article)
    client = _client(site)

    payload = await _build_payload(db, article, version, client, status="publish")
    post = await client.update_post(article.wordpress_post_id, payload)

    article.status = ArticleStatus.PUBLISHED
    article.published_url = post.get("link")
    article.published_at = datetime.now(timezone.utc)
    await db.flush()

    # Workflow 15 note: refresh corpus after publishing.
    await _upsert_corpus_entry(
        db, site,
        wordpress_post_id=article.wordpress_post_id,
        article_id=article.id,
        title=version.title,
        content=version.full_text,
        published_at=article.published_at,
    )
    await db.flush()
    return {"wordpress_post_id": article.wordpress_post_id, "url": article.published_url}


# --------------------------------------------------------------------------
# Workflow 15: historical synchronization
# --------------------------------------------------------------------------
async def handle_wordpress_sync(db, job: Job, ctx: dict | None = None) -> dict:
    site_id = job.payload.get("wordpress_site_id")
    if site_id:
        sites = [await db.get(WordPressSite, uuid.UUID(site_id))]
    else:
        sites = list(
            (await db.execute(select(WordPressSite).where(WordPressSite.is_active.is_(True))))
            .scalars().all()
        )

    total = 0
    for site in sites:
        if site is None:
            continue
        client = _client(site)
        page = 1
        while True:
            posts, total_pages = await client.list_posts(status="publish", page=page, per_page=50)
            for post in posts:
                title = (post.get("title") or {}).get("rendered", "")
                content = (post.get("content") or {}).get("rendered", "")
                published_at = None
                if post.get("date_gmt"):
                    published_at = date_parser.parse(post["date_gmt"]).replace(tzinfo=timezone.utc)
                await _upsert_corpus_entry(
                    db, site,
                    wordpress_post_id=post["id"],
                    article_id=None,
                    title=title,
                    content=text_utils.strip_html(content),
                    published_at=published_at,
                )
                total += 1
            await db.flush()
            if page >= total_pages:
                break
            page += 1

    return {"synced": total, "sites": len([s for s in sites if s])}


async def _upsert_corpus_entry(db, site: WordPressSite, *, wordpress_post_id: int,
                               article_id, title: str, content: str, published_at) -> None:
    result = await db.execute(
        select(PublishedCorpus).where(
            PublishedCorpus.wordpress_site_id == site.id,
            PublishedCorpus.wordpress_post_id == wordpress_post_id,
        )
    )
    corpus = result.scalar_one_or_none()
    normalized = text_utils.normalize(content)

    if corpus is None:
        corpus = PublishedCorpus(
            source="wordpress",
            wordpress_site_id=site.id,
            wordpress_post_id=wordpress_post_id,
            article_id=article_id,
            title=title,
            content=content,
            normalized_content=normalized,
            published_at=published_at,
        )
        db.add(corpus)
        await db.flush()
    else:
        # Only re-embed when the content changed.
        if corpus.content == content:
            return
        corpus.title = title
        corpus.content = content
        corpus.normalized_content = normalized
        corpus.published_at = published_at
        await db.execute(
            CorpusEmbedding.__table__.delete().where(CorpusEmbedding.corpus_id == corpus.id)
        )
        await db.flush()

    chunks = text_utils.chunk_text(normalized)
    if not chunks:
        return
    vectors = await openai_client.embed(chunks)
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        db.add(CorpusEmbedding(corpus_id=corpus.id, chunk_index=idx, content=chunk, embedding=vec))
    await db.flush()
