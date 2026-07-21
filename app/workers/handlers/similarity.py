"""Workflow 7: similarity-check worker.

Compares the generated article against the corpus of published articles.
Semantic similarity uses pgvector cosine distance over OpenAI embeddings;
text similarity uses token-set ratio and sentence overlap. Product-specific
tokens are removed/deweighted before comparison. Threshold < 50% must pass.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.enums import ArticleStatus
from app.integrations.openai_client import openai_client
from app.models import (
    Article,
    ArticleVersion,
    CorpusEmbedding,
    Job,
    Purchase,
    PublishedCorpus,
    SimilarityResult,
    Store,
)
from app.services import text_utils

SEMANTIC_WEIGHT = 0.7
TEXT_WEIGHT = 0.3
TOP_K = 5


async def handle_similarity_check(db, job: Job, ctx: dict | None = None) -> dict:
    article = await db.get(Article, job.article_id)
    if article is None:
        raise ValueError("Article not found")
    version = await db.get(ArticleVersion, article.current_version_id) if article.current_version_id else None
    if version is None:
        raise ValueError("Article has no current version")

    purchase = await db.get(Purchase, article.purchase_id)
    store = await db.get(Store, article.store_id)

    remove_terms = [
        t for t in [
            purchase.product_name if purchase else None,
            purchase.manufacturer if purchase else None,
            purchase.model_number if purchase else None,
            store.name if store else None,
        ] if t
    ]

    normalized = text_utils.normalize(version.full_text, remove_terms)

    # ---- Semantic similarity via pgvector ----
    semantic_score = 0.0
    most_similar: list[dict] = []
    query_vectors = await openai_client.embed([normalized[:6000]])
    if query_vectors:
        query_vec = query_vectors[0]
        distance = CorpusEmbedding.embedding.cosine_distance(query_vec).label("distance")
        stmt = (
            select(
                CorpusEmbedding.corpus_id,
                PublishedCorpus.title,
                PublishedCorpus.wordpress_post_id,
                distance,
            )
            .join(PublishedCorpus, PublishedCorpus.id == CorpusEmbedding.corpus_id)
            .order_by(distance)
            .limit(TOP_K)
        )
        if article.id:
            stmt = stmt.where(
                (PublishedCorpus.article_id.is_(None)) | (PublishedCorpus.article_id != article.id)
            )
        rows = (await db.execute(stmt)).all()
        for corpus_id, title, wp_post_id, dist in rows:
            score = text_utils.cosine_to_percentage(float(dist))
            most_similar.append(
                {
                    "corpus_id": str(corpus_id),
                    "wordpress_post_id": wp_post_id,
                    "title": title,
                    "score": round(score, 4),
                }
            )
        if most_similar:
            semantic_score = max(m["score"] for m in most_similar)

    # ---- Text similarity + repeated sections against the closest corpus entries ----
    text_score = 0.0
    repeated_sections: list[dict] = []
    top_corpus_ids = [m["corpus_id"] for m in most_similar[:3]]
    if top_corpus_ids:
        corpus_rows = (
            await db.execute(
                select(PublishedCorpus).where(PublishedCorpus.id.in_(top_corpus_ids))
            )
        ).scalars().all()
        for corpus in corpus_rows:
            other_norm = corpus.normalized_content or text_utils.normalize(corpus.content, remove_terms)
            ts = text_utils.text_similarity(normalized, other_norm)
            text_score = max(text_score, ts)
            overlaps = text_utils.sentence_overlap(version.full_text, corpus.content)
            if overlaps:
                repeated_sections.append(
                    {"corpus_id": str(corpus.id), "title": corpus.title, "sentences": overlaps[:5]}
                )

    final_score = round(SEMANTIC_WEIGHT * semantic_score + TEXT_WEIGHT * text_score, 4)
    passed = final_score < settings.SIMILARITY_THRESHOLD

    result = SimilarityResult(
        article_id=article.id,
        article_version_id=version.id,
        similarity_score=final_score,
        semantic_score=round(semantic_score, 4),
        text_score=round(text_score, 4),
        passed=passed,
        most_similar=most_similar,
        repeated_sections=repeated_sections,
    )
    db.add(result)

    version.similarity_score = final_score
    article.latest_similarity_score = final_score

    if passed:
        # Workflow 9: enter publication waiting list.
        article.status = ArticleStatus.WAITING_LIST
    else:
        # Workflow 7: similarity 50%+ -> warning.
        article.status = ArticleStatus.SIMILARITY_WARNING

    await db.flush()
    return {
        "similarity_score": final_score,
        "semantic_score": round(semantic_score, 4),
        "text_score": round(text_score, 4),
        "passed": passed,
        "most_similar": most_similar,
    }
