"""Seed baseline data: first admin, a demo store, persona and content rules.

Usage:  python -m scripts.seed
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionFactory, engine
from app.core.logging import get_logger
from app.core.security import hash_password
from app.enums import ContentRuleType, UserRole
from app.models import ContentRule, Persona, Store, User

logger = get_logger("seed")


async def seed() -> None:
    async with AsyncSessionFactory() as db:
        # ---- Admin ----
        existing = await db.execute(select(User).where(User.email == settings.FIRST_ADMIN_EMAIL))
        if existing.scalar_one_or_none() is None:
            db.add(
                User(
                    email=settings.FIRST_ADMIN_EMAIL,
                    full_name="Administrator",
                    role=UserRole.ADMIN,
                    hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                )
            )
            logger.info("Created admin %s", settings.FIRST_ADMIN_EMAIL)

        # ---- Powerful Trade Center stores (buyersbox.co.jp format) ----
        pawatore_stores = [
            {
                "name": "パワフルトレードセンター 豊平店",
                "code": "toyohira",
                "address": "北海道札幌市豊平区豊平3条9丁目3-10 エムズ豊平１F",
                "article_config": {"label": "豊平", "area": "札幌市豊平区"},
            },
            {
                "name": "パワフルトレードセンター 東苗穂店",
                "code": "naebo",
                "address": "北海道札幌市東区東苗穂3条1丁目3-45 コスモロイヤル東苗穂A棟 1F",
                "article_config": {"label": "東苗穂", "area": "札幌市東区"},
            },
            {
                "name": "パワフルトレードセンター 東米里店",
                "code": "yonesato",
                "address": "北海道札幌市白石区東米里2090-170",
                "article_config": {"label": "東米里", "area": "札幌市白石区"},
            },
        ]
        for data in pawatore_stores:
            exists = await db.execute(select(Store).where(Store.code == data["code"]))
            if exists.scalar_one_or_none() is None:
                db.add(Store(**data))
                logger.info("Created store %s", data["name"])

        # ---- Personas (buyersbox EXPERIENCE styles) ----
        personas_to_seed = [
            {
                "name": "パワトレギャル",
                "description": "明るい女性スタッフ口調の買取報告。EXPERIENCE最も典型的な文体。",
                "tone": "明るくフレンドリー、絵文字は段落あたり1〜2個",
                "writing_style": "短文です・ます。自虐・妄想コメント＋地域SEO＋ソフトCTA。",
                "system_prompt": (
                    "冒頭は『こんにちは～🙋‍♀️パワトレギャルです💕』。"
                    "商品名と型番は入力どおり正確に。価格や保証は書かない。"
                ),
            },
            {
                "name": "パワトレおじさん",
                "description": "温厚な男性スタッフ口調。電線・工具ネタ向き。",
                "tone": "落ち着きつつ親しみやすい。過剰な甘さは避ける。",
                "writing_style": "見た目・触感の一言コメント。勧誘は押し売りにしない。",
                "system_prompt": (
                    "冒頭は『どうも、パワトレおじさんです👨』。"
                    "電線カテゴリではVCTF/VVFなどの呼称を正確に。"
                ),
            },
            {
                "name": "買取速報",
                "description": "自己紹介なしのテンポ良い買取速報スタイル。",
                "tone": "端的・テンポ重視",
                "writing_style": "商品名太字→【買取速報】→報告→短コメント→来店促し。",
                "system_prompt": (
                    "自己紹介は書かない。先頭は商品名の太字行から。"
                    "『🚗【買取速報】…より！』を使う。"
                ),
            },
        ]
        for pdata in personas_to_seed:
            exists = await db.execute(
                select(Persona).where(Persona.name == pdata["name"], Persona.store_id.is_(None))
            )
            if exists.scalar_one_or_none() is None:
                db.add(Persona(**pdata))
                logger.info("Created persona %s", pdata["name"])
            else:
                # Refresh tone/prompts so style updates apply to existing installs.
                row = (
                    await db.execute(
                        select(Persona).where(
                            Persona.name == pdata["name"], Persona.store_id.is_(None)
                        )
                    )
                ).scalar_one()
                for k, v in pdata.items():
                    setattr(row, k, v)
                logger.info("Updated persona %s", pdata["name"])

        # ---- Common brand rules ----
        rule_result = await db.execute(select(ContentRule).limit(1))
        if rule_result.scalar_one_or_none() is None:
            db.add_all(
                [
                    ContentRule(rule_type=ContentRuleType.PROHIBITED_WORD, value="最安値"),
                    ContentRule(rule_type=ContentRuleType.PROHIBITED_WORD, value="絶対"),
                    ContentRule(
                        rule_type=ContentRuleType.PROHIBITED_CONTEXT,
                        value="医療効果",
                        note="Do not claim medical benefits.",
                    ),
                    ContentRule(
                        rule_type=ContentRuleType.BRAND_RULE,
                        value="Always mention the item can be sold/bought at our store.",
                    ),
                    ContentRule(
                        rule_type=ContentRuleType.STRUCTURE,
                        value="Include an introduction, product features and a call to action.",
                    ),
                ]
            )
            logger.info("Created default content rules")

        await db.commit()
    await engine.dispose()
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
