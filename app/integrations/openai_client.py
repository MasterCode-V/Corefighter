"""OpenAI integration: image analysis, article generation and embeddings.

All responses that must be structured are requested as JSON and parsed
defensively so a malformed model response surfaces as a job failure/retry
rather than corrupting the database.
"""
from __future__ import annotations

import base64
import json
from typing import Any, List, Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ------------------------------------------------------------------
    # Image analysis (workflow 4)
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def analyze_images(
        self,
        images: List[bytes],
        content_types: List[str],
        hint: Optional[str] = None,
    ) -> dict:
        """Extract structured product information from product images."""
        system = (
            "You are a product cataloguing assistant for a Japanese second-hand "
            "goods store. Analyse the provided product photographs and extract "
            "structured product information. Respond ONLY with JSON."
        )
        instruction = (
            "Extract the following fields. Use null when unknown. Respond as JSON with keys: "
            "manufacturer, product_name, model_number, category, condition, "
            "characteristics (array of short strings). "
        )
        if hint:
            instruction += f"\nAdditional context from staff: {hint}"

        content: List[dict[str, Any]] = [{"type": "text", "text": instruction}]
        for data, ctype in zip(images, content_types):
            b64 = base64.b64encode(data).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{ctype or 'image/jpeg'};base64,{b64}"},
                }
            )

        response = await self._client.chat.completions.create(
            model=settings.OPENAI_VISION_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return _parse_json(response.choices[0].message.content)

    # ------------------------------------------------------------------
    # Article generation (workflows 5 & 8)
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_article(self, system_prompt: str, user_prompt: str) -> dict:
        """Generate buyersbox-style article body JSON.

        Temperature is kept moderate so structure matches live EXPERIENCE
        articles while still allowing persona flavour.
        """
        response = await self._client.chat.completions.create(
            model=settings.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            top_p=settings.OPENAI_TOP_P,
            frequency_penalty=settings.OPENAI_FREQUENCY_PENALTY,
            presence_penalty=settings.OPENAI_PRESENCE_PENALTY,
        )
        return _parse_json(response.choices[0].message.content)

    # ------------------------------------------------------------------
    # Embeddings (workflows 7 & 15)
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]


def _parse_json(raw: Optional[str]) -> dict:
    if not raw:
        raise ValueError("Empty response from OpenAI")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start : end + 1])
        raise


openai_client = OpenAIClient()
