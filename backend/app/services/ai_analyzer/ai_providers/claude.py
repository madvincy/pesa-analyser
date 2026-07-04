"""
Anthropic Claude AI Provider.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
    """Anthropic Claude implementation."""

    async def analyze(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Analyze with Anthropic Claude."""
        try:
            import anthropic
        except ImportError:
            logger.warning("⚠️ Anthropic library not installed")
            return None

        full_prompt = self._build_prompt(
            transactions, statement_type, deterministic, prompt
        )

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": full_prompt}],
            )

            # Extract text from response
            response_text = self._extract_text(response)

            if response_text is None:
                logger.error("No text content in Claude response")
                return None

            return self._parse_json_response(response_text)

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return None

    def _extract_text(self, response) -> Optional[str]:
        """
        Extract text from Claude response.
        Handles both dict and object formats.
        """
        try:
            # If response is a dict
            if isinstance(response, dict):
                content = response.get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    block = content[0]
                    if isinstance(block, dict):
                        # Try common text fields
                        for key in ["text", "thinking", "data"]:
                            if key in block:
                                value = block[key]
                                if isinstance(value, str):
                                    return value
                                elif isinstance(value, dict) and "text" in value:
                                    return value["text"]
                        return str(block)
                    elif hasattr(block, "text"):
                        return block.text
                    elif hasattr(block, "thinking"):
                        return block.thinking
                    return str(block)
                return str(response)

            # If response has content attribute (object)
            if hasattr(response, "content"):
                content = response.content
                if content and len(content) > 0:
                    block = content[0]
                    # Try text attribute first
                    if hasattr(block, "text") and block.text:
                        return block.text
                    if hasattr(block, "thinking") and block.thinking:
                        return block.thinking
                    if hasattr(block, "data") and block.data:
                        return block.data
                    # If block is a dict
                    if isinstance(block, dict):
                        for key in ["text", "thinking", "data"]:
                            if key in block:
                                return str(block[key])
                    return str(block)
                return str(response.content)

            # Final fallback
            return str(response)

        except Exception as e:
            logger.error(f"Error extracting text from Claude response: {e}")
            return None
