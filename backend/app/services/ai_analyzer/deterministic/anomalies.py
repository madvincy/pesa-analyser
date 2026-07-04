"""
Anomaly detection for transactions.
"""

import logging
from typing import List, Dict, Any
from statistics import mean, stdev

from ..utils import normalize_transaction, get_tx_amount

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalous transactions."""

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect unusually large transactions (outliers)."""
        if not transactions:
            return []

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        amounts = [get_tx_amount(tx) for tx in norm_txs if get_tx_amount(tx) > 0]

        if len(amounts) < 3:
            return []

        avg = mean(amounts)
        sd = stdev(amounts)
        threshold = avg + 2 * sd

        anomalies = []
        for tx in norm_txs:
            amount = get_tx_amount(tx)
            if amount > threshold:
                anomalies.append(
                    {
                        "date": str(tx.get("date", "")),
                        "description": (tx.get("description") or "")[:60],
                        "amount": round(amount, 2),
                        "reason": f"Amount is {amount/avg:.1f}× the average",
                    }
                )

        return anomalies[:10]
