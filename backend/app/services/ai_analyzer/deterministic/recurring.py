"""
Recurring payment detection.
"""

import logging
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List

from ..utils import (
    normalize_transaction,
    get_tx_amount,
    get_tx_type,
)

logger = logging.getLogger(__name__)


class RecurringAnalyzer:
    """Detect recurring merchant and bill payments."""

    MIN_OCCURRENCES = 2
    AMOUNT_VARIATION = 0.20  # 20%

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect recurring outgoing payments."""

        if not transactions:
            return []

        txs = [normalize_transaction(tx) for tx in transactions]

        groups = defaultdict(list)

        for tx in txs:
            if not self._is_outgoing(tx):
                continue

            key = self._group_key(tx)

            if key is None:
                continue

            groups[key].append(tx)

        recurring = []

        for key, items in groups.items():

            if len(items) < self.MIN_OCCURRENCES:
                continue

            amounts = [get_tx_amount(i) for i in items]

            avg = mean(amounts)

            if avg == 0:
                continue

            variation = (max(amounts) - min(amounts)) / avg

            if variation > self.AMOUNT_VARIATION:
                continue

            dates = []

            for item in items:
                dt = self._parse_date(item.get("date"))
                if dt is not None:
                    dates.append(dt)

            dates.sort()

            frequency = self._detect_frequency(dates)

            # ✅ FIX: Use "description" instead of "name" for consistency
            recurring.append(
                {
                    "description": key,  # Changed from "name" to "description"
                    "average_amount": round(avg, 2),
                    "total": round(sum(amounts), 2),
                    "occurrences": len(items),
                    "frequency": frequency,
                    "first_payment": items[0].get("date"),
                    "last_payment": items[-1].get("date"),
                }
            )

        recurring.sort(
            key=lambda x: (x["occurrences"], x["total"]),
            reverse=True,
        )

        return recurring[:10]

    # -------------------------------------------------------------

    def _is_outgoing(self, tx: Dict[str, Any]) -> bool:
        """Determine whether transaction is an outgoing payment."""

        direction = tx.get("direction")

        if direction:
            return direction == "out"

        return get_tx_type(tx) != "income"

    # -------------------------------------------------------------

    def _group_key(self, tx: Dict[str, Any]) -> str | None:
        """
        Group using structured fields instead of descriptions.
        """

        tx_type = (tx.get("transaction_type") or "").lower()

        # Ignore person-to-person transfers

        if tx_type.startswith("customer_transfer"):
            return None

        if tx_type.startswith("customer_send_money"):
            return None

        if tx_type.startswith("sent"):
            return None

        if tx_type.startswith("funds_received"):
            return None

        # Merchant

        if tx.get("merchant_name"):
            return f"Merchant: {tx['merchant_name']}"

        # Paybill

        if tx.get("paybill_number"):
            name = tx.get("merchant_name") or tx["paybill_number"]
            return f"Paybill: {name}"

        # Till

        if tx.get("till_number"):
            name = tx.get("merchant_name") or tx["till_number"]
            return f"Till: {name}"

        # Utility / airtime

        category = (tx.get("category") or "").lower()

        if category:
            return category.title()

        # Description fallback

        description = tx.get("description", "").strip()

        if len(description) > 80:
            description = description[:80]

        return description if description else None

    # -------------------------------------------------------------

    def _parse_date(self, value):

        if not value:
            return None

        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                pass

        return None

    # -------------------------------------------------------------

    def _detect_frequency(self, dates):

        if len(dates) < 2:
            return "unknown"

        gaps = []

        for i in range(1, len(dates)):
            gaps.append((dates[i] - dates[i - 1]).days)

        avg_gap = mean(gaps)

        if 26 <= avg_gap <= 34:
            return "monthly"

        if 13 <= avg_gap <= 17:
            return "fortnightly"

        if 6 <= avg_gap <= 8:
            return "weekly"

        if 1 <= avg_gap <= 2:
            return "daily"

        return "irregular"
