"""
Health score calculation.
"""

import logging
from typing import Dict, Any, Tuple

from ..models import HealthScore

logger = logging.getLogger(__name__)


class HealthAnalyzer:
    """Calculate financial health score."""

    def calculate(
        self,
        fuliza_cycles: Dict[str, Any],
        income_analysis: Dict[str, Any],
        savings_rate: float,
        betting_pct: float,
        total_transactions: int,
    ) -> Tuple[int, Dict[str, int]]:
        """Calculate enhanced health score."""
        breakdown = {}

        # Fuliza dependency
        same_day_rate = fuliza_cycles.get("same_day_repayment_rate", 0)
        cycle_count = fuliza_cycles.get("cycle_count", 0)

        if same_day_rate > 70:
            breakdown["fuliza_dependency"] = -30
        elif same_day_rate > 40:
            breakdown["fuliza_dependency"] = -15
        elif cycle_count > 0:
            breakdown["fuliza_dependency"] = -5
        else:
            breakdown["fuliza_dependency"] = 15

        # Income quality
        loan_pct = income_analysis.get("loan_as_pct_of_total_inflow", 0)
        if loan_pct > 20:
            breakdown["income_quality"] = -20
        elif loan_pct > 5:
            breakdown["income_quality"] = -5
        else:
            breakdown["income_quality"] = 15

        # Savings rate
        if savings_rate >= 10:
            breakdown["savings_rate"] = 20
        elif savings_rate >= 5:
            breakdown["savings_rate"] = 10
        elif savings_rate >= 0:
            breakdown["savings_rate"] = 0
        else:
            breakdown["savings_rate"] = -10

        # Betting
        if betting_pct == 0:
            breakdown["betting"] = 15
        elif betting_pct < 5:
            breakdown["betting"] = 8
        else:
            breakdown["betting"] = -20

        # Transaction volume
        if total_transactions >= 30:
            breakdown["transaction_volume"] = 5
        elif total_transactions >= 10:
            breakdown["transaction_volume"] = 2
        else:
            breakdown["transaction_volume"] = 0

        score = max(0, min(100, 50 + sum(breakdown.values())))

        return score, breakdown
