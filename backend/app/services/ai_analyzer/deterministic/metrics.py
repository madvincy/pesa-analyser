"""
Core financial metrics calculation.
"""

import logging
from collections import defaultdict
from typing import List, Dict, Any, DefaultDict
from statistics import mean

from ..utils import normalize_transaction, get_tx_amount, get_tx_type

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculate core financial metrics from transactions."""

    def __init__(self):
        self.total_income = 0.0
        self.total_expenses = 0.0
        self.operating_expenses = 0.0
        self.total_fees = 0.0
        self.fuliza_total = 0.0
        self.fuliza_count = 0
        self.betting_total = 0.0
        self.p2p_total = 0.0
        self.p2p_count = 0
        self.highest_tx = 0.0
        self.highest_tx_date = ""
        self.balances = []
        self.categories: DefaultDict[str, float] = defaultdict(float)
        self.loan_inflows = 0.0
        self.loan_repayments = 0.0
        self.refunds = 0.0
        self.income_sources: DefaultDict[str, float] = defaultdict(float)
        self.income_count = 0
        self.expense_count = 0
        self.top_depositors: Dict[str, float] = defaultdict(float)
        self.top_creditors: Dict[str, float] = defaultdict(float)

    def calculate(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate all metrics."""
        # Normalize transactions
        norm_txs = [normalize_transaction(tx) for tx in transactions]

        # Reset state
        self._reset()

        # Process each transaction
        for tx in norm_txs:
            self._process_transaction(tx)

        # Calculate derived metrics
        return self._build_metrics()

    def _reset(self):
        """Reset all metrics."""
        self.total_income = 0.0
        self.total_expenses = 0.0
        self.operating_expenses = 0.0
        self.total_fees = 0.0
        self.fuliza_total = 0.0
        self.fuliza_count = 0
        self.betting_total = 0.0
        self.p2p_total = 0.0
        self.p2p_count = 0
        self.highest_tx = 0.0
        self.highest_tx_date = ""
        self.balances = []
        self.categories.clear()
        self.loan_inflows = 0.0
        self.loan_repayments = 0.0
        self.refunds = 0.0
        self.income_sources.clear()
        self.income_count = 0
        self.expense_count = 0
        self.top_depositors.clear()
        self.top_creditors.clear()

    def _process_transaction(self, tx: Dict[str, Any]):
        """Process a single transaction."""
        direction = tx.get("direction")
        transaction_type = tx.get("transaction_type")
        funding_source = tx.get("funding_source")
        amount = get_tx_amount(tx)
        if amount == 0:
            return

        tx_type = get_tx_type(tx)
        description = tx.get("description", "").lower()
        fee = abs(float(tx.get("fee", 0) or 0))

        # Count income/expense
        if tx_type == "income":
            self.income_count += 1
        else:
            self.expense_count += 1

        # Process balance
        balance = tx.get("balance")
        if balance not in (None, "", 0):
            try:
                self.balances.append(float(balance))
            except Exception:
                pass

        # Process fee
        if fee > 0:
            self.total_fees += fee
            self.total_expenses += fee

        # Process Fuliza/loan
        if tx.get("fuliza_used"):
            self.fuliza_total += float(tx.get("fuliza_amount", amount))
            self.fuliza_count += 1
            self.loan_inflows += amount
            self._update_highest(amount, tx.get("date", ""))
            return

        # Process loan repayment
        if transaction_type == "od_loan_repayment":
            self.loan_repayments += amount
            self._update_highest(amount, tx.get("date", ""))
            return

        # Process reversal
        if tx_type == "reversal":
            self.refunds += amount
            self._update_highest(amount, tx.get("date", ""))
            return

        # Process income/expense
        if direction == "in":
            self.total_income += amount
            self._classify_income_source(description, amount)
            # Track top depositors
            who = (
                tx.get("party_name")
                or tx.get("display_name")
                or tx.get("description", "Unknown")
            )
            self.top_depositors[who] += amount
        else:
            self.operating_expenses += amount
            self.total_expenses += amount + fee
            BETTING_KEYWORDS = (
                "betika",
                "sportpesa",
                "odibets",
                "shabiki",
                "bangbet",
                "betway",
                "mozzart",
                "parimatch",
                "1xbet",
            )
            # Check for betting
            if any(k in description for k in BETTING_KEYWORDS):
                self.betting_total += amount
                # Check for P2P
            tt = (tx.get("transaction_type") or "").lower()

            if tt.startswith("customer_transfer") or tt.startswith(
                "customer_send_money"
            ):
                self.p2p_total += amount
                self.p2p_count += 1
            # Track top creditors
            who = (
                tx.get("party_name")
                or tx.get("display_name")
                or tx.get("description", "Unknown")
            )
            self.top_creditors[who] += amount

        self._update_highest(amount, tx.get("date", ""))

    def _classify_income_source(self, description: str, amount: float):
        """Classify income source."""
        desc_lower = description.lower()
        if "salary" in desc_lower:
            self.income_sources["salary"] += amount
        elif "business" in desc_lower:
            self.income_sources["business"] += amount
        elif "funds received" in desc_lower:
            self.income_sources["peer_transfer"] += amount
        else:
            self.income_sources["other"] += amount

    def _update_highest(self, amount: float, date: str):
        """Update highest transaction."""
        if amount > self.highest_tx:
            self.highest_tx = amount
            self.highest_tx_date = date

    def _build_metrics(self) -> Dict[str, Any]:
        """Build metrics dictionary."""
        net_cash_flow = self.total_income - self.total_expenses
        avg_balance = mean(self.balances) if self.balances else 0.0
        savings_rate = (
            (net_cash_flow / self.total_income * 100) if self.total_income else 0.0
        )
        burn_rate = self.operating_expenses / 30 if self.operating_expenses else 0.0
        fee_pct = (
            (self.total_fees / self.total_expenses * 100)
            if self.total_expenses
            else 0.0
        )
        betting_pct = (
            (self.betting_total / self.operating_expenses * 100)
            if self.operating_expenses
            else 0.0
        )

        # Get top income source
        if self.income_sources:
            top_source, top_amount = max(
                self.income_sources.items(), key=lambda x: x[1]
            )
            income_concentration = (
                (top_amount / self.total_income * 100) if self.total_income else 0.0
            )
        else:
            top_source = "N/A"
            income_concentration = 0.0

        # Get top depositors and creditors
        top_depositors = sorted(
            [{"who": k, "amount": round(v, 2)} for k, v in self.top_depositors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        top_creditors = sorted(
            [{"who": k, "amount": round(v, 2)} for k, v in self.top_creditors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        return {
            "total_income": round(self.total_income, 2),
            "total_expenses": round(self.total_expenses, 2),
            "operating_expenses": round(self.operating_expenses, 2),
            "total_fees": round(self.total_fees, 2),
            "fee_pct": round(fee_pct, 2),
            "net_cash_flow": round(net_cash_flow, 2),
            "average_balance": round(avg_balance, 2),
            "savings_rate": round(savings_rate, 2),
            "burn_rate_daily": round(burn_rate, 2),
            "fuliza_total": round(self.fuliza_total, 2),
            "fuliza_count": self.fuliza_count,
            "betting_total": round(self.betting_total, 2),
            "betting_pct": round(betting_pct, 2),
            "p2p_total": round(self.p2p_total, 2),
            "p2p_count": self.p2p_count,
            "highest_transaction": round(self.highest_tx, 2),
            "highest_transaction_date": self.highest_tx_date,
            "loan_inflows": round(self.loan_inflows, 2),
            "loan_repayments": round(self.loan_repayments, 2),
            "refunds": round(self.refunds, 2),
            "income_count": self.income_count,
            "expense_count": self.expense_count,
            "top_income_source": top_source,
            "income_concentration": round(income_concentration, 2),
            "income_sources": dict(self.income_sources),
            "top_depositors": top_depositors,
            "top_creditors": top_creditors,
        }
