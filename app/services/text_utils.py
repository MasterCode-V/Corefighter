"""Text normalization, chunking and lightweight text-similarity helpers.

Used by the similarity worker (workflow 7) to reduce the weight of
product-specific tokens before comparing articles.
"""
from __future__ import annotations

import re
from typing import Iterable, List

from rapidfuzz import fuzz

_WHITESPACE = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return _HTML_TAG.sub(" ", text or "")


def normalize(text: str, remove_terms: Iterable[str] = ()) -> str:
    """Lowercase, strip HTML/markup, collapse whitespace and remove/deweight
    product-specific tokens (product name, manufacturer, model, store name)."""
    text = strip_html(text or "").lower()
    for term in remove_terms:
        if term:
            text = text.replace(term.lower(), " ")
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks suitable for embedding."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。.!?！？\n])", text or "")
    return [p.strip() for p in parts if p.strip()]


def text_similarity(a: str, b: str) -> float:
    """Token-set ratio in the 0-1 range."""
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0


def sentence_overlap(a: str, b: str, threshold: float = 0.85) -> List[str]:
    """Return sentences from `a` that closely match a sentence in `b`."""
    sents_b = split_sentences(b)
    repeated: List[str] = []
    for sa in split_sentences(a):
        if len(sa) < 12:
            continue
        for sb in sents_b:
            if fuzz.ratio(sa, sb) / 100.0 >= threshold:
                repeated.append(sa)
                break
    return repeated


def cosine_to_percentage(distance: float) -> float:
    """pgvector cosine distance (0..2) -> similarity 0..1."""
    return max(0.0, 1.0 - distance)
