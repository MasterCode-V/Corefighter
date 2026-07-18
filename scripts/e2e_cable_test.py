"""E2E test with the two cable product images."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ASSETS = Path(r"C:\Users\Administrator\.cursor\projects\e-Task-Space-cw1\assets")
IMG1 = ASSETS / "c__Users_Administrator_AppData_Roaming_Cursor_User_workspaceStorage_46845d0aaae0486553a0cb5e203f7a34_images_IMG_7023-480x640-1c924678-be0c-4951-9128-29d65b56630d.png"
IMG2 = ASSETS / "c__Users_Administrator_AppData_Roaming_Cursor_User_workspaceStorage_46845d0aaae0486553a0cb5e203f7a34_images_20241108_083612-e1731488972960-640x640-aff4a123-3f95-48f5-9ac9-61c227b96a5c.png"


async def poll(client: httpx.AsyncClient, headers: dict, job_id: str, label: str) -> dict:
    for _ in range(90):
        r = await client.get(f"{BASE}/jobs/{job_id}", headers=headers)
        job = r.json()
        print(f"{label}: {job['status']} attempts={job.get('attempts')}")
        if job["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            if job["status"] == "FAILED":
                print("ERROR:", job.get("error"))
            return job
        await asyncio.sleep(2)
    raise TimeoutError(label)


async def main() -> None:
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(
            f"{BASE}/auth/login",
            data={"username": "admin@corefighter.local", "password": "admin12345"},
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("LOGIN OK")

        stores = (await client.get(f"{BASE}/stores", headers=headers)).json()
        personas = (await client.get(f"{BASE}/personas", headers=headers)).json()
        store = next((s for s in stores if s.get("code") == "naebo"), stores[0])
        persona = next((p for p in personas if "おじさん" in p.get("name", "")), None)
        print("STORE", store["name"], store["code"])
        print("PERSONA", persona["name"] if persona else None)

        purchase = (
            await client.post(
                f"{BASE}/purchases",
                headers=headers,
                json={
                    "store_id": store["id"],
                    "persona_id": persona["id"] if persona else None,
                    "purchase_date": "7/16",
                    "purchase_method": "店頭",
                    "quantity": 1,
                    "quantity_unit": "巻",
                },
            )
        ).json()
        print("PURCHASE", purchase["id"])

        for path, image_type, order in ((IMG1, "ARTICLE", 0), (IMG2, "DETAIL", 1)):
            if not path.exists():
                raise FileNotFoundError(path)
            files = {"file": (path.name, path.read_bytes(), "image/png")}
            data = {"image_type": image_type, "sort_order": str(order)}
            up = await client.post(
                f"{BASE}/purchases/{purchase['id']}/images",
                headers=headers,
                files=files,
                data=data,
            )
            up.raise_for_status()
            print("UPLOADED", image_type, path.name)

        analyze = await client.post(
            f"{BASE}/purchases/{purchase['id']}/analyze", headers=headers
        )
        analyze.raise_for_status()
        job = await poll(client, headers, analyze.json()["job_id"], "ANALYZE")
        if job["status"] != "COMPLETED":
            return

        purchase2 = (
            await client.get(f"{BASE}/purchases/{purchase['id']}", headers=headers)
        ).json()
        print(
            "EXTRACTED",
            json.dumps(
                {
                    "manufacturer": purchase2.get("manufacturer"),
                    "product_name": purchase2.get("product_name"),
                    "model_number": purchase2.get("model_number"),
                    "category": purchase2.get("category"),
                    "condition": purchase2.get("condition"),
                    "characteristics": purchase2.get("characteristics"),
                    "ai_extraction": purchase2.get("ai_extraction"),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        generate = await client.post(
            f"{BASE}/purchases/{purchase['id']}/generate", headers=headers
        )
        generate.raise_for_status()
        job2 = await poll(client, headers, generate.json()["job_id"], "GENERATE")
        if job2["status"] != "COMPLETED":
            return

        article = None
        for _ in range(40):
            articles = (
                await client.get(f"{BASE}/articles?limit=30", headers=headers)
            ).json()
            article = next(
                (a for a in articles if a["purchase_id"] == purchase["id"]), None
            )
            if article and article.get("current_version") and article["current_version"].get("title"):
                article = (
                    await client.get(f"{BASE}/articles/{article['id']}", headers=headers)
                ).json()
                break
            await asyncio.sleep(2)

        if not article:
            print("NO ARTICLE FOUND")
            return

        version = article["current_version"]
        print("ARTICLE_STATUS", article["status"])
        print("TITLE", version.get("title"))
        print("BODY_PREVIEW")
        print((version.get("body") or "")[:500])
        print("RENDERED_LEN", len(version.get("rendered_html") or ""))
        print("VALIDATION", version.get("validation_outcome"))
        print("SIMILARITY", article.get("latest_similarity_score"))
        print("TEST OK")


if __name__ == "__main__":
    asyncio.run(main())
