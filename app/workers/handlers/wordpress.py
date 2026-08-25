"""Workflows 11-15: WordPress draft, update, publish and corpus sync."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
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
from app.services.wordpress_categories import (
    EXPERIENCE_CATEGORY_ID,
    category_id_for_name,
    resolve_category_ids,
)

logger = get_logger("wordpress")


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
        raise ValueError("この店舗に有効なWordPress接続がありません")
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


async def _upload_featured_image(db, article: Article, client: WordPressClient) -> dict:
    """Upload the main purchase image and describe it for inline markup.

    Returns ``{id, url, width, height, local_url}`` where ``url`` prefers the
    ``medium`` size, matching manual EXPERIENCE posts.

    Featured image is required for the live EXPERIENCE / store grid. Missing
    MinIO media or WP upload failure must fail the job so we never publish a
    post that cannot appear in the malls list.
    """
    result = await db.execute(
        select(Purchase).options(selectinload(Purchase.images)).where(Purchase.id == article.purchase_id)
    )
    purchase = result.scalar_one_or_none()
    if not purchase or not purchase.images:
        raise ValueError(
            "買取画像がありません。EXPERIENCE掲載にはアイキャッチ画像が必須です"
        )
    images = sorted(purchase.images, key=lambda i: (i.image_type != ImageType.ARTICLE, i.sort_order))
    main = images[0]
    try:
        data = await storage.download_bytes(main.storage_key)
        media = await client.upload_media(data, main.filename or "image.jpg", main.content_type)
    except Exception as exc:
        raise ValueError(
            f"アイキャッチ画像のアップロードに失敗しました（{main.storage_key}）: {exc}。"
            "MinIO上の画像とWordPress接続を確認してください。"
        ) from exc
    main.wordpress_media_id = media["id"]
    await db.flush()
    source_url = media.get("source_url") or ""
    if not source_url:
        raise ValueError("WordPressへの画像アップロードに失敗しました（URLが返りませんでした）")

    sizes = (media.get("media_details") or {}).get("sizes") or {}
    medium = sizes.get("medium") or {}
    return {
        "id": media["id"],
        "url": medium.get("source_url") or source_url,
        "width": medium.get("width"),
        "height": medium.get("height"),
        "size_class": "size-medium" if medium.get("source_url") else "size-full",
        "local_url": main.url,
    }


def _inject_wp_featured_image(content: str, media: dict) -> str:
    """Rewrite the inline main image to match live EXPERIENCE markup.

    Manual posts use
    ``<img src="…-512x640.jpg" alt="" width="512" height="640"
    class="wp-image-N size-medium aligncenter" />`` — never a MinIO URL or a
    ``<figure>`` wrapper. Prefer replacing our ``cf-main-image`` marker.
    """
    wp_url = media.get("url")
    media_id = media.get("id")
    local_url = media.get("local_url")
    if not wp_url or not media_id:
        return content

    alt_match = re.search(
        r'<img\b[^>]*class="[^"]*cf-main-image[^"]*"[^>]*\balt="([^"]*)"', content, re.IGNORECASE
    )
    alt = alt_match.group(1) if alt_match else ""
    dimensions = ""
    if media.get("width") and media.get("height"):
        dimensions = f' width="{media["width"]}" height="{media["height"]}"'

    wp_img = (
        f'<img src="{wp_url}" alt="{alt}"{dimensions} '
        f'class="wp-image-{media_id} {media.get("size_class", "size-full")} aligncenter" />'
    )
    replaced, n = re.subn(
        r'<img\b[^>]*class="[^"]*cf-main-image[^"]*"[^>]*/?>',
        wp_img,
        content,
        count=1,
        flags=re.IGNORECASE,
    )
    if n:
        return replaced

    replaced, n = re.subn(
        r'<figure\b[^>]*class="[^"]*cf-main-image[^"]*"[^>]*>.*?</figure>',
        wp_img,
        content,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if n:
        return replaced

    if local_url and local_url in content:
        return content.replace(local_url, wp_url)

    # Relative media proxy paths (e.g. /api/v1/media/purchases/…)
    replaced, n = re.subn(
        r'<img\b[^>]*src="/api/v1/media/[^"]+"[^>]*/?>',
        wp_img,
        content,
        count=1,
        flags=re.IGNORECASE,
    )
    return replaced if n else content


async def _build_payload(db, article: Article, version: ArticleVersion, client: WordPressClient,
                         status: str) -> dict:
    from app.services import article_template

    media = await _upload_featured_image(db, article, client)
    media_id = media["id"]

    content = _inject_wp_featured_image(_render_content(version), media)
    content = article_template.inject_related_into_html(
        content, getattr(article, "related_posts", None) or []
    )

    # Categories: always EXPERIENCE + any selected/suggested product categories
    # (multiple allowed, e.g. EXPERIENCE + 建材 + ペアコイル).
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.products), selectinload(Purchase.images))
        .where(Purchase.id == article.purchase_id)
    )
    purchase = result.scalar_one_or_none()
    store = await db.get(Store, article.store_id) if article.store_id else None
    cfg = article_template.resolve_config(store)
    # Theme owns VVF/SNS/stores — strip any CF-baked copies from post_content.
    content = article_template.ensure_experience_tail(content, cfg)
    purchase_category = getattr(purchase, "category", None) if purchase else None

    excerpt = article_template.build_excerpt(
        cfg, purchase, ai_excerpt=version.excerpt
    ) if purchase else (version.excerpt or "")

    payload: dict = {
        "title": version.title,
        "content": content,
        "excerpt": excerpt,
        "status": status,
        "featured_media": media_id,
    }

    cat_ids = resolve_category_ids(
        purchase_category,
        version.category_suggestion,
        include_experience=True,
    )
    if not cat_ids:
        cat_ids = [EXPERIENCE_CATEGORY_ID]
    # Never create new categories from AI suggestions: a brand-new term becomes
    # the permalink base (e.g. /conditioner/123) and drops the post out of the
    # /experience listing. Unknown names are logged and ignored.
    from app.services.wordpress_categories import split_category_names

    unknown = [
        name
        for name in split_category_names(version.category_suggestion, purchase_category)
        if category_id_for_name(name) is None
    ]
    if unknown:
        logger.info(
            "Ignoring unknown WordPress categories for article %s: %s", article.id, unknown
        )
    payload["categories"] = cat_ids

    # Always attach store tag (+ makers) so the post appears under the store
    # section on /experience (東苗穂店 / 豊平店 / 東米里店). No location tags.
    tag_names: list[str] = []
    if purchase is not None:
        tag_names.extend(article_template.build_default_tags(cfg, purchase))
    tag_names = article_template.filter_content_tags(
        [*tag_names, *(version.tag_suggestions or [])],
        cfg,
    )
    if tag_names:
        try:
            payload["tags"] = await client.ensure_tags(tag_names)
        except Exception:  # pragma: no cover
            logger.warning("Tag ensure failed for article %s", article.id, exc_info=True)
    return payload


async def _load_article_version(db, job: Job) -> tuple[Article, ArticleVersion]:
    article = await db.get(Article, job.article_id)
    if article is None:
        raise ValueError("記事が見つかりません")
    if not article.current_version_id:
        raise ValueError("記事に現行バージョンがありません")
    version = await db.get(ArticleVersion, article.current_version_id)
    if version is None:
        raise ValueError("記事バージョンが見つかりません")
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
    article.status = ArticleStatus.DRAFT
    await db.flush()
    return {"wordpress_post_id": article.wordpress_post_id, "status": "draft"}


# --------------------------------------------------------------------------
# Workflow 12: update existing draft
# --------------------------------------------------------------------------
async def handle_wordpress_update(db, job: Job, ctx: dict | None = None) -> dict:
    article, version = await _load_article_version(db, job)
    if not article.wordpress_post_id:
        raise ValueError("更新対象のWordPress投稿がありません")
    site = await _resolve_site(db, article)
    client = _client(site)
    # Editing a live article must not silently unpublish it.
    wp_status = "publish" if article.status == ArticleStatus.PUBLISHED else "draft"
    payload = await _build_payload(db, article, version, client, status=wp_status)
    await client.update_post(article.wordpress_post_id, payload)
    await db.flush()
    return {"wordpress_post_id": article.wordpress_post_id, "updated": True}


# --------------------------------------------------------------------------
# Workflow 13: publish
# --------------------------------------------------------------------------
async def handle_wordpress_publish(db, job: Job, ctx: dict | None = None) -> dict:
    article, version = await _load_article_version(db, job)
    site = await _resolve_site(db, article)
    client = _client(site)

    payload = await _build_payload(db, article, version, client, status="publish")
    # Publishing straight from the wizard is allowed, so the post may not exist yet.
    if article.wordpress_post_id and await client.get_post(article.wordpress_post_id):
        post = await client.update_post(article.wordpress_post_id, payload)
    else:
        post = await client.create_post(payload)
        article.wordpress_post_id = post["id"]

    article.wordpress_site_id = site.id
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
