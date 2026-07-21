"""Builds the system/user prompts for article generation & regeneration
(workflows 5 & 8), assembling persona, brand rules, structure and prohibited
words per the specification.

Buyersbox-style prompts are tuned from live EXPERIENCE articles:
https://www.buyersbox.co.jp/experience
"""
from __future__ import annotations

from typing import List, Optional

from app.enums import ContentRuleType, RegenerationScope
from app.models import ContentRule, Persona, Purchase, Store
from app.services.article_template import effective_products

ARTICLE_JSON_SCHEMA = (
    "Respond ONLY with JSON using exactly these keys: "
    "title (string), introduction (string), "
    "headings (array of {heading: string, content: string}), "
    "body (string, full article body in HTML), excerpt (string, <=120 chars), "
    "category_suggestion (string), tag_suggestions (array of strings)."
)


def build_system_prompt(persona: Optional[Persona], store: Store) -> str:
    parts: List[str] = [
        "You are an expert copywriter for a Japanese second-hand goods retailer.",
        f"You are writing a buyback/product article for the store: {store.name}.",
        "Write natural, engaging, SEO-friendly Japanese unless instructed otherwise.",
    ]
    if persona:
        parts.append(f"Persona: {persona.name}. {persona.description}")
        if persona.tone:
            parts.append(f"Tone: {persona.tone}.")
        if persona.writing_style:
            parts.append(f"Writing style: {persona.writing_style}.")
        if persona.system_prompt:
            parts.append(persona.system_prompt)
    return "\n".join(parts)


def _rules_by_type(rules: List[ContentRule], rule_type: ContentRuleType) -> List[str]:
    return [r.value for r in rules if r.rule_type == rule_type and r.is_active]


def build_user_prompt(
    purchase: Purchase,
    rules: List[ContentRule],
    *,
    user_instructions: Optional[str] = None,
    regeneration_scope: Optional[RegenerationScope] = None,
    regeneration_instruction: Optional[str] = None,
    target_section: Optional[str] = None,
    previous_body: Optional[str] = None,
) -> str:
    lines: List[str] = ["## Product information"]
    fields = {
        "Manufacturer": purchase.manufacturer,
        "Product name": purchase.product_name,
        "Model number": purchase.model_number,
        "Category": purchase.category,
        "Condition": purchase.condition,
        "Characteristics": purchase.characteristics,
        "Price": purchase.price,
        "Notes": purchase.manual_notes,
    }
    for label, value in fields.items():
        if value not in (None, ""):
            lines.append(f"- {label}: {value}")
    if purchase.extra_info:
        for key, value in purchase.extra_info.items():
            lines.append(f"- {key}: {value}")

    prohibited = _rules_by_type(rules, ContentRuleType.PROHIBITED_WORD)
    if prohibited:
        lines.append("\n## Prohibited words (must NOT appear)")
        lines.append(", ".join(prohibited))

    contexts = _rules_by_type(rules, ContentRuleType.PROHIBITED_CONTEXT)
    if contexts:
        lines.append("\n## Prohibited contexts (avoid these claims/themes)")
        lines.extend(f"- {c}" for c in contexts)

    brand = _rules_by_type(rules, ContentRuleType.BRAND_RULE)
    if brand:
        lines.append("\n## Common brand rules")
        lines.extend(f"- {b}" for b in brand)

    structure = _rules_by_type(rules, ContentRuleType.STRUCTURE)
    lines.append("\n## Required article structure")
    if structure:
        lines.extend(f"- {s}" for s in structure)
    else:
        lines.append("- Title, introduction, 2-4 headed sections, and a short excerpt.")

    combined_instructions = user_instructions or purchase.user_instructions
    if combined_instructions:
        lines.append("\n## Additional user instructions")
        lines.append(combined_instructions)

    if regeneration_scope:
        lines.append("\n## Regeneration request")
        lines.append(_regeneration_directive(regeneration_scope, target_section))
        if regeneration_instruction:
            lines.append(f"Instruction: {regeneration_instruction}")
        if previous_body:
            lines.append("\n## Previous version (for reference / to differ from)")
            lines.append(previous_body[:4000])

    lines.append("\n" + ARTICLE_JSON_SCHEMA)
    return "\n".join(lines)


# ==========================================================================
# Buyersbox EXPERIENCE style (from live articles on buyersbox.co.jp)
# ==========================================================================
BUYERSBOX_JSON_SCHEMA = (
    "Respond ONLY with JSON using exactly these keys:\n"
    "body (string: HTML of <p> paragraphs only; may include <strong> and emoji; "
    "NO <h1>, <h2>, phone numbers, store addresses, LINE links, or VVF/footer blocks),\n"
    "excerpt (string, <=80 Japanese chars, one soft CTA sentence),\n"
    "category_suggestion (string: one Japanese category noun, e.g. カーナビ / 電動工具 / 電線),\n"
    "tag_suggestions (array of 3-6 Japanese strings: maker, product type, store area)."
)

# Few-shot bodies distilled from real EXPERIENCE posts (variable part only).
STYLE_EXAMPLE_GAL = """\
<p>こんにちは～🙋‍♀️パワトレギャルです💕</p>
<p>本日は豊平店にて、<strong>ケンウッドのカーナビ「MDV-L613W」</strong>を2台買取させていただきました🚗✨</p>
<p>新品が2台並ぶと「どっちの車に付けようかな～」なんて妄想しちゃいます🤣<br />
…免許はあるんですけど、方向音痴なので結局ナビ頼りなんですけどね😂🗺️</p>
<p>パワトレは電線や工具のイメージが強いかもしれませんが、<strong>カーナビやカー用品も買取しています！</strong>✨</p>
<p>札幌市豊平区でカーナビ買取ならパワトレへ📍<br />
ケンウッドをはじめ、カロッツェリア・パナソニック・アルパインなど各メーカーも大歓迎！</p>
<p>新品・未使用品はもちろん、余剰在庫や倉庫整理品もお気軽にお持ち込みください😊🙌</p>"""

STYLE_EXAMPLE_OJISAN = """\
<p>どうも、パワトレおじさんです👨</p>
<p>本日は苗穂店にて、<strong>矢崎のVCTFケーブル 2×0.75</strong>を買取させていただきました⚡</p>
<p>VVFケーブルのお持ち込みが多い当店ですが、こういう<strong>VCTFケーブル</strong>ももちろん大歓迎です😊</p>
<p>私は勝手に「包まれ系電線」なんて呼んでるんですが、この丸っこい見た目、なんだか安心感があるんですよね（笑）</p>
<p>なんとも言えない手触りの梱包紙で、結構好きですね。</p>
<p>札幌市東区でVCTFケーブル買取・電線買取ならパワトレ苗穂店へ！<br />
矢崎はもちろん、VVF・IV・CV・LANケーブルなど各種電線を積極買取中です。</p>
<p>「VVFじゃないから売れないかな？」と思っている電線こそ、一度お持ちください。一本一本しっかり査定させていただきます👍</p>"""

STYLE_EXAMPLE_SOKUHOU = """\
<p><strong>KENWOOD（ケンウッド） カーナビ MDV-D612W</strong></p>
<p>🚗【買取速報】パワフルトレードセンター豊平店より！</p>
<p>本日は、KENWOOD（ケンウッド）製 カーナビ「MDV-D612W」を<br />
✨<strong>新品</strong>✨で買取させていただきました！</p>
<p>道に迷いがちな方にはまさに救世主…👀<br />
ナビがあるだけで安心感が全然違いますよね🚗³₃（笑）</p>
<p>パワトレでは、<br />
📡 <strong>カーナビ・カー用品の買取も対応中！</strong><br />
新品はもちろん、状態の良い中古品もご相談ください👌</p>
<p>使わずに眠っているカー用品があれば、ぜひ豊平店へ😊<br />
お持ち込みありがとうございました！</p>"""


def _persona_key(persona: Optional[Persona], cfg: dict) -> str:
    """Map persona / config to a style variant: gal | ojisan | sokuhou."""
    if cfg.get("style") in ("gal", "ojisan", "sokuhou"):
        return str(cfg["style"])
    name = (persona.name if persona else "") or ""
    if "おじさん" in name:
        return "ojisan"
    if "速報" in name or "sokuhou" in name.lower():
        return "sokuhou"
    return "gal"


def _persona_intro(key: str, cfg: dict) -> str:
    if key == "ojisan":
        return cfg.get("persona_intro") or "どうも、パワトレおじさんです👨"
    if key == "sokuhou":
        return ""  # product-first style; no greeting line
    return cfg.get("persona_intro") or "こんにちは～🙋‍♀️パワトレギャルです💕"


def _competitor_brands(category: str) -> str:
    cat = category or ""
    if any(k in cat for k in ("ナビ", "カー", "電化")):
        return "カロッツェリア・パナソニック・アルパインなど"
    if any(k in cat for k in ("電線", "ケーブル", "VVF", "VCTF", "IV", "CV")):
        return "矢崎・富士・弥栄・愛知電線など"
    if any(k in cat for k in ("工具", "ドリル", "インパクト", "電動")):
        return "マキタ・ハイコーキ・ボッシュ・リョービなど"
    return "各メーカー"


def build_buyersbox_system_prompt(cfg: dict, persona: Optional[Persona]) -> str:
    key = _persona_key(persona, cfg)
    intro = _persona_intro(key, cfg)

    parts = [
        "あなたは札幌の買取店「パワフルトレードセンター（通称パワトレ）」の",
        "EXPERIENCEブログ（https://www.buyersbox.co.jp/experience）専用コピーライターです。",
        "出力は日本語のみ。口調・長さ・絵文字量は実店舗の公開記事に合わせます。",
        "",
        "## 文体ルール（厳守）",
        "- 短文・1段落あたり1〜3文。全文でおおむね 350〜650字（HTMLタグ除く）。",
        "- 「です・ます」調。馴れ馴れしくても誇大表現・虚假のスペックは禁止。",
        "- 絵文字は段落あたり最大1〜2個。並べすぎない。",
        "- 商品名・型番は入力どおり正確に。推測で型番を作らない。不明なら書かない。",
        "- 価格・保証・査定額は絶対に書かない。",
        "- HTMLは <p> / <br /> / <strong> のみ。見出し・リスト・リンク禁止。",
        "- 電話番号・LINE・店舗住所・VVF価格・フッターは本文に入れない（システム側が付与）。",
        "- 強調したい商品名・キーフレーズは <strong>…</strong> で囲む。",
        "",
    ]

    if key == "gal":
        parts += [
            "## 人格：パワトレギャル",
            f"- 冒頭は必ず「{intro}」",
            "- 明るく少し甘い口調。「～」「…」「（笑）」OK。",
            "- 商品にまつわる軽い自虐・妄想を1つ入れる（例：方向音痴→ナビ）。",
            "",
            "## 良い例（ギャル）",
            STYLE_EXAMPLE_GAL,
        ]
    elif key == "ojisan":
        parts += [
            "## 人格：パワトレおじさん",
            f"- 冒頭は必ず「{intro}」",
            "- 温厚でやや落ち着いた口調。マニア寄りだが押しつけない。",
            "- 商品の見た目・触感の本音コメントを1〜2文。",
            "",
            "## 良い例（おじさん）",
            STYLE_EXAMPLE_OJISAN,
        ]
    else:
        parts += [
            "## 人格：買取速報スタイル",
            "- 冒頭は自己紹介ではなく、商品名の太字行 →「【買取速報】…より！」",
            "- テンポよく、状態（新品など）を目立たせる。",
            "",
            "## 良い例（速報）",
            STYLE_EXAMPLE_SOKUHOU,
        ]

    if persona and persona.system_prompt:
        parts.append("\n## 追加ペルソナ指示")
        parts.append(persona.system_prompt)
    if persona and persona.tone:
        parts.append(f"トーン補足: {persona.tone}")

    return "\n".join(parts)


def build_buyersbox_user_prompt(
    cfg: dict,
    purchase: Purchase,
    rules: List[ContentRule],
    *,
    persona: Optional[Persona] = None,
    user_instructions: Optional[str] = None,
    regeneration_instruction: Optional[str] = None,
    previous_body: Optional[str] = None,
) -> str:
    key = _persona_key(persona, cfg)
    label = cfg.get("label", "")
    area = cfg.get("area", "")
    products = effective_products(purchase)
    multi = len(products) > 1
    primary = products[0]
    qty = primary["quantity"] or 1
    unit = primary["quantity_unit"] or "点"
    maker = primary["manufacturer"]
    product = primary["product_name"]
    model = primary["model_number"]
    category = (primary["category"] or product or "商品").strip()
    condition = primary["condition"]
    brands = _competitor_brands(category)
    store_call = f"{label}店" if label else "当店"

    # Exact product phrase used in the purchase announcement.
    product_phrase_parts = [p for p in (maker, product) if p]
    product_phrase = "".join(
        [
            f"{maker}の" if maker else "",
            product or category,
            f"「{model}」" if model else "",
        ]
    ) or category
    bold_phrase = " ".join(product_phrase_parts + ([model] if model else []))

    lines: List[str] = [
        "## 今回の買取（これら以外の事実を捏造しない）",
    ]
    info = {
        "店舗ラベル": label,
        "店舗の呼び方": store_call,
        "エリア（SEO）": area,
        "買取方法": purchase.purchase_method,
        "メーカー": maker,
        "商品名": product,
        "型番": model,
        "数量": f"{qty}{unit}",
        "状態": condition,
        "カテゴリー": category,
        "特徴": purchase.characteristics,
        "備考": purchase.manual_notes,
    }
    for k, v in info.items():
        if v not in (None, ""):
            lines.append(f"- {k}: {v}")

    if multi:
        lines.append("\n## 買取商品リスト（複数）")
        lines.append("今回はまとめ買取です。以下すべての商品に自然に触れてください。")
        for i, pr in enumerate(products, 1):
            seg = " ".join(
                x for x in (pr["manufacturer"], pr["product_name"], pr["model_number"]) if x
            )
            q = f'（{pr["quantity"]}{pr["quantity_unit"]}）' if (pr["quantity"] or 1) > 1 else ""
            extra = f' / 状態:{pr["condition"]}' if pr["condition"] else ""
            lines.append(f"{i}. {seg or pr['category'] or '商品'}{q}{extra}")

    lines.append("\n## 必須の段落構成（この順で 5〜7 の <p>）")
    if multi:
        lines.append(
            "※ 複数商品のため、②では代表商品ではなく『まとめてお売りいただいた』旨を述べ、"
            "続く段落で各商品を1〜2文ずつ自然に紹介する（型番の羅列にしない）。"
        )
    if key == "sokuhou":
        lines.append(f'1. <p><strong>{bold_phrase or product_phrase}</strong></p>')
        lines.append(
            f'2. <p>🚗【買取速報】パワフルトレードセンター{store_call}より！</p>'
        )
        cond = f"✨<strong>{condition}</strong>✨で" if condition else ""
        lines.append(
            f'3. 「本日は、{product_phrase}を{cond}買取させていただきました！」'
        )
    else:
        lines.append(f'1. 冒頭の自己紹介（システム指定どおり）')
        lines.append(
            f'2. 「本日は{store_call}にて、<strong>{product_phrase}</strong>を'
            f'{qty}{unit}買取させていただきました」＋絵文字1つ'
        )
        if condition:
            lines.append(f'   （状態が分かる場合は自然に「{condition}」と触れてよい）')

    lines.append("3. 商品に紐づく短い人間味コメント（1〜2文）。スペック羅列は禁止。")
    lines.append(
        f'4. 「パワトレは電線や工具のイメージが強いかもしれませんが、'
        f'<strong>{category}も買取しています！</strong>」に近い文'
        "（カテゴリが電線・工具そのものの場合は自然に言い換える）"
    )
    if area:
        lines.append(
            f'5. 「{area}で{category}買取ならパワトレへ📍」＋'
            f'「{maker or "当メーカー"}をはじめ、{brands}も大歓迎」'
        )
    lines.append(
        "6. 締め："
        "「新品・未使用品はもちろん、余剰在庫や倉庫整理品 / 状態の良い中古もお気軽に」"
        "のいずれか近い表現。お持ち込みありがとうで終えてよい。"
    )

    lines.append("\n## 品質チェック")
    lines.append("- 入力にない型番・数量・状態を追加していないか")
    lines.append("- 電話番号 / LINE / 定型フッターを本文に入れていないか")
    lines.append("- 例文のコピペではなく、今回の商品向けに言い換えたか")
    lines.append("- 類似記事と表現が丸かぶりしない程度に新鮮な言い回しか")

    prohibited = _rules_by_type(rules, ContentRuleType.PROHIBITED_WORD)
    if prohibited:
        lines.append("\n## 使用禁止ワード")
        lines.append("、".join(prohibited))
    contexts = _rules_by_type(rules, ContentRuleType.PROHIBITED_CONTEXT)
    if contexts:
        lines.append("\n## 禁止コンテキスト")
        lines.extend(f"- {c}" for c in contexts)

    combined = user_instructions or purchase.user_instructions
    if combined:
        lines.append("\n## スタッフ追加指示（優先）")
        lines.append(combined)

    if regeneration_instruction:
        lines.append("\n## 再生成の指示")
        lines.append(regeneration_instruction)
    if previous_body:
        lines.append("\n## 前回本文（丸写し禁止・差異を出せ）")
        lines.append(previous_body[:2500])

    lines.append("\n" + BUYERSBOX_JSON_SCHEMA)
    return "\n".join(lines)


def _regeneration_directive(scope: RegenerationScope, target_section: Optional[str]) -> str:
    return {
        RegenerationScope.FULL: "Regenerate the entire article with fresh wording.",
        RegenerationScope.TITLE: "Regenerate ONLY the title; keep other fields consistent.",
        RegenerationScope.INTRODUCTION: "Regenerate ONLY the introduction.",
        RegenerationScope.SECTION: f"Regenerate ONLY the section: {target_section}.",
        RegenerationScope.DIFFERENT_TONE: "Rewrite the article using a clearly different tone.",
        RegenerationScope.MORE_DIFFERENT: (
            "Rewrite the article to be substantially different in structure and "
            "wording from previous/published articles while keeping facts accurate."
        ),
    }.get(scope, "Regenerate the entire article.")
