"""
Transaction categorization engine.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

from .patterns import CATEGORY_RULES, KNOWN_PAYBILLS, PHONE_PATTERNS

logger = logging.getLogger(__name__)


class Categorizer:
    """Categorize transactions based on rules and patterns."""

    def __init__(self):
        self.category_rules = CATEGORY_RULES
        self.known_paybills = KNOWN_PAYBILLS
        self.phone_patterns = PHONE_PATTERNS

    def categorize(self, transaction: Dict[str, Any]) -> Dict[str, str]:
        """
        Categorize a single transaction.

        Returns:
            Dict with 'category', 'subcategory', 'direction'
        """
        description = (transaction.get("description") or "").lower()

        for pattern, category, subcategory, direction in self.category_rules:
            if re.search(pattern, description):
                return {
                    "category": category,
                    "subcategory": subcategory,
                    "direction": direction,
                }

        # Default based on transaction type
        direction = "in" if transaction.get("type") == "income" else "out"
        return {
            "category": "other",
            "subcategory": "other",
            "direction": direction,
        }

    def categorize_batch(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Categorize multiple transactions."""
        return [self.categorize(tx) for tx in transactions]

    def get_paybill_merchant(self, paybill: str) -> Optional[Dict[str, str]]:
        """Get merchant info for a paybill number."""
        if paybill in self.known_paybills:
            name, category, subcategory = self.known_paybills[paybill]
            return {
                "name": name,
                "category": category,
                "subcategory": subcategory,
            }
        return None

    def extract_merchant_from_description(self, description: str) -> Optional[str]:
        """Extract merchant name from description."""
        patterns = [
            r"to\s+(\d+)\s*[-–]\s*([A-Za-z\s]+)",
            r"to\s+([A-Za-z\s]+)",
            r"at\s+([A-Za-z\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                groups = match.groups()
                return groups[-1].strip() if groups else None

        return None

    def classify_income_source(self, description: str) -> str:
        """Classify the source of income."""
        desc_lower = description.lower()

        if "salary" in desc_lower:
            return "salary"
        elif any(
            bank in desc_lower for bank in ["kcb", "equity", "ncba", "stanbic", "absa"]
        ):
            return "bank_transfer"
        elif "business" in desc_lower or "payment from" in desc_lower:
            return "business"
        elif "funds received from" in desc_lower:
            return "peer_transfer"
        elif "deposit" in desc_lower:
            return "deposit"
        elif "loan" in desc_lower or "fuliza" in desc_lower:
            return "loan"
        else:
            return "other"

    def get_category_breakdown(
        self, transactions: List[Dict[str, Any]], classified: List[Dict[str, str]]
    ) -> Dict[str, float]:
        """Get category breakdown totals."""
        breakdown = {}

        for tx, cls in zip(transactions, classified):
            category = cls["category"]
            amount = abs(float(tx.get("amount", 0) or 0))
            breakdown[category] = breakdown.get(category, 0) + amount

        return breakdown

    def get_merchant_breakdown(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Get merchant breakdown totals."""
        merchant_totals = {}

        for tx in transactions:
            if tx.get("type") != "expense":
                continue

            description = tx.get("description", "")
            merchant = self.extract_merchant_from_description(description)

            if merchant:
                amount = abs(float(tx.get("amount", 0) or 0))
                merchant_totals[merchant] = merchant_totals.get(merchant, 0) + amount

        return dict(sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True))
