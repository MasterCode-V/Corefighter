"""Buyback article template (buyersbox.co.jp style).

An article is composed of three parts:

    1. Fixed header   -> centered H2 + centered red thanks + optional product line
                         + centered main image (WordPress aligncenter)
    2. Variable body  -> the AI-written casual blog about the specific item
    3. Fixed footer   -> phone / LINE / VVF / store-info boilerplate (identical
                         on every article; NOT used for similarity)

The variable body is stored on ``ArticleVersion.body`` (so similarity only
compares the unique part). The fully assembled HTML is stored on
``ArticleVersion.rendered_html`` and is what gets pushed to WordPress.

Global defaults live here; each store may override any key via
``Store.article_config`` (a JSONB column).

Markup mirrors clean manual EXPERIENCE posts (e.g. post #16118 / #16705 header).
"""
from __future__ import annotations

from typing import Optional

from app.models import Purchase, Store

# ---------------------------------------------------------------------------
# Global defaults (can be overridden per store via Store.article_config)
# ---------------------------------------------------------------------------
DEFAULT_TEMPLATE: dict = {
    "label": "",                       # e.g. 豊平 / 東苗穂 / 東米里
    "area": "",                        # e.g. 札幌市豊平区
    "title_prefix": "パワトレ",
    "title_suffix": "店から最新の買取情報",
    "heading_prefix": "パワフルトレードセンター",
    "heading_suffix": "店から買取情報",
    "thanks_text": "お売りいただきありがとうございました",
    "thanks_color": "#ff0000",
    "persona_intro": "こんにちは～🙋‍♀️パワトレギャルです💕",
    "many_threshold": 10,              # qty >= this => omit model number in title
    "phone_general": "011-827-1149",
    "phone_dispatch": "050-3479-0800",
    "line_url": "https://lin.ee/WnXr1bu",
    # Footer HTML matches live EXPERIENCE dial block (green labels + LINE link),
    # then the shared VVF / SNS / store boilerplate. {phone_*} / {line_url} filled in.
    "footer_html": (
        '<p style="text-align: left;">'
        '<span style="color: #008000;"><strong>出張買取専用ダイヤル</strong></span>'
        'はこちら： <b>{phone_dispatch}</b><br />\n'
        '<span style="color: #008000;"><strong>パワフルトレードセンター総合ダイヤル</strong></span><br />\n'
        '最短1分カンタン査定はこちら： <b>{phone_general}</b><br />\n'
        'LINE査定もご利用ください。<br />\n'
        'LINE査定は<a href="{line_url}">こちら</a>から</p>\n'
        '<h3>年間買取10000件　パワトレ買取実績</h3>\n'
        '<h5>【札幌市内No.1】最新のVVF電線買取価格</h5>\n'
        '<h5>【札幌市内No.1】最新のペアコイル買取価格</h5>\n'
        '<h5>SNS情報発信&amp;査定依頼受付中</h5>\n'
        '<p>無料査定はLINE、インスタのDM、電話から受け付けております😎<br />\n'
        '☎︎：{phone_general}</p>\n'
        '<h4>パワフルトレードセンター 東苗穂店</h4>\n'
        '<p>〒007-0803 北海道札幌市東区東苗穂3条1丁目3-45 コスモロイヤル東苗穂A棟 1F 定休日：日曜・祝日</p>\n'
        '<h4>パワフルトレードセンター 豊平店</h4>\n'
        '<p>〒062-0903 北海道札幌市豊平区豊平3条9丁目3-10 エムズ豊平１F 定休日：日曜・祝日</p>\n'
        '<h4>パワフルトレードセンター 東米里店</h4>\n'
        '<p>〒003-0876 北海道札幌市白石区東米里2090-170 定休日：日曜・祝日</p>'
    ),
}


def resolve_config(store: Optional[Store]) -> dict:
    """Merge the store's overrides over the global defaults."""
    cfg = dict(DEFAULT_TEMPLATE)
    if store is not None:
        if store.article_config:
            cfg.update({k: v for k, v in store.article_config.items() if v not in (None, "")})
        if not cfg.get("label"):
            cfg["label"] = store.name or ""
    return cfg


def effective_products(purchase: Purchase) -> list[dict]:
    """Return the purchase's products as plain dicts.

    When the purchase has explicit product rows they are used (ordered by
    sort_order); otherwise the legacy purchase-level columns are returned as a
    single implicit product. This keeps single-item purchases working exactly
    as before while supporting multiple products.
    """
    rows = list(getattr(purchase, "products", None) or [])
    if rows:
        rows.sort(key=lambda p: p.sort_order)
        return [
            {
                "manufacturer": (p.manufacturer or "").strip(),
                "product_name": (p.product_name or "").strip(),
                "model_number": (p.model_number or "").strip(),
                "category": (p.category or "").strip(),
                "condition": (p.condition or "").strip(),
                "characteristics": (p.characteristics or "").strip(),
                "quantity": p.quantity or 1,
                "quantity_unit": (p.quantity_unit or "点").strip(),
            }
            for p in rows
        ]
    return [
        {
            "manufacturer": (purchase.manufacturer or "").strip(),
            "product_name": (purchase.product_name or "").strip(),
            "model_number": (purchase.model_number or "").strip(),
            "category": (purchase.category or "").strip(),
            "condition": (purchase.condition or "").strip(),
            "characteristics": (purchase.characteristics or "").strip(),
            "quantity": purchase.quantity or 1,
            "quantity_unit": (purchase.quantity_unit or "点").strip(),
        }
    ]


def _product_title_segment(pr: dict, many_threshold: int) -> str:
    maker = pr["manufacturer"]
    product = pr["product_name"]
    model = pr["model_number"]
    qty = pr["quantity"] or 1
    unit = pr["quantity_unit"] or "点"
    many = qty >= many_threshold
    seg = [p for p in (maker, product) if p]
    if model and not many:
        seg.append(model)
    if qty and qty > 1:
        seg.append(f"{qty}{unit}")
    return " ".join(seg)


def build_title(cfg: dict, purchase: Purchase) -> str:
    """Title format (matches live WP titles with an HTML line break):

    パワトレ{label}店から最新の買取情報 <br>【{商品1} / {商品2} …】
    """
    label = cfg.get("label", "")
    many_threshold = int(cfg.get("many_threshold", 10))
    segments = [
        seg
        for pr in effective_products(purchase)
        if (seg := _product_title_segment(pr, many_threshold))
    ]
    inner_str = " / ".join(segments) if segments else "買取品"

    return f"{cfg['title_prefix']}{label}{cfg['title_suffix']} <br>【{inner_str}】"


def build_heading(cfg: dict) -> str:
    return f"{cfg['heading_prefix']}{cfg.get('label', '')}{cfg['heading_suffix']}"


def build_product_line(cfg: dict, purchase: Purchase) -> str:
    """Centered product subtitle under the thanks line (manual EXPERIENCE style)."""
    many_threshold = int(cfg.get("many_threshold", 10))
    segments = [
        seg
        for pr in effective_products(purchase)
        if (seg := _product_title_segment(pr, many_threshold))
    ]
    return " / ".join(segments)


def build_default_tags(cfg: dict, purchase: Purchase) -> list[str]:
    """Tags used on live posts: store label (e.g. 東米里店) + makers."""
    tags: list[str] = []
    label = (cfg.get("label") or "").strip()
    if label:
        store_tag = label if label.endswith("店") else f"{label}店"
        tags.append(store_tag)
    for pr in effective_products(purchase):
        maker = (pr.get("manufacturer") or "").strip()
        if maker and maker not in tags:
            tags.append(maker)
    return tags


def build_excerpt(cfg: dict, purchase: Purchase, *, ai_excerpt: Optional[str] = None) -> str:
    """SEO-friendly excerpt for WP / AIOSEO (#post_excerpt).

    Live EXPERIENCE posts often leave excerpt empty in the editor; AIOSEO still
    scores better when a short meta description with product + store + CTA exists.
    Prefer a cleaned AI excerpt when present; otherwise build a deterministic one.
    """
    cleaned = (ai_excerpt or "").strip()
    cleaned = cleaned.replace("\n", " ")
    if cleaned and len(cleaned) >= 20:
        return cleaned[:120]

    label = (cfg.get("label") or "").strip()
    store = label if label.endswith("店") else (f"{label}店" if label else "パワトレ")
    area = (cfg.get("area") or "札幌").strip()
    products = effective_products(purchase)
    primary = products[0] if products else {}
    product = (
        (primary.get("product_name") or "").strip()
        or (primary.get("category") or "").strip()
        or "買取品"
    )
    maker = (primary.get("manufacturer") or "").strip()
    focus = f"{maker}{product}" if maker else product
    return f"{area}で{focus}の買取ならパワトレ{store}へ。出張買取・大量買取もご相談ください。"[:120]


def _image_html(main_image_url: Optional[str]) -> str:
    if not main_image_url:
        return ""
    # Class ``cf-main-image`` is a marker rewritten to wp-image-N on WP upload.
    return (
        f'<img class="cf-main-image aligncenter" src="{main_image_url}" alt="" />'
    )


def assemble_html(
    cfg: dict,
    heading: str,
    ai_body_html: str,
    *,
    main_image_url: Optional[str] = None,
    product_line: Optional[str] = None,
) -> str:
    """Wrap the AI body with the fixed header + footer to produce the final HTML."""
    color = cfg.get("thanks_color") or "#ff0000"
    thanks = (
        f'<p style="text-align: center;">'
        f'<strong><span style="color: {color};">{cfg["thanks_text"]}</span></strong></p>'
    )
    product_html = ""
    if product_line:
        product_html = (
            f'<p style="text-align: center;"><strong>{product_line}</strong></p>'
        )
    footer = cfg["footer_html"].format(
        phone_general=cfg.get("phone_general", ""),
        phone_dispatch=cfg.get("phone_dispatch", ""),
        line_url=cfg.get("line_url", "https://lin.ee/WnXr1bu"),
    )
    parts = [
        f'<h2 style="text-align: center;">{heading}</h2>',
        thanks,
        product_html,
        _image_html(main_image_url),
        (ai_body_html or "").strip(),
        footer,
    ]
    return "\n".join(p for p in parts if p)
