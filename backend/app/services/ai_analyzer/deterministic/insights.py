"""
Insights, warnings, and recommendations generation.
"""

import logging
from typing import List, Dict, Any, Optional

from ..models import HealthScore

logger = logging.getLogger(__name__)


class InsightsGenerator:
    """Generate insights, warnings, and recommendations."""

    def generate(
        self,
        metrics: Dict[str, Any],
        categories: Dict[str, Any],
        income_analysis: Dict[str, Any],
        fuliza_cycles: Dict[str, Any],
        health_score: int,
        recurring: List[Dict[str, Any]],
        anomalies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate insights, warnings, and recommendations."""
        return {
            "insights": self._generate_insights(
                metrics=metrics,
                categories=categories,
                fuliza_cycles=fuliza_cycles,
                health_score=health_score,
                recurring=recurring,
            ),
            "warnings": self._generate_warnings(
                metrics=metrics,
                income_analysis=income_analysis,
                fuliza_cycles=fuliza_cycles,
                anomalies=anomalies,
            ),
            "recommendations": self._generate_recommendations(
                metrics=metrics,
                categories=categories,
                fuliza_cycles=fuliza_cycles,
                recurring=recurring,
                health_score=health_score,
            ),
            "income_change": 0,  # Would need previous period data
            "expenses_change": 0,  # Would need previous period data
        }

    def _generate_insights(
        self,
        metrics: Dict[str, Any],
        categories: Dict[str, Any],
        fuliza_cycles: Dict[str, Any],
        health_score: int,
        recurring: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate actionable insights."""
        insights = []

        total_income = metrics.get("total_income", 0)
        total_expenses = metrics.get("total_expenses", 0)
        net_cash_flow = metrics.get("net_cash_flow", 0)
        savings_rate = metrics.get("savings_rate", 0)
        burn_rate = metrics.get("burn_rate_daily", 0)

        # Net cash flow
        direction = "positive" if net_cash_flow >= 0 else "negative"
        insights.append(
            f"Your net cash flow is {direction}: KES {abs(net_cash_flow):,.0f} "
            f"({'surplus' if net_cash_flow >= 0 else 'deficit'}) "
            f"with a {savings_rate:.1f}% savings rate."
        )

        # Top category
        top_category = categories.get("top_category", "N/A")
        top_category_pct = categories.get("top_category_percent", 0)
        if top_category != "N/A" and top_category_pct > 0:
            insights.append(
                f"Your biggest spending category is {top_category} "
                f"({top_category_pct:.1f}% of total spend)."
            )

        # Burn rate
        if burn_rate > 0:
            insights.append(
                f"You spend approximately KES {burn_rate:,.0f} per day. "
                f"At this rate, KES 10,000 lasts about {10000/burn_rate:.0f} days."
            )

        # Recurring payments
        if recurring:
            top_r = recurring[0]
            insights.append(
                f"Your largest recurring payment is '{top_r['description']}' "
                f"averaging KES {top_r['average_amount']:,.0f} "
                f"({top_r['occurrences']} times)."
            )

        # Health score
        label = (
            "excellent"
            if health_score >= 80
            else (
                "good"
                if health_score >= 65
                else "fair" if health_score >= 50 else "needs attention"
            )
        )
        insights.append(
            f"Your financial health score is {health_score}/100 ({label}). "
            f"Kenyan average is around 55/100."
        )

        return insights

    def _generate_warnings(
        self,
        metrics: Dict[str, Any],
        income_analysis: Dict[str, Any],
        fuliza_cycles: Dict[str, Any],
        anomalies: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate warning messages."""
        warnings = []

        betting_pct = metrics.get("betting_pct", 0)
        total_income = metrics.get("total_income", 0)
        savings_rate = metrics.get("savings_rate", 0)
        fee_pct = metrics.get("fee_pct", 0)

        # Betting
        if betting_pct > 20:
            warnings.append(
                f"🚨 Betting accounts for {betting_pct:.1f}% of your total spend "
                f"(KES {total_income * betting_pct / 100:,.0f}). "
                f"This is significantly impacting your financial health."
            )
        elif betting_pct > 5:
            warnings.append(
                f"⚠️ Betting is {betting_pct:.1f}% of your spend. "
                f"Consider reducing this to below 5%."
            )

        # Fuliza
        fuliza_count = fuliza_cycles.get("cycle_count", 0)
        fuliza_total = fuliza_cycles.get("total_fuliza_drawn", 0)
        if fuliza_count > 5:
            warnings.append(
                f"🚨 You used Fuliza {fuliza_count} times (KES {fuliza_total:,.0f} total). "
                f"Frequent Fuliza use indicates cash flow gaps — consider an emergency fund."
            )
        elif fuliza_count > 0:
            warnings.append(
                f"⚠️ {fuliza_count} Fuliza usage(s) detected. "
                f"Reducing reliance on credit improves your score."
            )

        # Savings
        if savings_rate < 0:
            warnings.append(
                "🚨 You are spending more than you earn. "
                "Review your expenses immediately to avoid debt accumulation."
            )
        elif savings_rate < 5:
            warnings.append(
                f"⚠️ Your savings rate is only {savings_rate:.1f}%. "
                f"Aim for at least 10% (KES {total_income * 0.10:,.0f}/month)."
            )

        # Fees
        if fee_pct > 5:
            warnings.append(
                f"⚠️ M-PESA fees are {fee_pct:.1f}% of your income. "
                f"Use Mpesa Ratiba or bank transfers for large amounts to save on fees."
            )

        # Anomalies
        if anomalies:
            warnings.append(
                f"⚠️ {len(anomalies)} unusually large transaction(s) detected. "
                f"Largest: KES {anomalies[0]['amount']:,.0f} on {anomalies[0]['date']}."
            )

        # Loan income
        if income_analysis.get("loan_disbursement_warning"):
            loan_pct = income_analysis.get("loan_as_pct_of_total_inflow", 0)
            if loan_pct > 20:
                warnings.append(
                    f"🚨 {loan_pct:.1f}% of your 'income' is actually loan disbursements. "
                    f"This masks your true financial position."
                )
            elif loan_pct > 5:
                warnings.append(
                    f"⚠️ {loan_pct:.1f}% of inflows are loan disbursements. "
                    f"Don't treat loans as income."
                )

        return warnings

    def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        categories: Dict[str, Any],
        fuliza_cycles: Dict[str, Any],
        recurring: List[Dict[str, Any]],
        health_score: int,
    ) -> List[str]:
        """Generate concrete recommendations."""
        recommendations = []

        savings_rate = metrics.get("savings_rate", 0)
        betting_pct = metrics.get("betting_pct", 0)
        fuliza_count = fuliza_cycles.get("cycle_count", 0)
        top_category = categories.get("top_category", "N/A")
        top_category_pct = categories.get("top_category_percent", 0)

        # Savings
        if savings_rate < 10:
            target = max(10.0, savings_rate + 5)
            recommendations.append(
                f"Set up automatic savings of {target:.0f}% of each income received. "
                f"Use M-Shwari Lock Savings to make it harder to spend."
            )

        # Betting
        if betting_pct > 5:
            recommendations.append(
                f"Reduce betting from {betting_pct:.1f}% to under 5% of spend. "
                f"Redirect those funds to a Sacco or money market fund."
            )

        # Fuliza
        if fuliza_count > 0:
            recommendations.append(
                "Build a KES 5,000–10,000 emergency buffer in M-Shwari to eliminate "
                "Fuliza dependency. Even KES 200/day savings builds this in 25–50 days."
            )

        # Top category
        if top_category_pct > 30:
            recommendations.append(
                f"Your top category ({top_category}) is {top_category_pct:.1f}% of spend. "
                f"Set a monthly budget cap and track it weekly."
            )

        # Recurring payments
        if recurring:
            total_recurring = sum(r["total"] for r in recurring[:5])
            recommendations.append(
                f"You have KES {total_recurring:,.0f} in recurring payments. "
                f"Review each one — cancel any subscriptions you no longer use."
            )

        # General advice
        recommendations.append(
            "Use the 50/30/20 rule adapted for Kenya: "
            "50% needs (rent, food, transport), 30% wants, 20% savings/investment."
        )

        return recommendations[:5]
