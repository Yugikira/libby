"""AI-powered metadata extraction."""

import json
import os

from openai import AsyncOpenAI

from libby.models.config import LibbyConfig


class AIExtractor:
    """Extract DOI/title using LLM."""

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, config: LibbyConfig):
        api_key = config.ai_extractor.api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("AI extractor requires api_key (config or DEEPSEEK_API_KEY)")

        base_url = config.ai_extractor.base_url or self.DEFAULT_BASE_URL
        model = config.ai_extractor.model or self.DEFAULT_MODEL
        max_tokens = config.ai_extractor.max_tokens

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.max_tokens = max_tokens

    async def extract_from_text(self, text: str) -> dict:
        """Extract DOI and title from text."""
        prompt = f"""Extract DOI and title from this academic paper text.
If DOI is split across lines, join it correctly.
Return ONLY valid JSON: {{"doi": "xxx", "title": "xxx"}}
If not found, return: {{"doi": null, "title": null}}

Text (first 2000 chars):
{text[:2000]}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)