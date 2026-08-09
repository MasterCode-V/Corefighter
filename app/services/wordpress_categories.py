"""Buyersbox WordPress category catalog (live site taxonomy).

IDs were fetched from https://www.buyersbox.co.jp REST API.
Buyback / EXPERIENCE posts should include EXPERIENCE (id=2) plus one or more
product categories (e.g. EXPERIENCE + 建材 + ペアコイル).
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

# Primary blog category for 買取実績 / EXPERIENCE posts.
EXPERIENCE_CATEGORY_ID = 2
EXPERIENCE_CATEGORY_NAME = "EXPERIENCE"

# name -> WordPress term_id (counts omitted; names match wp-admin)
WORDPRESS_CATEGORIES: list[dict] = [
    {"id": 2, "name": "EXPERIENCE"},
    {"id": 10, "name": "NEWS"},
    {"id": 12, "name": "電線"},
    {"id": 11, "name": "VVFケーブル"},
    {"id": 6, "name": "工具"},
    {"id": 176, "name": "建材"},
    {"id": 214, "name": "中古電動工具"},
    {"id": 19, "name": "設備資材"},
    {"id": 98, "name": "新品電動工具"},
    {"id": 215, "name": "その他建築資材"},
    {"id": 103, "name": "ペアコイル"},
    {"id": 211, "name": "内装資材"},
    {"id": 1, "name": "その他"},
    {"id": 20, "name": "電設資材"},
    {"id": 223, "name": "その他ツール"},
    {"id": 50, "name": "LANケーブル"},
    {"id": 201, "name": "電化製品"},
    {"id": 117, "name": "半端電線"},
    {"id": 69, "name": "IVケーブル"},
    {"id": 106, "name": "CVケーブル"},
    {"id": 45, "name": "マイナーケーブル"},
    {"id": 82, "name": "VCTFケーブル"},
    {"id": 47, "name": "同軸ケーブル"},
    {"id": 107, "name": "CVTケーブル"},
    {"id": 212, "name": "発電機・溶接機"},
    {"id": 46, "name": "エコケーブル"},
]

# Product categories shown in the UI (EXPERIENCE/NEWS are structural).
PRODUCT_CATEGORY_NAMES: list[str] = [
    c["name"]
    for c in WORDPRESS_CATEGORIES
    if c["name"] not in {"EXPERIENCE", "NEWS"}
]

_BY_NAME = {c["name"]: c["id"] for c in WORDPRESS_CATEGORIES}
_SPLIT_RE = re.compile(r"[,、/|；;]+")


def split_category_names(*values: Optional[str]) -> list[str]:
    """Split one or more category fields that may contain multiple names."""
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        for part in _SPLIT_RE.split(str(value)):
            key = part.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(key)
    return names


def category_id_for_name(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    key = name.strip()
    if key in _BY_NAME:
        return _BY_NAME[key]
    lower = key.lower()
    for n, i in _BY_NAME.items():
        if n.lower() == lower:
            return i
    return None


def resolve_category_ids(
    *names: Optional[str],
    include_experience: bool = True,
) -> list[int]:
    """Build a de-duplicated list of WP category IDs for a post.

    Each ``names`` entry may itself be a multi-value string
    (``"建材、ペアコイル"`` or ``"工具, 中古電動工具"``).
    """
    ids: list[int] = []
    if include_experience:
        ids.append(EXPERIENCE_CATEGORY_ID)
    for name in split_category_names(*names):
        cid = category_id_for_name(name)
        if cid is None or cid in ids:
            continue
        # WordPress builds %category% permalinks from the lowest term id, so a
        # category below EXPERIENCE (e.g. その他 = 1) would move the post off
        # /experience/ and out of the live listing.
        if include_experience and cid < EXPERIENCE_CATEGORY_ID:
            continue
        ids.append(cid)
    return ids


def join_category_names(names: Iterable[str]) -> str:
    return "、".join(n.strip() for n in names if n and n.strip())


def allowed_category_prompt_list() -> str:
    return " / ".join(PRODUCT_CATEGORY_NAMES)
