"""Buyback article template (buyersbox.co.jp style).

An article is composed of three parts:

    1. Fixed header   -> H2 heading + red bold "thank you" line (per store label)
    2. Variable body  -> the AI-written casual blog about the specific item
    3. Fixed footer   -> phone / LINE / VVF / store-info boilerplate (identical
                         on every article; NOT used for similarity)

The variable body is stored on ``ArticleVersion.body`` (so similarity only
compares the unique part). The fully assembled HTML is stored on
``ArticleVersion.rendered_html`` and is what gets pushed to WordPress.

Global defaults live here; each store may override any key via
``Store.article_config`` (a JSONB column).
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
    "thanks_color": "#e60000",
    "persona_intro": "こんにちは～🙋‍♀️パワトレギャルです💕",
    "many_threshold": 10,              # qty >= this => omit model number in title
    "phone_general": "011-827-1149",
    "phone_dispatch": "050-3479-0800",
    # Footer HTML is intentionally editable so staff can paste the exact
    # boilerplate (including real image URLs) later. {phone_*} are filled in.
    "footer_html": (
        '<hr />\n'
        '<div class="cf-footer">\n'
        '<p><strong>出張買取専用ダイヤルはこちら：</strong> {phone_dispatch}<br />\n'
        '<strong>パワフルトレードセンター総合ダイヤル</strong><br />\n'
        '最短1分カンタン査定はこちら： {phone_general}<br />\n'
        'LINE査定もご利用ください。 LINE査定はこちらから</p>\n'
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
        '<p>〒003-0876 北海道札幌市白石区東米里2090-170 定休日：日曜・祝日</p>\n'
        '</div>'
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


def build_title(cfg: dict, purchase: Purchase) -> str:
    """Title format:
    パワトレ{label}店から最新の買取情報【{メーカー} {商品名} {型番} {個数}】

    - Few items: メーカー 商品名 型番 (+ qty when > 1)
    - Many items (qty >= many_threshold): メーカー 商品名 (+ qty), model omitted
    """
    label = cfg.get("label", "")
    maker = (purchase.manufacturer or "").strip()
    product = (purchase.product_name or "").strip()
    model = (purchase.model_number or "").strip()
    qty = purchase.quantity or 1
    unit = (purchase.quantity_unit or "点").strip()
    many = qty >= int(cfg.get("many_threshold", 10))

    inner = [p for p in (maker, product) if p]
    if model and not many:
        inner.append(model)
    if qty and qty > 1:
        inner.append(f"{qty}{unit}")
    inner_str = " ".join(inner) if inner else (product or "買取品")

    return f"{cfg['title_prefix']}{label}{cfg['title_suffix']}【{inner_str}】"


def build_heading(cfg: dict) -> str:
    return f"{cfg['heading_prefix']}{cfg.get('label', '')}{cfg['heading_suffix']}"


def _image_html(main_image_url: Optional[str]) -> str:
    if not main_image_url:
        return ""
    return (
        f'<figure class="cf-main-image">'
        f'<img src="{main_image_url}" alt="買取商品" /></figure>'
    )


def assemble_html(
    cfg: dict,
    heading: str,
    ai_body_html: str,
    *,
    main_image_url: Optional[str] = None,
) -> str:
    """Wrap the AI body with the fixed header + footer to produce the final HTML."""
    thanks = (
        f'<p style="color:{cfg["thanks_color"]};font-weight:bold;">'
        f'{cfg["thanks_text"]}</p>'
    )
    footer = cfg["footer_html"].format(
        phone_general=cfg.get("phone_general", ""),
        phone_dispatch=cfg.get("phone_dispatch", ""),
    )
    parts = [
        f"<h2>{heading}</h2>",
        thanks,
        _image_html(main_image_url),
        (ai_body_html or "").strip(),
        footer,
    ]
    return "\n".join(p for p in parts if p)
