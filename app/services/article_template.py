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

import html as html_lib
import re
from typing import Iterable, Optional

from app.models import Purchase, Store

# Ward/city/prefecture tags (e.g. 札幌市東区) must not be sent to WordPress.
_LOCATION_TAG_RE = re.compile(
    r"(北海道|札幌|横浜|東京|大阪|名古屋|福岡|仙台|市|区|町|村|県|都|郡)"
)

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
    "phone_dispatch": "050-1809-4396",
    "line_url": "https://lin.ee/WnXr1bu",
    # Footer = the dial / LINE block only, byte-for-byte like manual EXPERIENCE
    # posts. The 買取価格 tables, SNS block, store info and maps below an article
    # are rendered by the theme for /experience/ posts — putting them in the
    # content produces empty duplicate headings.
    "footer_html": (
        '<p style="text-align: left;">'
        '<span style="color: #008000;"><strong>出張買取専用ダイヤル</strong></span>'
        'はこちら： <b>{phone_dispatch}</b><br />\n'
        '<span style="color: #008000;"><strong>パワフルトレードセンター総合ダイヤル</strong></span><br />\n'
        '最短1分カンタン査定はこちら： <b>{phone_general}</b><br />\n'
        'LINE査定もご利用ください。<br />\n'
        'LINE査定は<a href="{line_url}">こちら</a>から</p>'
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


def is_location_tag(tag: str, cfg: Optional[dict] = None) -> bool:
    """True for area/city tags such as 札幌市東区. Store names like 東米里店 are kept."""
    t = (tag or "").strip()
    if not t:
        return True
    if t.endswith("店"):
        return False
    area = ((cfg or {}).get("area") or "").strip()
    if area and (t == area or t in area or area in t):
        return True
    return bool(_LOCATION_TAG_RE.search(t))


def filter_content_tags(tags: Iterable[str], cfg: Optional[dict] = None) -> list[str]:
    """Drop empty and location tags; keep store / maker / product tags."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        t = str(raw).strip()
        if not t or t in seen or is_location_tag(t, cfg):
            continue
        seen.add(t)
        out.append(t)
    return out


def build_default_tags(cfg: dict, purchase: Purchase) -> list[str]:
    """Tags used on live posts: store label (e.g. 東米里店) + makers. No area tags."""
    tags: list[str] = []
    label = (cfg.get("label") or "").strip()
    if label:
        store_tag = label if label.endswith("店") else f"{label}店"
        tags.append(store_tag)
    for pr in effective_products(purchase):
        maker = (pr.get("manufacturer") or "").strip()
        if maker and maker not in tags:
            tags.append(maker)
    return filter_content_tags(tags, cfg)


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


def _image_html(main_image_url: Optional[str], alt: str = "") -> str:
    if not main_image_url:
        return ""
    # Class ``cf-main-image`` is a marker rewritten to wp-image-N on WP upload.
    return (
        f'<img class="cf-main-image aligncenter" src="{main_image_url}" alt="{alt}" />'
    )


def assemble_html(
    cfg: dict,
    heading: str,
    ai_body_html: str,
    *,
    main_image_url: Optional[str] = None,
    product_line: Optional[str] = None,
    related_posts: Optional[Iterable[dict]] = None,
) -> str:
    """Wrap the AI body with the fixed header + footer to produce the final HTML.

    Structure mirrors manual EXPERIENCE posts: centered H2, centered red thanks,
    centered main image, body, optional related block, dial/LINE footer.
    """
    color = cfg.get("thanks_color") or "#ff0000"
    thanks = (
        f'<p style="text-align: center;">'
        f'<strong><span style="color: {color};">{cfg["thanks_text"]}</span></strong></p>'
    )
    footer = cfg["footer_html"].format(
        phone_general=cfg.get("phone_general", ""),
        phone_dispatch=cfg.get("phone_dispatch", ""),
        line_url=cfg.get("line_url", "https://lin.ee/WnXr1bu"),
    )
    alt = f"{product_line}買取" if product_line else ""
    parts = [
        f'<h2 style="text-align: center;">{heading}</h2>',
        thanks,
        _image_html(main_image_url, alt),
        (ai_body_html or "").strip(),
        build_related_html(related_posts),
        footer,
    ]
    return "\n".join(p for p in parts if p)


def _format_related_date(raw: str) -> str:
    """Normalize ISO / WP dates to buyersbox style ``YYYY.MM.DD``."""
    text = (raw or "").strip()
    if not text:
        return ""
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not m:
        return ""
    return f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"


def _related_title_html(title: str) -> str:
    """Keep intentional ``<br>`` breaks; escape the rest for safe overlay text."""
    raw = (title or "").strip()
    if not raw:
        return ""
    # Normalize common break variants from WP titles.
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html_lib.unescape(raw).replace("&nbsp;", " ").strip()
    parts = [p.strip() for p in re.split(r"[\n]+", raw) if p.strip()]
    if not parts:
        return ""
    return "<br>".join(html_lib.escape(p) for p in parts)


def build_related_html(related_posts: Optional[Iterable[dict]]) -> str:
    """HTML block for manually selected related articles (max 4).

    Markup mirrors the buyersbox YARPP thumbnail gallery
    (``年間買取10000件 パワトレ買取実績``) so the live theme CSS renders a
    2×2 image grid with centered dark title overlays.
    """
    items = [r for r in (related_posts or []) if (r.get("title") or "").strip()][:4]
    if not items:
        return ""

    cards: list[str] = []
    for row in items:
        title_html = _related_title_html(row.get("title") or "")
        link = html_lib.escape((row.get("link") or "").strip(), quote=True)
        thumb = html_lib.escape((row.get("thumbnail") or "").strip(), quote=True)
        date = _format_related_date(row.get("date") or "")
        date_html = (
            f'<span class="cf-related-date">{html_lib.escape(date)}</span>'
            if date
            else ""
        )
        img = (
            f'<img class="container_01_image" width="480" height="480" '
            f'src="{thumb}" alt="" data-pin-nopin="true" />'
            if thumb
            else '<span class="container_01_image cf-related-placeholder"></span>'
        )
        overlay = (
            f'<div class="in_img-text yarpp-thumbnail-title">'
            f"{date_html}"
            f'<span class="cf-related-title-text">{title_html}</span>'
            f"</div>"
        )
        attrs = (
            f'class="container_01 yarpp-thumbnail" rel="norewrite" href="{link}"'
            if link
            else 'class="container_01 yarpp-thumbnail" rel="norewrite"'
        )
        tag = "a" if link else "div"
        cards.append(f"<{tag} {attrs}>{img}{overlay}</{tag}>")

    # Hide theme-auto YARPP when this manual block is present, and force a
    # reliable 2-column layout even if theme CSS is unavailable in content.
    style = (
        "<style>"
        ".yarpp:not(.cf-manual-related){display:none!important;}"
        ".cf-manual-related.yarpp{display:block!important;margin:24px 0;}"
        ".cf-manual-related>h3{"
        "background:#111;color:#fff;font-size:16px;font-weight:700;"
        "line-height:1.4;margin:0 0 12px;padding:10px 14px;position:relative;"
        "}"
        ".cf-manual-related>h3::after{"
        "content:'//';position:absolute;right:14px;top:50%;"
        "transform:translateY(-50%);letter-spacing:2px;opacity:.85;"
        "}"
        ".cf-manual-related .yarpp-thumbnails-horizontal{"
        "display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));"
        "gap:10px;width:100%;margin:0;"
        "}"
        ".cf-manual-related .yarpp-thumbnail{"
        "position:relative;display:block;overflow:hidden;border-radius:4px;"
        "aspect-ratio:1/1;background:#222;text-decoration:none;"
        "}"
        ".cf-manual-related .container_01_image,"
        ".cf-manual-related .cf-related-placeholder{"
        "display:block;width:100%!important;height:100%!important;"
        "object-fit:cover;border-radius:0!important;margin:0!important;"
        "}"
        ".cf-manual-related .cf-related-placeholder{background:#444;min-height:180px;}"
        ".cf-manual-related .in_img-text{"
        "position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);"
        "width:85%!important;margin:0;padding:6px 10px;color:#fff;"
        "background:rgba(0,0,0,.8);font-size:13px!important;font-weight:700;"
        "line-height:1.45;text-align:center;box-sizing:border-box;"
        "}"
        ".cf-manual-related .cf-related-date{display:block;margin-bottom:2px;}"
        "@media (max-width:560px){"
        ".cf-manual-related .yarpp-thumbnails-horizontal{"
        "grid-template-columns:1fr!important;"
        "}"
        "}"
        "</style>"
    )

    return (
        "<!--cf-related-start-->"
        f"{style}"
        '<div class="custom-relate yarpp yarpp-related yarpp-related-website '
        'yarpp-template-thumbnails cf-manual-related">'
        "<h3>年間買取10000件　<br class=\"sp\">パワトレ買取実績</h3>"
        '<div class="yarpp-thumbnails-horizontal">'
        f"{''.join(cards)}"
        "</div>"
        "</div>"
        "<!--cf-related-end-->"
    )


def inject_related_into_html(html: str, related_posts: Optional[Iterable[dict]]) -> str:
    """Replace or insert the related block before the dial/LINE footer."""
    block = build_related_html(related_posts)
    cleaned = re.sub(
        r"<!--cf-related-start-->[\s\S]*?<!--cf-related-end-->\s*",
        "",
        html or "",
        count=1,
    )
    if not block:
        return cleaned.strip()
    marker = "出張買取専用ダイヤル"
    idx = cleaned.find(marker)
    if idx >= 0:
        p_start = cleaned.rfind("<p", 0, idx)
        if p_start >= 0:
            return cleaned[:p_start].rstrip() + "\n" + block + "\n" + cleaned[p_start:]
    return cleaned.rstrip() + "\n" + block

