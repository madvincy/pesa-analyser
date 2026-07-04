"""
OpenAI AI Provider.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI implementation."""

    async def analyze(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Analyze with OpenAI."""
        try:
            import openai
        except ImportError:
            logger.warning("⚠️ OpenAI library not installed")
            return None

        full_prompt = self._build_prompt(
            transactions, statement_type, deterministic, prompt
        )

        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Respond with valid JSON only."},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

            # Extract content and handle None case
            content = response.choices[0].message.content

            # Check if content is None
            if content is None:
                logger.error("OpenAI returned empty response")
                return None

            # Ensure content is a string
            if not isinstance(content, str):
                content = str(content)

            return self._parse_json_response(content)

        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            return None
