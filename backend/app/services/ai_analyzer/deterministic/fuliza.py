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
        """Detect Fuliza drawdown → repayment cycles."""

        if not transactions:
            return self._empty_cycle()

        norm_txs = [normalize_transaction(tx) for tx in transactions]

        # Transactions funded using Fuliza
        drawdowns = [tx for tx in norm_txs if tx.get("fuliza_used") is True]

        # Transactions that repay Fuliza
        repayments = [tx for tx in norm_txs if tx.get("fuliza_repayment") is True]

        logger.info(
            "Fuliza drawdowns=%d repayments=%d",
            len(drawdowns),
            len(repayments),
        )

        total_drawn = sum(
            tx.get("fuliza_amount", get_tx_amount(tx)) for tx in drawdowns
        )

        total_repaid = sum(get_tx_amount(tx) for tx in repayments)

        cycle_count = len(repayments)

        same_day_cycles = 0

        for repayment in repayments:
            repayment_date = repayment.get("date")

            if any(drawdown.get("date") == repayment_date for drawdown in drawdowns):
                same_day_cycles += 1

        logger.info(
            "Fuliza totals: drawn=%.2f repaid=%.2f cycles=%d same_day=%d",
            total_drawn,
            total_repaid,
            cycle_count,
            same_day_cycles,
        )

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
            "interpretation": self._get_interpretation(
                same_day_cycles,
                cycle_count,
            ),
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
