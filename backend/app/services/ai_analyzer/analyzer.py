"""
Main AIAnalyzer class - orchestrates all analysis components.
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional

from .models import StageCallback
from .utils import normalize_transactions
from .deterministic import (
    MetricsCalculator,
    CategoryAnalyzer,
    IncomeAnalyzer,
    FulizaAnalyzer,
    HealthAnalyzer,
    RecurringAnalyzer,
    AnomalyDetector,
    InsightsGenerator,
)
from .ai_providers import AIProviderFactory

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Main analyzer orchestrating deterministic and AI analysis."""

    def __init__(self) -> None:
        """Initialize the AI Analyzer with API keys and configurations."""
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.claude_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

        self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.claude_model_name = os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-20241022")
        self.deepseek_model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.openai_model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.deepseek_base_url = "https://api.deepseek.com/v1"

        # Initialize components
        self.metrics_calculator = MetricsCalculator()
        self.category_analyzer = CategoryAnalyzer()
        self.income_analyzer = IncomeAnalyzer()
        self.fuliza_analyzer = FulizaAnalyzer()
        self.health_analyzer = HealthAnalyzer()
        self.recurring_analyzer = RecurringAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        self.insights_generator = InsightsGenerator()
        self.ai_provider_factory = AIProviderFactory()

        self.available_providers = self._check_available_providers()
        self.analysis_prompt = self._build_analysis_prompt()

    def _check_available_providers(self) -> List[str]:
        """Check which AI providers are available."""
        providers = []
        for key, name in [
            (self.gemini_api_key, "gemini"),
            (self.claude_api_key, "claude"),
            (self.deepseek_api_key, "deepseek"),
            (self.openai_api_key, "openai"),
        ]:
            if key and not key.startswith("your_"):
                providers.append(name)

        if not providers:
            logger.warning(
                "⚠️ No AI API keys configured — using deterministic analysis only."
            )
        else:
            logger.info(f"✅ Available AI providers: {', '.join(providers)}")

        return providers

    def _build_analysis_prompt(self) -> str:
        """Build the analysis prompt for AI providers."""
        return """
You are a Kenyan personal finance advisor specialising in M-PESA and bank statements.
Analyse the pre-computed transaction data below and enrich it with deeper insights.

Return ONLY a valid JSON object with these keys (do not wrap in markdown):
- insights: array of 5 specific, actionable strings in plain English
- warnings: array of strings for concerning patterns (betting, Fuliza overuse, etc.)
- recommendations: array of 5 concrete steps the user can take
- top_income_source: string (e.g. "Salary from ABC Company")
- income_concentration: float (% of income from single source, 0-100)
- income_change: float (% change vs previous period, estimate from data)
- expenses_change: float (% change vs previous period, estimate from data)

Context: This is a Kenyan user. Reference KES amounts, M-PESA services,
local merchants (Naivas, KPLC, etc.), and Kenyan financial context.
Be specific — mention actual amounts and merchants from the data.
"""

    # ─── Public Entry Points ──────────────────────────────────────────────────

    async def analyze_transactions(
        self, transactions: List[Dict[str, Any]], statement_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Analyze pre-parsed transactions directly.

        Args:
            transactions: List of transaction dictionaries
            statement_type: Type of statement

        Returns:
            Dictionary with complete analysis results
        """
        if not transactions:
            logger.warning("⚠️ No transactions provided")
            return self._empty_result()

        logger.info(f"🔵 Analyzing {len(transactions)} transactions")

        result = self._deterministic_analysis(transactions, statement_type)

        try:
            ai_result = await self._try_ai_providers(
                transactions, statement_type, result
            )
            if ai_result:
                result.update(ai_result)
                logger.info("✅ AI enrichment successful")
        except Exception as e:
            logger.warning(f"⚠️ AI enrichment failed: {e}")

        return result

    async def analyze_transactions_staged(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str = "unknown",
        on_stage: Optional[StageCallback] = None,
    ) -> Dict[str, Any]:
        """
        Analyze transactions with staged progress reporting.

        Stages:
            1. basic_summary - Core metrics
            2. category_breakdown - Category analysis
            3. behavior_metrics - Health, recurring, anomalies
            4. insights - AI-enriched insights
        """
        if not transactions:
            empty = self._empty_result()
            if on_stage:
                await on_stage("basic_summary", empty)
            return empty

        logger.info(f"🔵 Running staged analysis on {len(transactions)} transactions")

        # Run full deterministic analysis
        full = self._deterministic_analysis(transactions, statement_type)

        # Stage 1: Basic summary
        basic_summary = self._extract_stage(
            full,
            [
                "total_income",
                "total_expenses",
                "net_cash_flow",
                "average_balance",
                "savings_rate",
                "burn_rate_daily",
                "total_fees",
                "fee_pct",
                "fuliza_total",
                "fuliza_count",
                "betting_total",
                "betting_pct",
                "p2p_total",
                "p2p_count",
                "income_count",
                "expense_count",
                "highest_transaction",
                "highest_transaction_date",
                "total_transactions",
                "transaction_count",
            ],
        )
        if on_stage:
            await on_stage("basic_summary", basic_summary)

        # Stage 2: Category breakdown
        category_breakdown = self._extract_stage(
            full,
            [
                "category_data",
                "monthly_data",
                "trend_data",
                "top_category",
                "top_category_amount",
                "top_category_percent",
                "top_income_source",
                "income_concentration",
                "top_depositors",
                "top_creditors",
            ],
        )
        if on_stage:
            await on_stage("category_breakdown", category_breakdown)

        # Stage 3: Behavior metrics
        behavior_metrics = self._extract_stage(
            full,
            [
                "health_score",
                "health_breakdown",
                "fuliza_cycles",
                "income_analysis",
                "day_of_week_spend",
                "salary_day",
                "recurring_payments",
                "anomalies",
            ],
        )
        if on_stage:
            await on_stage("behavior_metrics", behavior_metrics)

        # Stage 4: Insights
        insights_stage = self._extract_stage(
            full,
            [
                "insights",
                "warnings",
                "recommendations",
                "income_change",
                "expenses_change",
            ],
        )
        if on_stage:
            await on_stage("insights", insights_stage)

        # ─── AI Enrichment ───────────────────────────────────────────────
        try:
            ai_result = await self._try_ai_providers(transactions, statement_type, full)
            if ai_result:
                logger.info("✅ AI enrichment successful — re-pushing insights")
                full.update(ai_result)
                enriched_insights = self._extract_stage(
                    full,
                    [
                        "insights",
                        "warnings",
                        "recommendations",
                        "income_change",
                        "expenses_change",
                        "top_income_source",
                        "income_concentration",
                    ],
                )
                if on_stage:
                    await on_stage("insights", enriched_insights)
        except Exception as e:
            logger.warning(f"⚠️ AI enrichment failed: {e}")

        return full

    def _extract_stage(self, data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        """Extract specific keys from data."""
        return {k: data.get(k) for k in keys if k in data}

    # ─── Deterministic Analysis ──────────────────────────────────────────────

    def _deterministic_analysis(
        self, transactions: List[Dict[str, Any]], statement_type: str = "unknown"
    ) -> Dict[str, Any]:
        """Perform deterministic (non-AI) financial analysis."""
        if not transactions:
            logger.warning("⚠️ No transactions supplied")
            return self._empty_result()

        # Normalize transactions
        norm_transactions = normalize_transactions(transactions)
        logger.info(
            f"🔵 Running deterministic analysis on {len(norm_transactions)} transactions"
        )

        # Calculate metrics
        metrics = self.metrics_calculator.calculate(norm_transactions)

        # Analyze categories
        categories = self.category_analyzer.analyze(norm_transactions)

        # Analyze income
        income_analysis = self.income_analyzer.analyze(norm_transactions)

        # Analyze Fuliza
        fuliza_cycles = self.fuliza_analyzer.detect_cycles(norm_transactions)

        # Analyze recurring payments
        recurring = self.recurring_analyzer.detect(norm_transactions)

        # Detect anomalies
        anomalies = self.anomaly_detector.detect(norm_transactions)

        # Calculate health score
        health_score, health_breakdown = self.health_analyzer.calculate(
            fuliza_cycles=fuliza_cycles,
            income_analysis=income_analysis,
            savings_rate=metrics.get("savings_rate", 0),
            betting_pct=metrics.get("betting_pct", 0),
            total_transactions=len(norm_transactions),
        )

        # Generate insights
        insights = self.insights_generator.generate(
            metrics=metrics,
            categories=categories,
            income_analysis=income_analysis,
            fuliza_cycles=fuliza_cycles,
            health_score=health_score,
            recurring=recurring,
            anomalies=anomalies,
        )

        # Build result with all fields
        result = {
            # Core metrics
            "total_income": metrics.get("total_income", 0),
            "total_expenses": metrics.get("total_expenses", 0),
            "operating_expenses": metrics.get("operating_expenses", 0),
            "net_cash_flow": metrics.get("net_cash_flow", 0),
            "average_balance": metrics.get("average_balance", 0),
            "savings_rate": metrics.get("savings_rate", 0),
            "burn_rate_daily": metrics.get("burn_rate_daily", 0),
            # Fees
            "total_fees": metrics.get("total_fees", 0),
            "fee_pct": metrics.get("fee_pct", 0),
            # Fuliza
            "fuliza_total": metrics.get("fuliza_total", 0),
            "fuliza_count": metrics.get("fuliza_count", 0),
            "fuliza_cycles": fuliza_cycles,
            # Betting
            "betting_total": metrics.get("betting_total", 0),
            "betting_pct": metrics.get("betting_pct", 0),
            # P2P
            "p2p_total": metrics.get("p2p_total", 0),
            "p2p_count": metrics.get("p2p_count", 0),
            # Transactions
            "total_transactions": len(norm_transactions),
            "transaction_count": len(norm_transactions),
            "income_count": metrics.get("income_count", 0),
            "expense_count": metrics.get("expense_count", 0),
            "highest_transaction": metrics.get("highest_transaction", 0),
            "highest_transaction_date": metrics.get("highest_transaction_date", ""),
            # Categories
            **categories,
            # Income
            "top_income_source": metrics.get("top_income_source", "N/A"),
            "income_concentration": metrics.get("income_concentration", 0),
            "income_analysis": income_analysis,
            "income_change": 0,  # Will be calculated from monthly data
            "expenses_change": 0,  # Will be calculated from monthly data
            # People
            "top_depositors": metrics.get("top_depositors", []),
            "top_creditors": metrics.get("top_creditors", []),
            # Health
            "health_score": health_score,
            "health_breakdown": health_breakdown,
            # Reports
            "recurring_payments": recurring,
            "anomalies": anomalies,
            # Insights
            **insights,
            # Metadata
            "statement_type": statement_type,
        }

        # Add monthly and trend data
        monthly_data = self.category_analyzer.get_monthly_breakdown(norm_transactions)
        result["monthly_data"] = monthly_data
        result["trend_data"] = self._build_trend_data(monthly_data)

        # Add day of week spend
        result["day_of_week_spend"] = self.category_analyzer.get_day_of_week_spend(
            norm_transactions
        )

        # Add salary day
        result["salary_day"] = self.income_analyzer.detect_salary_day(norm_transactions)

        # Calculate income/expense change from monthly data
        if len(monthly_data) >= 2:
            prev = monthly_data[-2]
            curr = monthly_data[-1]
            result["income_change"] = self._calculate_change(
                prev.get("income", 0), curr.get("income", 0)
            )
            result["expenses_change"] = self._calculate_change(
                prev.get("expenses", 0), curr.get("expenses", 0)
            )

        # Add detailed metrics
        result["detailed_transaction_metrics"] = self._build_detailed_metrics(
            norm_transactions
        )

        return result

    def _calculate_change(self, prev: float, curr: float) -> float:
        """Calculate percentage change."""
        if prev == 0:
            return 0.0
        return round((curr - prev) / prev * 100, 2)

    def _build_trend_data(
        self, monthly_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build trend data from monthly breakdown."""
        return [
            {
                "date": m["month"],
                "transactions": m["transaction_count"],
                "amount": m["expenses"],
            }
            for m in monthly_data
        ]

    def _build_detailed_metrics(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build detailed transaction metrics."""
        return {
            "total_transactions": len(transactions),
            "total_income": sum(
                t.get("amount", 0) for t in transactions if t.get("type") == "income"
            ),
            "total_expenses": sum(
                t.get("amount", 0) for t in transactions if t.get("type") == "expense"
            ),
        }

    # ─── AI Providers ─────────────────────────────────────────────────────────

    async def _try_ai_providers(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Try AI providers in sequence until one succeeds."""
        for provider_name in self.available_providers:
            try:
                logger.info(f"🔍 Trying {provider_name.capitalize()}...")
                provider = self.ai_provider_factory.get_provider(provider_name)

                if provider is None:
                    logger.warning(f"⚠️ Provider {provider_name} not available")
                    continue

                result = await provider.analyze(
                    transactions=transactions,
                    statement_type=statement_type,
                    deterministic=deterministic,
                    prompt=self.analysis_prompt,
                )
                if result:
                    logger.info(
                        f"✅ {provider_name.capitalize()} enrichment successful"
                    )
                    return result
            except Exception as e:
                logger.warning(f"⚠️ {provider_name} failed: {str(e)[:120]}")
                continue

        logger.info("ℹ️ No AI provider succeeded, using deterministic analysis only")
        return None

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when no transactions found."""
        return {
            "total_income": 0,
            "total_expenses": 0,
            "net_cash_flow": 0,
            "average_balance": 0,
            "savings_rate": 0,
            "burn_rate_daily": 0,
            "total_fees": 0,
            "fee_pct": 0,
            "fuliza_total": 0,
            "fuliza_count": 0,
            "betting_total": 0,
            "betting_pct": 0,
            "p2p_total": 0,
            "p2p_count": 0,
            "income_count": 0,
            "expense_count": 0,
            "highest_transaction": 0,
            "highest_transaction_date": "",
            "top_category": "N/A",
            "top_category_amount": 0,
            "top_category_percent": 0,
            "top_income_source": "N/A",
            "income_concentration": 0,
            "total_transactions": 0,
            "transaction_count": 0,
            "category_data": [],
            "monthly_data": [],
            "trend_data": [],
            "health_score": 0,
            "health_breakdown": {},
            "day_of_week_spend": [],
            "salary_day": None,
            "recurring_payments": [],
            "anomalies": [],
            "insights": ["No transactions found. Please upload a valid statement."],
            "warnings": [],
            "recommendations": [],
            "income_change": 0,
            "expenses_change": 0,
            "statement_type": "unknown",
            "fuliza_cycles": {"cycle_count": 0, "same_day_repayment_rate": 0},
            "income_analysis": {"loan_disbursement_warning": False},
            "top_depositors": [],
            "top_creditors": [],
            "detailed_transaction_metrics": {},
        }
