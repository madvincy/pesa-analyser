"""
Category analysis for transactions.
"""

import re
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, Dict, List

from ..patterns import CATEGORY_RULES
from ..utils import (
    normalize_transaction,
    get_tx_amount,
    get_tx_type,
)

logger = logging.getLogger(__name__)


class CategoryAnalyzer:
    """Analyze transaction categories."""

    def __init__(self):
        self.category_rules = CATEGORY_RULES

    # ------------------------------------------------------------------ #
    # PUBLIC
    # ------------------------------------------------------------------ #

    def analyze(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not transactions:
            return self._empty_result()

        txs = [normalize_transaction(t) for t in transactions]

        totals: DefaultDict[str, float] = defaultdict(float)

        for tx in txs:

            amount = get_tx_amount(tx)
            if amount <= 0:
                continue

            classification = self._classify_transaction(tx)

            # Category analysis is about MONEY SPENT.
            # Ignore income categories.
            if classification["direction"] == "out":
                totals[classification["category"]] += amount

        category_data = sorted(
            (
                {"name": name, "value": round(value, 2)}
                for name, value in totals.items()
            ),
            key=lambda x: x["value"],
            reverse=True,
        )

        if not category_data:
            return self._empty_result()

        total_spend = sum(i["value"] for i in category_data)

        top = category_data[0]

        return {
            "category_data": category_data,
            "top_category": top["name"],
            "top_category_amount": top["value"],
            "top_category_percent": round(
                top["value"] / total_spend * 100 if total_spend else 0,
                2,
            ),
        }

    # ------------------------------------------------------------------ #
    # CLASSIFICATION
    # ------------------------------------------------------------------ #

    def _classify_transaction(self, tx: Dict[str, Any]) -> Dict[str, str]:

        description = (tx.get("description") or "").lower()
        tx_type = (tx.get("transaction_type") or "").lower()

        direction = tx.get("direction")
        if direction not in ("in", "out"):
            direction = "in" if get_tx_type(tx) == "income" else "out"

        # --------------------------------------------------------------
        # Income
        # --------------------------------------------------------------

        if direction == "in":
            return {
                "category": "income",
                "subcategory": tx_type or "income",
                "direction": "in",
            }

        # --------------------------------------------------------------
        # Transaction type based (preferred)
        # --------------------------------------------------------------

        if "merchant_payment" in tx_type:
            return self._classify_merchant(description)

        if "customer_transfer" in tx_type:
            return {
                "category": "transfer",
                "subcategory": "p2p",
                "direction": "out",
            }

        if "customer_send_money" in tx_type:
            return {
                "category": "transfer",
                "subcategory": "p2p",
                "direction": "out",
            }

        if "paybill" in tx_type:
            return {
                "category": "utilities",
                "subcategory": "paybill",
                "direction": "out",
            }

        if "airtime" in tx_type:
            return {
                "category": "airtime",
                "subcategory": "airtime",
                "direction": "out",
            }

        if "withdraw" in tx_type:
            return {
                "category": "cash",
                "subcategory": "withdrawal",
                "direction": "out",
            }

        if "fuliza_repayment" in tx_type:
            return {
                "category": "loan",
                "subcategory": "fuliza_repayment",
                "direction": "out",
            }

        if "loan_repayment" in tx_type:
            return {
                "category": "loan",
                "subcategory": "loan_repayment",
                "direction": "out",
            }

        # --------------------------------------------------------------
        # Description rules
        # --------------------------------------------------------------

        for pattern, category, subcategory, rule_direction in self.category_rules:

            # Don't classify merchant payments as loans simply because
            # they contain the word Fuliza.
            if category == "loan" and tx.get("fuliza_used"):
                continue

            if re.search(pattern, description):
                return {
                    "category": category,
                    "subcategory": subcategory,
                    "direction": rule_direction,
                }

        return {
            "category": "other",
            "subcategory": "other",
            "direction": direction,
        }

    # ------------------------------------------------------------------ #
    # Merchant classifier
    # ------------------------------------------------------------------ #

    def _classify_merchant(self, description: str):

        desc = description.lower()

        # Food & Restaurants
        if any(
            word in desc
            for word in (
                "restaurant",
                "lounge",
                "hotel",
                "cafe",
                "pizza",
                "burger",
                "kfc",
                "java",
                "chicken",
                "nyama",
                "grill",
            )
        ):
            return {
                "category": "food",
                "subcategory": "dining",
                "direction": "out",
            }

        # Supermarkets
        if any(
            word in desc
            for word in (
                "naivas",
                "quickmart",
                "carrefour",
                "cleanshelf",
                "chandarana",
            )
        ):
            return {
                "category": "food",
                "subcategory": "groceries",
                "direction": "out",
            }

        # Fuel
        if any(
            word in desc
            for word in (
                "shell",
                "total",
                "rubis",
                "ola",
                "petrol",
                "diesel",
                "fuel",
            )
        ):
            return {
                "category": "transport",
                "subcategory": "fuel",
                "direction": "out",
            }

        # Betting
        if any(
            word in desc
            for word in (
                "betika",
                "sportpesa",
                "odibets",
                "shabiki",
                "mcheza",
            )
        ):
            return {
                "category": "betting",
                "subcategory": "betting",
                "direction": "out",
            }

        return {
            "category": "shopping",
            "subcategory": "merchant_payment",
            "direction": "out",
        }

    # ------------------------------------------------------------------ #
    # Monthly
    # ------------------------------------------------------------------ #

    def get_monthly_breakdown(
        self,
        transactions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        txs = [normalize_transaction(t) for t in transactions]

        months = defaultdict(
            lambda: {
                "income": 0.0,
                "expenses": 0.0,
                "transaction_count": 0,
            }
        )

        for tx in txs:

            month = str(tx.get("date", ""))[:7]
            amount = get_tx_amount(tx)

            cls = self._classify_transaction(tx)

            months[month]["transaction_count"] += 1

            if cls["direction"] == "in":
                months[month]["income"] += amount
            else:
                months[month]["expenses"] += amount

        return [
            {
                "month": month,
                "income": round(data["income"], 2),
                "expenses": round(data["expenses"], 2),
                "balance": round(
                    data["income"] - data["expenses"],
                    2,
                ),
                "transaction_count": data["transaction_count"],
            }
            for month, data in sorted(months.items())
        ]

    # ------------------------------------------------------------------ #
    # Day of week
    # ------------------------------------------------------------------ #

    def get_day_of_week_spend(
        self,
        transactions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        txs = [normalize_transaction(t) for t in transactions]

        spend = defaultdict(float)

        names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for tx in txs:

            cls = self._classify_transaction(tx)

            if cls["direction"] != "out":
                continue

            raw = str(tx.get("date", ""))

            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    spend[dt.weekday()] += get_tx_amount(tx)
                    break
                except ValueError:
                    pass

        return [
            {
                "day": names[i],
                "spend": round(spend.get(i, 0), 2),
            }
            for i in range(7)
        ]

    # ------------------------------------------------------------------ #

    def _empty_result(self):

        return {
            "category_data": [],
            "top_category": "N/A",
            "top_category_amount": 0,
            "top_category_percent": 0,
        }
