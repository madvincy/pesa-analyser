"""
Base AI Provider class and factory.
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Base class for AI providers."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def analyze(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Analyze transactions using the AI provider."""
        pass

    def _build_prompt(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Build the full prompt for AI analysis."""
        summary = {
            "statement_type": statement_type,
            "total_transactions": deterministic.get("total_transactions", 0),
            "total_income": deterministic.get("total_income", 0),
            "total_expenses": deterministic.get("total_expenses", 0),
            "net_cash_flow": deterministic.get("net_cash_flow", 0),
            "savings_rate": deterministic.get("savings_rate", 0),
            "health_score": deterministic.get("health_score", 0),
            "top_categories": deterministic.get("category_data", [])[:6],
            "fuliza_count": deterministic.get("fuliza_count", 0),
            "fuliza_total": deterministic.get("fuliza_total", 0),
            "betting_total": deterministic.get("betting_total", 0),
            "betting_pct": deterministic.get("betting_pct", 0),
            "recurring": deterministic.get("recurring_payments", [])[:5],
            "sample_transactions": self._prepare_sample_data(transactions),
        }

        return (
            prompt_template
            + f"\n\nPre-computed data:\n{json.dumps(summary, indent=2, default=str)}"
        )

    def _prepare_sample_data(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prepare sample transaction data for AI prompt."""
        samples = []
        for tx in transactions[:50]:
            samples.append(
                {
                    "date": str(tx.get("date", "")),
                    "description": str(tx.get("description", ""))[:80],
                    "amount": float(tx.get("amount", 0) or 0),
                    "type": str(tx.get("type", "unknown")),
                    "balance": float(tx.get("balance", 0) or 0),
                }
            )
        return samples

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from AI response, handling markdown code blocks."""
        if not text:
            logger.warning("Empty response received from AI provider")
            return {}

        try:
            clean = re.sub(r"```json\s*", "", text)
            clean = re.sub(r"```\s*", "", clean).strip()

            if not clean:
                logger.warning("No JSON content found in AI response")
                return {}

            # Try to find JSON if there's extra text around it
            json_match = re.search(r"\{.*\}", clean, re.DOTALL)
            if json_match:
                clean = json_match.group(0)

            return json.loads(clean)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON response: {e}")
            return {}


class AIProviderFactory:
    """Factory for creating AI provider instances with graceful failure."""

    def __init__(self):
        import os

        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.claude_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-20241022")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.deepseek_base_url = "https://api.deepseek.com/v1"

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """
        Get an AI provider instance by name.

        Returns None if the provider is not available or fails to initialize.
        """
        try:
            if name == "gemini" and self.gemini_api_key:
                from .gemini import GeminiProvider

                return GeminiProvider(self.gemini_api_key, self.gemini_model)

            elif name == "claude" and self.claude_api_key:
                from .claude import ClaudeProvider

                return ClaudeProvider(self.claude_api_key, self.claude_model)

            elif name == "deepseek" and self.deepseek_api_key:
                from .deepseek import DeepSeekProvider

                return DeepSeekProvider(
                    self.deepseek_api_key, self.deepseek_model, self.deepseek_base_url
                )

            elif name == "openai" and self.openai_api_key:
                from .openai import OpenAIProvider

                return OpenAIProvider(self.openai_api_key, self.openai_model)

            else:
                if not self._has_valid_api_key(name):
                    logger.info(f"ℹ️ {name.capitalize()} API key not configured")
                return None

        except ImportError as e:
            logger.warning(f"⚠️ Could not import {name} provider: {e}")
            logger.info(f"ℹ️ Install required package for {name} provider")
            return None

        except Exception as e:
            logger.warning(f"⚠️ Could not initialize {name} provider: {e}")
            return None

    def _has_valid_api_key(self, name: str) -> bool:
        """Check if the provider has a valid API key."""
        key_map = {
            "gemini": self.gemini_api_key,
            "claude": self.claude_api_key,
            "deepseek": self.deepseek_api_key,
            "openai": self.openai_api_key,
        }
        key = key_map.get(name, "")
        return bool(key and not key.startswith("your_"))

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        providers = []
        for name in ["gemini", "claude", "deepseek", "openai"]:
            if self._has_valid_api_key(name):
                providers.append(name)
        return providers
