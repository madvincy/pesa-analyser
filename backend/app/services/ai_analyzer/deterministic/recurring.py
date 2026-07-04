# recurring.py - Auto-generated file
# Add content here
"""
Recurring payment detection.
"""

import logging
from collections import defaultdict
from typing import List, Dict, Any
from statistics import mean, stdev

from ..utils import normalize_transaction, get_tx_amount
from ..models import CategoryBreakdown

logger = logging.getLogger(__name__)


class RecurringAnalyzer:
    """Detect recurring payments."""

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect recurring payments based on description and amount consistency."""
        if not transactions:
            return []

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        classified = [self._classify_transaction(tx) for tx in norm_txs]

        groups: Dict[str, List[float]] = defaultdict(list)

        for tx, cls in zip(norm_txs, classified):
            if cls["direction"] != "out":
                continue

            desc = (tx.get("description") or "")[:40].strip()
            amount = get_tx_amount(tx)
            if amount > 0:
                groups[desc].append(amount)

        recurring = []
        for desc, amounts in groups.items():
            if len(amounts) < 2:
                continue

            avg = mean(amounts)
            cv = stdev(amounts) / avg if len(amounts) > 1 and avg > 0 else 0

            if cv < 0.15:  # Low coefficient of variation means consistent
                recurring.append(
                    {
                        "description": desc,
                        "average_amount": round(avg, 2),
                        "occurrences": len(amounts),
                        "total": round(sum(amounts), 2),
                    }
                )

        return sorted(recurring, key=lambda x: x["total"], reverse=True)[:10]

    def _classify_transaction(self, tx: Dict[str, Any]) -> Dict[str, str]:
        """Simple classification for recurring detection."""
        from ..patterns import CATEGORY_RULES
        import re

        description = (tx.get("description") or "").lower()

        for pattern, category, subcategory, direction in CATEGORY_RULES:
            if re.search(pattern, description):
                return {
                    "category": category,
                    "subcategory": subcategory,
                    "direction": direction,
                }

        tx_type = tx.get("type", "unknown")
        direction = "in" if tx_type == "income" else "out"
        return {"category": "other", "subcategory": "other", "direction": direction}
