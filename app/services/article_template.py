"""Buyback article template (buyersbox.co.jp style).

An article is composed of:

    1. Fixed header   -> centered H2 + centered red thanks + optional product line
                         + centered main image (WordPress aligncenter)
    2. Variable body  -> the AI-written casual blog about the specific item
    3. Dial footer    -> phone / LINE block
    4. Related block  -> optional CF gallery (manual posts use YARPP here)
    5. After footer   -> VVF / ペアコイル images, SNS QR, 3-store maps
                         (same layout as live post #16708)

The variable body is stored on ``ArticleVersion.body`` (so similarity only
compares the unique part). The fully assembled HTML is stored on
``ArticleVersion.rendered_html`` and is what gets pushed to WordPress.

Global defaults live here; each store may override any key via
``Store.article_config`` (a JSONB column).

Markup mirrors manual EXPERIENCE posts (reference: post #16708).
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

# Live media used on every EXPERIENCE post (from buyersbox.co.jp post #16708).
_VVF_PRICE_IMG = (
    "https://www.buyersbox.co.jp/wp/wp-content/uploads/2026/06/"
    "0391f739ac5e4e662cf9c9355008b588.jpg"
)
_PAIR_COIL_IMG = (
    "https://www.buyersbox.co.jp/wp/wp-content/uploads/2026/06/"
    "851581fd0325e7f22df4ea70b523613f.jpg"
)
_LINE_QR_IMG = "https://www.buyersbox.co.jp/wp/wp-content/uploads/2024/06/line.png"
_IG_QR_IMG = (
    "https://www.buyersbox.co.jp/wp/wp-content/uploads/2024/02/powetre.cen_qr-557x640.png"
)
_STORE_IMG_NAEBO = "https://www.buyersbox.co.jp/wp/wp-content/uploads/2023/10/02-640x427.jpg"
_STORE_IMG_TOYOHIRA = (
    "https://www.buyersbox.co.jp/wp/wp-content/themes/original/images/takahiro-box/BB.jpg"
)
_STORE_IMG_YONESATO = (
    "https://www.buyersbox.co.jp/wp/wp-content/themes/original/images/"
    "takahiro-box/%E6%9D%B1%E7%B1%B3%E9%87%8C%E5%BA%97.png"
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
    "phone_dispatch": "050-3479-0800",
    "line_url": "https://lin.ee/WnXr1bu",
    # Dial / LINE only. Related gallery is inserted after this, then after_footer.
    "footer_html": (
        '<p style="text-align: left;">'
        '<span style="color: #008000;"><strong>出張買取専用ダイヤル</strong></span>'
        'はこちら： <b>{phone_dispatch}</b><br />\n'
        '<span style="color: #008000;"><strong>パワフルトレードセンター総合ダイヤル</strong></span><br />\n'
        '最短1分カンタン査定はこちら： <b>{phone_general}</b><br />\n'
        'LINE査定もご利用ください。<br />\n'
        'LINE査定は<a href="{line_url}">こちら</a>から</p>'
    ),
    # Filled by build_after_footer_html() below (VVF / SNS / stores).
    "after_footer_html": "",
}


def build_after_footer_html(*, phone_general: str = "011-827-1149") -> str:
    """Shared EXPERIENCE tail after related articles (post #16708 layout)."""
    tel = html_lib.escape(phone_general)
    return f"""<!--cf-after-footer-start-->
<hr class="mt60" />
<h5 style="text-align: center;">【札幌市内No.1】<br>最新のVVF電線買取価格</h5>
<div class="mt40">
<figure class="wp-block-image size-large"><img decoding="async" src="{_VVF_PRICE_IMG}" alt="VVF電線買取価格" class="wp-image-16441" /></figure>
</div>
<hr class="mt60" />
<h5 style="text-align: center;">【札幌市内No.1】<br>最新のペアコイル買取価格</h5>
<div class="mt40">
<figure class="wp-block-image size-large"><img loading="lazy" decoding="async" src="{_PAIR_COIL_IMG}" alt="ペアコイル買取価格" class="wp-image-16357" /></figure>
</div>
<hr class="mt60" />
<h5 style="text-align: center;">SNS情報発信&amp;査定依頼受付中</h5>
<p class="mt20" style="text-align: center;">
無料査定はLINE、インスタのDM、電話から受け付けております😎<br />
お電話よりLINE、インスタグラムDMでの査定の方がより正確な査定額をご連絡できますのでおすすめです♪<br />
査定額でご納得いただけましたらそのままご来店日時のご連絡も受け付けております！買取商品が多い場合は出張買取も対応しております🚗💨
</p>
<p style="text-align: center;"><a class="sns__tel mt20" href="tel:{tel}">☎︎：{tel}</a></p>
<div>
<ul class="sns__icon-wrap mt20">
<li><a href="https://page.line.me/613fwlhk?openQrModal=true"><img src="{_LINE_QR_IMG}" alt="LINE" width="400" height="300" /></a></li>
<li><a href="https://www.instagram.com/powetre.cen/"><img src="{_IG_QR_IMG}" alt="Instagram" width="400" height="300" /></a></li>
</ul>
</div>
<hr class="mt60" />
<div class="map__wrap mt40">
<!-- 東苗穂 -->
<h4>● パワフルトレードセンター 東苗穂店</h4>
<div class="map-container mt20">
<img src="{_STORE_IMG_NAEBO}" alt="東苗穂店" width="400" height="300" class="alignnone size-medium wp-image-5561 shop-img" style="object-fit: cover; margin-right: 10px;" />
<iframe src="https://www.google.com/maps/embed?pb=!4v1696668903845!6m8!1m7!1sCAoSLEFGMVFpcE85eWtacWIxcFg2ZE5EbnpReS0zbWlBdkx3a2VNd20zam4zVVBQ!2m2!1d43.08611046008158!2d141.4029573217392!3f303.31!4f-2.319999999999993!5f0.4000000000000002" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="store-view"></iframe>
</div>
<p style="text-align: center;">
<br /><span>〒007-0803</span><br />
<span>北海道札幌市東区東苗穂3条1丁目3-45 コスモロイヤル東苗穂A棟 1F</span><br />
<span>定休日：日曜・祝日</span><br />
<a href="/takahiro-box#store-info-1"><span style="text-decoration: underline; color: #000!important;">詳しい店舗情報はこちら</span></a><br />
<br /><iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d1456.938389287661!2d141.40160165660876!3d43.086085851647766!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x5f0b2fe72b79b61f%3A0xad919e4358c75373!2z44OR44Ov44OV44Or44OI44Os44O844OJ44K744Oz44K_44O85p2x6IuX56mC5bqXKOODkeODr-ODleODq-iyt-WPluOCu-ODs-OCv-ODvCk!5e0!3m2!1sja!2sjp!4v1697186127724!5m2!1sja!2sjp" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="map"></iframe>
</p>
<!-- 豊平 -->
<h4>● パワフルトレードセンター 豊平店</h4>
<div class="map-container mt20">
<img src="{_STORE_IMG_TOYOHIRA}" alt="豊平店" width="400" height="300" class="size-medium wp-image-5541 shop-img" style="object-fit: cover; margin-right: 10px;" />
<iframe src="https://www.google.com/maps/embed?pb=!4v1696668925555!6m8!1m7!1sCAoSLEFGMVFpcE1FUENfa29WUTRybkp4d0pSTFVBRGNpa3hxbG5xOEx4aHkzdEpj!2m2!1d43.04808588136832!2d141.3776521227879!3f303.0121462985205!4f-7.844453741452611!5f0.4000000000000002" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="store-view"></iframe>
</div>
<p style="text-align: center;">
<br /><span>〒062-0903</span><br />
<span>北海道札幌市豊平区豊平3条9丁目3-10　エムズ豊平１F</span><br />
<span>定休日：日曜・祝日</span><br />
<a href="/takahiro-box#store-info-2"><span style="text-decoration: underline; color: #000!important;">詳しい店舗情報はこちら</span></a><br />
<br /><iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d23325.469362714506!2d141.33954584598547!3d43.04808672084896!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x5f0b2a32aa16aaab%3A0x2d2ebd87762f8f17!2z44OR44Ov44OV44Or44OI44Os44O844OJ44K744Oz44K_44O86LGK5bmz5bqXKOODkeODr-ODleODq-iyt-WPluOCu-ODs-OCv-ODvCk!5e0!3m2!1sja!2sjp!4v1697186042166!5m2!1sja!2sjp" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="map"></iframe>
</p>
<!-- 東米里 -->
<h4>● パワフルトレードセンター 東米里店</h4>
<div class="map-container mt20">
<img src="{_STORE_IMG_YONESATO}" alt="東米里店" width="400" height="300" class="alignnone size-medium shop-img" style="object-fit: cover; margin-right: 10px;" />
<iframe src="https://www.google.com/maps/embed?pb=!4v1697703959827!6m8!1m7!1sCAoSLEFGMVFpcE5uMGVxaWx1UjlLWVZfZEs3UFBJUjVVTmhoX1ZMMldFckxvc2lz!2m2!1d43.08430388564238!2d141.4518002916817!3f180.18!4f-0.1700000000000017!5f0.7820865974627469" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="store-view"></iframe>
</div>
<p style="text-align: center;">
<br /><span>〒003-0876</span><br />
<span>北海道札幌市白石区東米里2090-170</span><br />
<span>定休日：日曜・祝日</span><br />
<a href="/takahiro-box#store-info-3"><span style="text-decoration: underline; color: #000!important;">詳しい店舗情報はこちら</span></a><br />
<br /><iframe src="https://www.google.com/maps/embed?pb=!1m14!1m8!1m3!1d11655.846165037865!2d141.4518002916817!3d43.08430388564238!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x5f0b2d96c3ff41b3%3A0xb325a5d4310655d1!2z44OR44Ov44OV44Or44OI44Os44O844OJ44K744Oz44K_44O85p2x57Gz6YeM5bqX77yI44OR44Ov44OV44Or6LK35Y-W44K744Oz44K_44O877yJ!5e0!3m2!1sja!2sjp!4v1697674709910!5m2!1sja!2sjp" width="100%" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" class="map"></iframe>
</p>
</div>
<!--cf-after-footer-end-->"""


DEFAULT_TEMPLATE["after_footer_html"] = build_after_footer_html()


def resolve_config(store: Optional[Store]) -> dict:
    """Merge the store's overrides over the global defaults."""
    cfg = dict(DEFAULT_TEMPLATE)
    if store is not None:
        if store.article_config:
            cfg.update({k: v for k, v in store.article_config.items() if v not in (None, "")})
        if not cfg.get("label"):
            cfg["label"] = store.name or ""
    after = (cfg.get("after_footer_html") or "").strip()
    if not after or "{phone_general}" in after:
        cfg["after_footer_html"] = build_after_footer_html(
            phone_general=cfg.get("phone_general") or "011-827-1149",
        )
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


def _format_dial(cfg: dict) -> str:
    return cfg["footer_html"].format(
        phone_general=cfg.get("phone_general", ""),
        phone_dispatch=cfg.get("phone_dispatch", ""),
        line_url=cfg.get("line_url", "https://lin.ee/WnXr1bu"),
    )


def _format_after_footer(cfg: dict) -> str:
    after = (cfg.get("after_footer_html") or "").strip()
    if not after:
        after = build_after_footer_html(
            phone_general=cfg.get("phone_general") or "011-827-1149",
        )
    try:
        return after.format(phone_general=cfg.get("phone_general", "011-827-1149"))
    except (KeyError, ValueError, IndexError):
        return after


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

    Order matches manual EXPERIENCE post #16708:
    H2 → thanks → product → image → body → dial → related → VVF/SNS/stores.
    """
    color = cfg.get("thanks_color") or "#ff0000"
    thanks = (
        f'<p style="text-align: center;">'
        f'<strong><span style="color: {color};">{cfg["thanks_text"]}</span></strong></p>'
    )
    product_html = ""
    if product_line:
        product_html = (
            f'<p style="text-align: center;"><strong>{html_lib.escape(product_line)}</strong></p>'
        )
    alt = f"{product_line}買取" if product_line else ""
    parts = [
        f'<h2 style="text-align: center;">{heading}</h2>',
        thanks,
        product_html,
        _image_html(main_image_url, alt),
        (ai_body_html or "").strip(),
        _format_dial(cfg),
        build_related_html(related_posts),
        _format_after_footer(cfg),
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

    WordPress runs ``wpautop`` on post content and breaks nested
    ``<div>`` inside ``<a>`` (that caused the tall gray collapsed layout).
    Cards therefore use only inline ``<span>`` children and CSS
    ``background-image``, wrapped in a Gutenberg HTML block so the markup
    stays intact on publish.
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
            f'<span class="cf-rel__date">{html_lib.escape(date)}</span>'
            if date
            else ""
        )
        bg = f' style="background-image:url({thumb})"' if thumb else ""
        inner = (
            f'<span class="cf-rel__overlay">'
            f"{date_html}"
            f'<span class="cf-rel__title">{title_html}</span>'
            f"</span>"
        )
        if link:
            cards.append(f'<a class="cf-rel__card" href="{link}"{bg}>{inner}</a>')
        else:
            cards.append(f'<span class="cf-rel__card"{bg}>{inner}</span>')

    # Keep CSS compact (one line) so wpautop does not insert <p> mid-rule.
    # Desktop stays 2x2; mobile rules only adjust type/spacing (and 1-col under 380px).
    style = (
        "<style type=\"text/css\">"
        ".yarpp{display:none!important;}"
        ".cf-rel{display:block!important;margin:24px 0;clear:both;"
        "width:100%!important;max-width:100%!important;box-sizing:border-box;}"
        ".cf-rel__head{background:#111;color:#fff;font-size:16px;font-weight:700;"
        "line-height:1.4;margin:0 0 12px;padding:10px 14px;position:relative;"
        "box-sizing:border-box;}"
        ".cf-rel__head::after{content:'//';position:absolute;right:14px;top:50%;"
        "transform:translateY(-50%);letter-spacing:2px;opacity:.85;}"
        ".cf-rel__grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));"
        "gap:10px;width:100%;margin:0;box-sizing:border-box;}"
        ".cf-rel__card{position:relative;display:block;overflow:hidden;border-radius:4px;"
        "aspect-ratio:1/1;background:#222 center/cover no-repeat;text-decoration:none;"
        "min-height:180px;box-sizing:border-box;width:100%;}"
        ".cf-rel__overlay{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);"
        "width:85%;max-width:85%;max-height:78%;margin:0;padding:6px 10px;color:#fff;"
        "background:rgba(0,0,0,.8);font-size:13px;font-weight:700;line-height:1.45;"
        "text-align:center;box-sizing:border-box;overflow:hidden;}"
        ".cf-rel__date{display:block;margin-bottom:2px;}"
        ".cf-rel__title{display:block;}"
        ".cf-rel__br{display:none;}"
        "@media (max-width:768px){"
        ".cf-rel{margin:16px 0;}"
        ".cf-rel__br{display:inline;}"
        ".cf-rel__head{font-size:13px;padding:8px 36px 8px 10px;margin:0 0 8px;}"
        ".cf-rel__head::after{right:10px;font-size:12px;}"
        ".cf-rel__grid{gap:6px!important;}"
        ".cf-rel__card{min-height:0;border-radius:3px;}"
        ".cf-rel__overlay{width:90%;max-width:90%;padding:4px 6px;font-size:10px;"
        "line-height:1.35;}"
        ".cf-rel__date{margin-bottom:1px;font-size:9px;}"
        ".cf-rel__title{display:-webkit-box;-webkit-box-orient:vertical;"
        "-webkit-line-clamp:4;overflow:hidden;}"
        "}"
        "@media (max-width:380px){"
        ".cf-rel__grid{grid-template-columns:1fr!important;gap:8px!important;}"
        ".cf-rel__card{min-height:160px;}"
        ".cf-rel__overlay{font-size:12px;padding:6px 8px;}"
        ".cf-rel__date{font-size:11px;}"
        ".cf-rel__title{-webkit-line-clamp:5;}"
        "}"
        "</style>"
    )

    # Gutenberg raw HTML block prevents wpautop from rewriting the structure.
    return (
        "<!--cf-related-start-->"
        "<!-- wp:html -->"
        f"{style}"
        '<div class="cf-rel">'
        '<div class="cf-rel__head">年間買取10000件　'
        '<br class="cf-rel__br" />パワトレ買取実績</div>'
        f'<div class="cf-rel__grid">{"".join(cards)}</div>'
        "</div>"
        "<!-- /wp:html -->"
        "<!--cf-related-end-->"
    )


def _strip_related_blocks(html: str) -> str:
    cleaned = re.sub(
        r"(?:<p>\s*)?<!--cf-related-start-->[\s\S]*?<!--cf-related-end-->(?:\s*</p>)?\s*",
        "",
        html or "",
        count=1,
    )
    cleaned = re.sub(
        r'<div class="custom-relate yarpp[^"]*cf-manual-related[^"]*"[\s\S]*?</div>\s*</div>\s*',
        "",
        cleaned,
        count=1,
    )
    return cleaned


def _strip_after_footer(html: str) -> str:
    return re.sub(
        r"(?:<p>\s*)?<!--cf-after-footer-start-->[\s\S]*?<!--cf-after-footer-end-->(?:\s*</p>)?\s*",
        "",
        html or "",
        count=1,
    )


def inject_related_into_html(html: str, related_posts: Optional[Iterable[dict]]) -> str:
    """Replace or insert the related block between dial and VVF/SNS after-footer."""
    block = build_related_html(related_posts)
    cleaned = _strip_related_blocks(html or "")
    if not block:
        return cleaned.strip()

    # Prefer inserting before after-footer / VVF section (post #16708 order).
    for marker in ("<!--cf-after-footer-start-->", "最新のVVF電線買取価格", "SNS情報発信"):
        idx = cleaned.find(marker)
        if idx >= 0:
            insert_at = cleaned.rfind("<hr", 0, idx)
            if insert_at < 0 or idx - insert_at > 200:
                insert_at = idx
            return cleaned[:insert_at].rstrip() + "\n" + block + "\n" + cleaned[insert_at:]

    # Fallback: after dial paragraph.
    marker = "出張買取専用ダイヤル"
    idx = cleaned.find(marker)
    if idx >= 0:
        p_end = cleaned.find("</p>", idx)
        if p_end >= 0:
            p_end += len("</p>")
            return cleaned[:p_end].rstrip() + "\n" + block + "\n" + cleaned[p_end:].lstrip()
    return cleaned.rstrip() + "\n" + block


def ensure_experience_tail(html: str, cfg: dict) -> str:
    """Guarantee dial + VVF/SNS/store tail exist (for older rendered_html on publish)."""
    text = html or ""
    after = _format_after_footer(cfg)
    dial = _format_dial(cfg)

    has_after = "VVF電線買取価格" in text and "SNS情報発信" in text and "map__wrap" in text
    has_dial = "出張買取専用ダイヤル" in text
    if has_after and has_dial:
        return text

    text = _strip_after_footer(text)

    if not has_dial:
        if "<!--cf-related-start-->" in text:
            text = text.replace(
                "<!--cf-related-start-->",
                dial + "\n<!--cf-related-start-->",
                1,
            )
        else:
            text = text.rstrip() + "\n" + dial

    if "VVF電線買取価格" not in text or "map__wrap" not in text:
        if "<!--cf-related-end-->" in text:
            text = text.replace(
                "<!--cf-related-end-->",
                "<!--cf-related-end-->\n" + after,
                1,
            )
        elif "出張買取専用ダイヤル" in text:
            idx = text.find("出張買取専用ダイヤル")
            p_end = text.find("</p>", idx)
            if p_end >= 0:
                p_end += len("</p>")
                rel_end = text.find("<!--cf-related-end-->", p_end)
                if rel_end >= 0:
                    rel_end += len("<!--cf-related-end-->")
                    text = text[:rel_end] + "\n" + after + text[rel_end:]
                else:
                    text = text[:p_end] + "\n" + after + text[p_end:]
            else:
                text = text.rstrip() + "\n" + after
        else:
            text = text.rstrip() + "\n" + after

    return text

