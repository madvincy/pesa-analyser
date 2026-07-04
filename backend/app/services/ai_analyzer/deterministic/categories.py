"""
Category analysis for transactions.
"""

import re
import logging
from collections import defaultdict
from typing import List, Dict, Any, DefaultDict, Optional
from datetime import datetime

from ..models import CategoryBreakdown, MonthlyData
from ..patterns import CATEGORY_RULES
from ..utils import normalize_transaction, get_tx_type, get_tx_amount

logger = logging.getLogger(__name__)


class CategoryAnalyzer:
    """Analyze transaction categories."""

    def __init__(self):
        self.category_rules = CATEGORY_RULES

    def analyze(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze categories from transactions."""
        if not transactions:
            return self._empty_result()

        # Normalize transactions
        norm_txs = [normalize_transaction(tx) for tx in transactions]

        categories: DefaultDict[str, float] = defaultdict(float)
        classified = [self._classify_transaction(tx) for tx in norm_txs]

        for tx, cls in zip(norm_txs, classified):
            amount = get_tx_amount(tx)
            if amount > 0:
                categories[cls["category"]] += amount

        # Build category data
        category_data = sorted(
            [{"name": k, "value": round(v, 2)} for k, v in categories.items()],
            key=lambda x: x["value"],
            reverse=True,
        )

        top_category = category_data[0]["name"] if category_data else "N/A"
        top_category_amount = category_data[0]["value"] if category_data else 0.0

        total_expenses = sum(
            v for k, v in categories.items() if k not in ["income", "transfer"]
        )
        top_category_pct = (
            (top_category_amount / total_expenses * 100) if total_expenses else 0.0
        )

        return {
            "category_data": category_data,
            "top_category": top_category,
            "top_category_amount": round(top_category_amount, 2),
            "top_category_percent": round(top_category_pct, 2),
        }

    def _classify_transaction(self, tx: Dict[str, Any]) -> Dict[str, str]:
        """Classify a single transaction using category rules."""
        description = (tx.get("description") or "").lower()

        for pattern, category, subcategory, direction in self.category_rules:
            if re.search(pattern, description):
                return {
                    "category": category,
                    "subcategory": subcategory,
                    "direction": direction,
                }

        tx_type = get_tx_type(tx)
        direction = "in" if tx_type == "income" else "out"
        return {"category": "other", "subcategory": "other", "direction": direction}

    def get_monthly_breakdown(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get monthly breakdown of transactions."""
        if not transactions:
            return []

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        classified = [self._classify_transaction(tx) for tx in norm_txs]

        months: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"income": 0.0, "expenses": 0.0, "transaction_count": 0}
        )

        for tx, cls in zip(norm_txs, classified):
            raw_date = str(tx.get("date", ""))
            month = raw_date[:7] if len(raw_date) >= 7 else "unknown"
            amount = get_tx_amount(tx)

            months[month]["transaction_count"] += 1
            if cls["direction"] == "in":
                months[month]["income"] += amount
            else:
                months[month]["expenses"] += amount

        result = []
        for month, data in sorted(months.items()):
            result.append(
                {
                    "month": month,
                    "income": round(data["income"], 2),
                    "expenses": round(data["expenses"], 2),
                    "balance": round(data["income"] - data["expenses"], 2),
                    "transaction_count": data["transaction_count"],
                }
            )

        return result

    def get_day_of_week_spend(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calculate spending by day of week."""
        if not transactions:
            return []

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        classified = [self._classify_transaction(tx) for tx in norm_txs]

        dow: Dict[int, float] = defaultdict(float)
        dow_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for tx, cls in zip(norm_txs, classified):
            if cls["direction"] != "out":
                continue

            raw = str(tx.get("date", ""))
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    d = datetime.strptime(raw, fmt)
                    dow[d.weekday()] += get_tx_amount(tx)
                    break
                except ValueError:
                    continue

        return [
            {"day": dow_names[i], "spend": round(dow.get(i, 0.0), 2)} for i in range(7)
        ]

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "category_data": [],
            "top_category": "N/A",
            "top_category_amount": 0,
            "top_category_percent": 0,
        }
