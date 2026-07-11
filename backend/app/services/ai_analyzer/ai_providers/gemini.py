"""
Google Gemini AI Provider.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini implementation."""

    async def analyze(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Analyze with Google Gemini."""
        GEMINI_MODELS = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-8b",
        ]

        if self.model and self.model in GEMINI_MODELS:
            GEMINI_MODELS = [self.model] + [m for m in GEMINI_MODELS if m != self.model]

        full_prompt = self._build_prompt(
            transactions, statement_type, deterministic, prompt
        )

        # ─── Try google.genai first (newer API) ──────────────────────────────
        try:
            import google.genai as genai

            client = genai.Client(api_key=self.api_key)

            for model_name in GEMINI_MODELS:
                try:
                    logger.info(f"🔍 Trying Gemini model (genai): {model_name}")
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=full_prompt,
                    )
                    response_text = getattr(response, "text", None)
                    if response_text:
                        logger.info(f"✅ Gemini {model_name} succeeded")
                        parsed = self._parse_json_response(response_text)
                        if parsed:
                            return parsed
                        else:
                            logger.warning(f"⚠️ Failed to parse Gemini response")
                            continue
                except Exception as e:
                    error_msg = str(e).lower()
                    if "404" in error_msg or "not found" in error_msg:
                        logger.warning(f"⚠️ Model {model_name} not found, trying next")
                        continue
                    elif "api_key" in error_msg or "authentication" in error_msg:
                        logger.warning(f"⚠️ Authentication failed for Gemini: {e}")
                        return None
                    else:
                        logger.warning(f"⚠️ Gemini {model_name} failed: {e}")
                        continue

        except ImportError:
            logger.debug("google.genai not available, trying google.generativeai")
        except Exception as e:
            logger.warning(f"⚠️ google.genai failed: {e}")

        # ─── Fallback to google.generativeai (older API) ──────────────────────
        try:
            import google.generativeai as genai

            # ✅ FIX: Use genai.configure() directly
            genai.configure(api_key=self.api_key)

            for model_name in GEMINI_MODELS:
                try:
                    logger.info(f"🔍 Trying Gemini model (generativeai): {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = await asyncio.to_thread(
                        model.generate_content, full_prompt
                    )

                    response_text = self._extract_response_text(response)
                    if response_text is None:
                        logger.warning(f"Gemini {model_name} returned empty response")
                        continue

                    logger.info(f"✅ Gemini {model_name} succeeded")
                    parsed = self._parse_json_response(response_text)
                    if parsed:
                        return parsed
                    else:
                        logger.warning(f"⚠️ Failed to parse Gemini response")
                        continue

                except Exception as e:
                    error_msg = str(e).lower()
                    if "404" in error_msg or "not found" in error_msg:
                        logger.warning(f"⚠️ Model {model_name} not found, trying next")
                        continue
                    elif "api_key" in error_msg or "authentication" in error_msg:
                        logger.warning(f"⚠️ Authentication failed for Gemini: {e}")
                        return None
                    else:
                        logger.warning(f"⚠️ Gemini {model_name} failed: {e}")
                        continue

        except ImportError:
            logger.debug("google.generativeai not available")
        except Exception as e:
            logger.warning(f"⚠️ google.generativeai failed: {e}")

        return None

    def _extract_response_text(self, response) -> Optional[str]:
        """Extract text from Gemini response."""
        if not response:
            return None

        if hasattr(response, "text") and response.text:
            return response.text

        if hasattr(response, "result") and response.result:
            if hasattr(response.result, "text"):
                return response.result.text
            return str(response.result)

        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                return part.text

        return str(response)
