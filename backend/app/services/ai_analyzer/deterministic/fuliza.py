"""
Fuliza cycle detection and analysis.
"""

import logging
from typing import List, Dict, Any

from ..models import FulizaCycle
from ..utils import normalize_transaction, get_tx_amount

logger = logging.getLogger(__name__)


class FulizaAnalyzer:
    """Detect and analyze Fuliza cycles."""

    def detect_cycles(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect Fuliza drawdown→repayment cycles."""
        if not transactions:
            return self._empty_cycle()

        norm_txs = [normalize_transaction(tx) for tx in transactions]

        fuliza_legs = [t for t in norm_txs if t.get("fuliza")]
        repayments = [
            t
            for t in norm_txs
            if "od loan repayment" in t.get("description", "").lower()
        ]

        total_drawn = sum(get_tx_amount(t) for t in fuliza_legs)
        total_repaid = sum(get_tx_amount(t) for t in repayments)
        cycle_count = len(repayments)

        same_day_cycles = 0
        for r in repayments:
            r_date = r.get("date", "")
            same_day_drawdowns = [f for f in fuliza_legs if f.get("date") == r_date]
            if same_day_drawdowns:
                same_day_cycles += 1

        return {
            "total_fuliza_drawn": round(total_drawn, 2),
            "total_repaid": round(total_repaid, 2),
            "cycle_count": cycle_count,
            "same_day_repayment_rate": (
                round(same_day_cycles / cycle_count * 100, 1) if cycle_count else 0
            ),
            "avg_cycle_amount": (
                round(total_drawn / cycle_count, 2) if cycle_count else 0
            ),
            "interpretation": self._get_interpretation(same_day_cycles, cycle_count),
        }

    def _get_interpretation(self, same_day_cycles: int, cycle_count: int) -> str:
        """Get interpretation of Fuliza usage."""
        if cycle_count == 0:
            return "No Fuliza usage detected"

        rate = same_day_cycles / max(cycle_count, 1)
        if rate > 0.7:
            return "Severe Fuliza dependency — same-day repayment cycles"
        elif rate > 0.3:
            return "Moderate Fuliza usage"
        else:
            return "Low Fuliza usage"

    def _empty_cycle(self) -> Dict[str, Any]:
        return {
            "total_fuliza_drawn": 0,
            "total_repaid": 0,
            "cycle_count": 0,
            "same_day_repayment_rate": 0,
            "avg_cycle_amount": 0,
            "interpretation": "No Fuliza usage detected",
        }
