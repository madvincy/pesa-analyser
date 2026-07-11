"""
Income source classification and analysis.
"""

import re
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models import IncomeAnalysis
from ..utils import normalize_transaction, get_tx_amount

logger = logging.getLogger(__name__)


class IncomeAnalyzer:
    """Analyze income sources."""

    def analyze(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Classify income sources and identify issues."""
        if not transactions:
            return self._empty_result()

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        sources: Dict[str, List[float]] = defaultdict(list)

        for tx in norm_txs:
            if tx.get("direction") != "in":
                continue

            amount = get_tx_amount(tx)
            if amount == 0:
                continue

            desc = tx.get("description", "").lower()

            if "salary payment" in desc:
                if "ncba" in desc or "kcb" in desc or "equity" in desc:
                    sources["salary_bank"].append(amount)
                else:
                    sources["salary_other"].append(amount)
            elif "deposit of funds at agent" in desc:
                sources["agent_deposit"].append(amount)
            elif "funds received from" in desc:
                sources["peer_transfer"].append(amount)
            elif "platinum credit" in desc or "loan" in desc:
                sources["loan_disbursement"].append(amount)
            elif "business payment" in desc:
                sources["business_payment"].append(amount)
            else:
                sources["other"].append(amount)

        summary = {}
        for source, amounts in sources.items():
            summary[source] = {
                "count": len(amounts),
                "total": round(sum(amounts), 2),
                "average": round(sum(amounts) / len(amounts), 2) if amounts else 0,
            }

        loan_total = summary.get("loan_disbursement", {}).get("total", 0)
        true_income_total = sum(
            s["total"] for k, s in summary.items() if k != "loan_disbursement"
        )

        return {
            "by_source": summary,
            "loan_disbursement_warning": loan_total > 0,
            "loan_as_pct_of_total_inflow": (
                round(loan_total / (loan_total + true_income_total) * 100, 1)
                if (loan_total + true_income_total) > 0
                else 0
            ),
            "total_true_income": round(true_income_total, 2),
            "total_loan_income": round(loan_total, 2),
        }

    def detect_salary_day(self, transactions: List[Dict[str, Any]]) -> Optional[int]:
        """Detect the most common salary day of month."""
        if not transactions:
            return None

        norm_txs = [normalize_transaction(tx) for tx in transactions]
        logger.info("=" * 80)
        logger.info("Income analyzer received %d transactions", len(norm_txs))

        income_seen = 0

        for tx in norm_txs:
            logger.info(
                "type=%s amount=%s description=%s",
                tx.get("type"),
                get_tx_amount(tx),
                tx.get("description"),
            )

            if tx.get("direction") == "in":
                income_seen += 1

        logger.info("Income transactions found: %d", income_seen)
        logger.info("=" * 80)
        salary_days: List[int] = []

        for tx in norm_txs:
            desc = tx.get("description", "").lower()
            if "salary" not in desc:
                continue

            raw_date = str(tx.get("date", ""))
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    salary_days.append(datetime.strptime(raw_date, fmt).day)
                    break
                except ValueError:
                    continue

        if not salary_days:
            return None

        return max(set(salary_days), key=salary_days.count)

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "by_source": {},
            "loan_disbursement_warning": False,
            "loan_as_pct_of_total_inflow": 0,
            "total_true_income": 0,
            "total_loan_income": 0,
        }
