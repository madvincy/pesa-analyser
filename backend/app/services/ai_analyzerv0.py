import os
import json
import asyncio
import re
import logging
import concurrent.futures
from collections import defaultdict
from datetime import datetime
from statistics import mean, stdev
import statistics
from turtle import pd
from typing import Dict, List, Any, Optional, Tuple, Callable, Awaitable, DefaultDict

logger = logging.getLogger(__name__)


# ─── Kenyan PayBill → Merchant lookup ────────────────────────────────────────
KNOWN_PAYBILLS: Dict[str, Tuple[str, str, str]] = {
    "888880": ("KPLC Prepaid", "utilities", "electricity"),
    "888884": ("KPLC Postpaid", "utilities", "electricity"),
    "888861": ("Nairobi Water", "utilities", "water"),
    "200222": ("KCB Bank", "finance", "bank_transfer"),
    "522522": ("Equity Bank", "finance", "bank_transfer"),
    "400200": ("DSTV", "entertainment", "subscription"),
    "969696": ("Safaricom Data", "airtime", "mobile_data"),
    "290290": ("Fuliza Repay", "loan", "fuliza_repayment"),
    "300300": ("M-Shwari", "loan", "mshwari"),
    "601600": ("Zuku", "utilities", "internet"),
    "802900": ("Faiba", "utilities", "internet"),
    "185185": ("Startimes", "entertainment", "subscription"),
    "111222": ("Stanbic Bank", "finance", "bank_transfer"),
    "303030": ("NCBA Bank", "finance", "bank_transfer"),
}

# ─── Category rules: (pattern, category, subcategory, direction) ─────────────
CATEGORY_RULES: List[Tuple[str, str, str, str]] = [
    (r"received from", "income", "peer_transfer", "in"),
    (r"salary|wages|payroll", "income", "salary", "in"),
    (r"reversal", "income", "reversal", "in"),
    (r"pay bill received|paybill received", "income", "business_receipt", "in"),
    (r"mshwari deposit|m-shwari deposit", "income", "mshwari", "in"),
    (r"sent to|transfer to", "transfer", "peer_transfer", "out"),
    (r"kplc|kenya power", "utilities", "electricity", "out"),
    (r"nairobi water|nwsc", "utilities", "water", "out"),
    (r"zuku|faiba|safaricom home", "utilities", "internet", "out"),
    (r"dstv|startimes|showmax|netflix", "entertainment", "subscription", "out"),
    (r"fuliza", "loan", "fuliza", "out"),
    (r"fuliza repay|repay fuliza", "loan", "fuliza_repayment", "out"),
    (r"m-shwari|mshwari", "loan", "mshwari", "out"),
    (r"kcb mpesa|kcb m-pesa", "loan", "kcb_mpesa", "out"),
    (r"withdraw.*agent|agent.*withdraw", "cash", "withdrawal", "out"),
    (r"airtime|scratch card", "airtime", "airtime", "out"),
    (r"data bundle|data pack", "airtime", "data", "out"),
    (r"uber|bolt|little cab|faras", "transport", "ride_hailing", "out"),
    (r"fuel|petrol|diesel|total energies|kenol|rubis", "transport", "fuel", "out"),
    (r"matatu|bus|sacco", "transport", "public_transport", "out"),
    (
        r"naivas|quickmart|carrefour|chandarana|cleanshelf|uchumi",
        "food",
        "grocery",
        "out",
    ),
    (
        r"java|kfc|chicken inn|pizza|burger|cafe|restaurant|hotel",
        "food",
        "dining",
        "out",
    ),
    (r"jumia|kilimall|amazon", "shopping", "ecommerce", "out"),
    (r"buy goods|till", "shopping", "till_payment", "out"),
    (r"hospital|clinic|pharmacy|chemist|doctor|nhif", "health", "medical", "out"),
    (r"school|university|college|tuition|kcse|knec", "education", "tuition", "out"),
    (
        r"sportpesa|betika|shabiki|mcheza|odibets|premiumbetting",
        "betting",
        "betting",
        "out",
    ),
    (r"sacco|chama|investment|shares|nse|cma", "savings", "investment", "out"),
    (r"mshwari lock|fixed deposit", "savings", "fixed_deposit", "out"),
]


# ─── Stage callback type ──────────────────────────────────────────────────────
# Called as: await on_stage("basic_summary", {...partial fields...})
StageCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]


class AIAnalyzer:
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

        # Add regex patterns for parsing
        self.patterns = {
            "phone": re.compile(r"(\+?254|0)?[7-9]\d{8}\b"),
            "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            "receipt": re.compile(
                r"^([A-Z0-9]{10})\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$"
            ),
            "amount": re.compile(
                r"(Completed|Failed|Pending|Complete)\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s*$"
            ),
        }

        self.available_providers: List[str] = []
        for key, name in [
            (self.gemini_api_key, "gemini"),
            (self.claude_api_key, "claude"),
            (self.deepseek_api_key, "deepseek"),
            (self.openai_api_key, "openai"),
        ]:
            if key and not key.startswith("your_"):
                self.available_providers.append(name)
                # logger.info(f"✅ {name.capitalize()} API key configured")
            else:
                logger.info(f"ℹ️  {name.capitalize()} API key not configured")

        if not self.available_providers:
            logger.warning(
                "⚠️  No AI API keys configured — using deterministic analysis only."
            )
        else:
            logger.info(
                f"✅ Available AI providers: {', '.join(self.available_providers)}"
            )

        self.analysis_prompt = """
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

    # ─── Public entry point ──────────────────────────────────────────────────
    async def analyze(self, text: str, statement_type: str = "mpesa") -> Dict[str, Any]:
        """
        Main entry point for analyzing transaction data from raw text.

        ✅ FIXED: previously spun up a brand-new event loop with
        run_until_complete() to run the AI enrichment coroutine. Since this
        method is called from within an already-running async request (the
        FastAPI handler's event loop), that call raised RuntimeError
        immediately — before the coroutine was ever scheduled — which is
        exactly what produced the "coroutine was never awaited" warning.
        Now this method is itself async and just awaits directly.

        Args:
            text: Raw statement text to analyze
            statement_type: Type of statement (mpesa, bank, etc.)

        Returns:
            Dictionary with complete analysis results
        """
        print("Before extract_transactions")
        logger.info("🔥 analyze() called - will extract transactions from raw text")
        transactions = self._extract_transactions(text)
        print("After extract_transactions")
        print(len(transactions))
        logger.info(f"🔵 Extracted {len(transactions)} transactions from raw text")

        for tx in transactions:
            parsed = self._parse_transaction_details(tx.get("description", ""))
            tx.update(
                {
                    "party_name": parsed["name"],
                    "party_phone": parsed["phone"],
                    "merchant_till": parsed["till"],
                    "paybill_number": parsed["paybill"],
                    "agent_number": parsed["agent"],
                    "location": parsed["location"],
                    "parsed_type": parsed["type"],
                }
            )

        result = self._deterministic_analysis(transactions, statement_type)

        try:
            ai_result = await self._try_ai_providers(
                transactions, statement_type, result
            )
            if ai_result:
                # logger.info("✅ AI enrichment successful, merging results")
                result.update(ai_result)
            else:
                logger.info(
                    "ℹ️  AI enrichment returned no results, using deterministic analysis"
                )
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            logger.info("ℹ️  Continuing with deterministic analysis only")

        return result

    async def analyze_transactions(
        self, transactions: List[Dict[str, Any]], statement_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Analyze pre-parsed transactions directly. Callers must `await` this
        now — see the note in analyze() above for why it changed from sync
        to async.

        Args:
            transactions: List of transaction dictionaries
            statement_type: Type of statement (mpesa, bank, etc.)

        Returns:
            Dictionary with complete analysis results
        """
        if not transactions:
            logger.warning("⚠️  No transactions provided to analyze_transactions")
            return self._empty_result()

        # logger.info(f"🔵 Analyzing {len(transactions)} pre-parsed transactions")

        result = self._deterministic_analysis(transactions, statement_type)

        try:
            ai_result = await self._try_ai_providers(
                transactions, statement_type, result
            )
            if ai_result:
                # logger.info("✅ AI enrichment successful, merging results")
                result.update(ai_result)
            else:
                logger.info(
                    "ℹ️  AI enrichment returned no results, using deterministic analysis"
                )
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            # logger.info("ℹ️  Continuing with deterministic analysis only")

        return result

    async def analyze_transactions_staged(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str = "unknown",
        on_stage: Optional[StageCallback] = None,
    ) -> Dict[str, Any]:
        """
        Same result as analyze_transactions(), but reveals it in ordered
        pieces via `on_stage(stage_name, stage_data)` — cheapest/fastest
        first, AI enrichment last (the only step with real network latency).
        Callers persist each stage to its own table and push it over
        WebSocket as soon as it arrives, instead of waiting for everything.

        Stage order:
          1. "basic_summary"      — totals, fees, fuliza/betting/p2p aggregates
          2. "category_breakdown" — category_data, monthly/trend data, top sources
          3. "behavior_metrics"   — health score, fuliza cycles, recurring, anomalies
          4. "insights"           — deterministic insights/warnings/recommendations,
                                     re-pushed if AI enrichment then improves them
        """
        logger.info("🔥 analyze_transactions() called - using pre-parsed transactions")
        if not transactions:
            empty = self._empty_result()
            if on_stage:
                await on_stage("basic_summary", empty)
            return empty

        # logger.info(f"🔵 Running staged analysis on {len(transactions)} transactions")

        # The deterministic pass itself is a single cheap O(n) computation —
        # we're not re-running it per stage, just revealing pre-computed
        # pieces of it in order so the frontend can render progressively
        # instead of blocking on the slow AI call at the very end.
        full = self._deterministic_analysis(transactions, statement_type)

        basic_summary = {
            k: full[k]
            for k in (
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
                "highest_transaction",
                "highest_transaction_date",
                "total_transactions",
                "transaction_count",
            )
        }
        if on_stage:
            await on_stage("basic_summary", basic_summary)

        category_breakdown = {
            k: full[k]
            for k in (
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
            )
        }
        if on_stage:
            await on_stage("category_breakdown", category_breakdown)

        behavior_metrics = {
            k: full[k]
            for k in (
                "health_score",
                "health_breakdown",
                "fuliza_cycles",
                "income_analysis",
                "day_of_week_spend",
                "salary_day",
                "recurring_payments",
                "anomalies",
            )
        }
        if on_stage:
            await on_stage("behavior_metrics", behavior_metrics)

        insights_stage = {
            k: full[k]
            for k in (
                "insights",
                "warnings",
                "recommendations",
                "income_change",
                "expenses_change",
            )
        }
        if on_stage:
            await on_stage("insights", insights_stage)

        # ─── Slowest step: AI enrichment (real network calls) ───────────────
        try:
            ai_result = await self._try_ai_providers(transactions, statement_type, full)
            if ai_result:
                logger.info(
                    "✅ AI enrichment successful — merging + re-pushing insights"
                )
                full.update(ai_result)
                enriched_keys = [
                    k
                    for k in (
                        "insights",
                        "warnings",
                        "recommendations",
                        "income_change",
                        "expenses_change",
                        "top_income_source",
                        "income_concentration",
                    )
                    if k in full
                ]
                enriched_insights = {k: full[k] for k in enriched_keys}
                if on_stage:
                    await on_stage("insights", enriched_insights)
            else:
                logger.info(
                    "ℹ️  AI enrichment returned no results — deterministic insights stand"
                )
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            logger.info("ℹ️  Continuing with deterministic insights only")

        return full

    # ─── Transaction Extraction ──────────────────────────────────────────────
    def _extract_transactions(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse Safaricom M-PESA PDF text into logical transactions.

        Multiple rows with the same receipt number are treated as one
        logical transaction.

        Example:

            Merchant Payment
            Pay Merchant Charge
            OverDraft of Credit Party

        becomes

            Merchant Payment
            fee = merchant charge
        """

        transactions: List[Dict[str, Any]] = []

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        receipt_pattern = self.patterns["receipt"]
        amount_pattern = self.patterns["amount"]

        receipt_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        ####################################################################
        # STEP 1
        # Parse every receipt into individual legs
        ####################################################################

        i = 0

        while i < len(lines):
            m = receipt_pattern.match(lines[i])

            if not m:
                i += 1
                continue

            receipt, date_str, time_str, remainder = m.groups()

            receipt_lines = [remainder]

            j = i + 1

            while j < len(lines):
                if receipt_pattern.match(lines[j]):
                    break

                receipt_lines.append(lines[j])
                j += 1

            description_parts: List[str] = []

            for line in receipt_lines:
                amt = amount_pattern.search(line)

                if amt:
                    status, amount_str, balance_str = amt.groups()

                    description = " ".join(description_parts).strip()
                    description = re.sub(r"\s+", " ", description)

                    try:
                        amount = float(amount_str.replace(",", ""))
                        balance = float(balance_str.replace(",", ""))
                    except ValueError:
                        description_parts = []
                        continue

                    receipt_groups[receipt].append(
                        {
                            "receipt": receipt,
                            "date": date_str,
                            "time": time_str,
                            "description": description,
                            "amount": amount,
                            "balance": balance,
                            "status": status,
                        }
                    )

                    logger.debug(
                        "LEG %-12s %10.2f %s",
                        receipt,
                        amount,
                        description,
                    )

                    description_parts = []
                else:
                    description_parts.append(line)

            i = j

        logger.info("Parsed %d receipt groups", len(receipt_groups))

        ####################################################################
        # STEP 2
        # Convert each receipt into one logical transaction
        ####################################################################

        mechanic_keywords = (
            "overdraft of credit party",
            "customer transfer of funds charge",
            "pay merchant charge",
            "pay bill charge",
            "withdrawal charge",
            "agent withdrawal charge",
            "agent deposit charge",
            "send money charge",
        )

        for receipt, legs in receipt_groups.items():
            if not legs:
                continue

            fee_total = 0.0
            primary = None
            is_fuliza = False

            for leg in legs:
                desc = leg["description"].lower()

                ####################################################
                # Fuliza detection
                ####################################################

                if "fuliza" in desc or "overdraft" in desc or "od loan" in desc:
                    is_fuliza = True

                ####################################################
                # Charges
                ####################################################

                if "charge" in desc or "fee" in desc:
                    fee_total += abs(leg["amount"])

                    logger.debug(
                        "FEE %-12s %10.2f %s",
                        receipt,
                        abs(leg["amount"]),
                        desc,
                    )

                    continue

                ####################################################
                # Ignore accounting entries
                ####################################################

                if any(keyword in desc for keyword in mechanic_keywords):
                    continue

                ####################################################
                # Choose primary transaction
                ####################################################

                if primary is None:
                    primary = leg

            ########################################################
            # Fallback
            ########################################################

            if primary is None:
                primary = max(
                    legs,
                    key=lambda x: abs(x["amount"]),
                )

            amount = primary["amount"]

            tx = {
                "receipt": receipt,
                "date": primary["date"],
                "time": primary["time"],
                "description": primary["description"],
                "amount": abs(amount),
                "balance": primary["balance"],
                "status": primary["status"],
                "type": "income" if amount > 0 else "expense",
                "fee": round(fee_total, 2),
                "fuliza": is_fuliza,
            }

            ########################################################
            # Category
            ########################################################

            desc = tx["description"]
            desc_lower = desc.lower()

            if "salary payment" in desc_lower:
                tx["category"] = "Salary"
            elif "funds received from" in desc_lower:
                tx["category"] = "Received Money"
            elif "business payment from" in desc_lower:
                tx["category"] = "Business Payment"
            elif "merchant payment" in desc_lower:
                tx["category"] = "Buy Goods"
                m = re.search(r"to\s+(\d+)", desc, re.I)
                if m:
                    tx["till"] = m.group(1)
            elif "customer payment to small business" in desc_lower:
                tx["category"] = "Pochi La Biashara"
            elif "pay bill" in desc_lower:
                tx["category"] = "PayBill"
                m = re.search(r"to\s+(\d+)", desc, re.I)
                if m:
                    tx["paybill"] = m.group(1)
            elif "withdrawal at agent" in desc_lower:
                tx["category"] = "Agent Withdrawal"
            elif "deposit at agent" in desc_lower:
                tx["category"] = "Agent Deposit"
            elif (
                "customer transfer" in desc_lower
                or "customer send money" in desc_lower
                or "sent to" in desc_lower
            ):
                tx["category"] = "Send Money"
            elif "airtime" in desc_lower:
                tx["category"] = "Airtime"
            elif "bundle purchase" in desc_lower:
                tx["category"] = "Data Bundle"
            elif "m-shwari" in desc_lower:
                tx["category"] = "M-Shwari"
            elif "international transfer" in desc_lower:
                tx["category"] = "International Transfer"
            elif "promotion payment" in desc_lower:
                tx["category"] = "Promotion"

            ########################################################
            # Phone extraction
            ########################################################

            phone = re.search(
                r"(254\d{9}|07\d{8}|01\d{8})",
                desc,
            )

            if phone:
                tx["phone"] = phone.group()

            transactions.append(tx)

        ####################################################################
        # STEP 3
        # Finalize
        ####################################################################

        transactions.sort(key=lambda x: (x["date"], x["time"]))

        logger.info("=" * 80)
        logger.info("LOGICAL TRANSACTION SUMMARY")
        logger.info("=" * 80)

        total_fees = 0.0

        for tx in transactions:
            total_fees += tx.get("fee", 0)

            logger.info(
                "%s | %-10s | %8.2f | fee=%7.2f | %s",
                tx["receipt"],
                tx["type"],
                tx["amount"],
                tx["fee"],
                tx["description"],
            )

        logger.info("=" * 80)
        logger.info("Transactions : %d", len(transactions))
        logger.info("Total Fees   : %.2f", total_fees)
        logger.info("=" * 80)

        return transactions

    # ─── Fuliza Cycle Detection ──────────────────────────────────────────────
    def _detect_fuliza_cycles(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detects the drawdown→repayment pattern visible throughout this statement.
        A 'cycle' = a Fuliza-tagged expense followed within minutes by an
        OD Loan Repayment of a similar amount, funded by a fresh deposit.
        """
        fuliza_legs = [t for t in transactions if t.get("fuliza")]
        repayments = [
            t for t in transactions if "od loan repayment" in t["description"].lower()
        ]

        total_drawn = sum(t["amount"] for t in fuliza_legs)
        total_repaid = sum(t["amount"] for t in repayments)
        cycle_count = len(repayments)

        same_day_cycles = 0
        for r in repayments:
            r_date = r["date"]
            same_day_drawdowns = [f for f in fuliza_legs if f["date"] == r_date]
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
            "interpretation": (
                "Severe Fuliza dependency — same-day repayment cycles"
                if same_day_cycles / max(cycle_count, 1) > 0.7
                else "Moderate Fuliza usage"
            ),
        }

    # ─── Income Source Classification ────────────────────────────────────────
    def _classify_income_sources(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Classifies income sources by type and flags potential issues.
        """
        sources: Dict[str, List[float]] = defaultdict(list)

        for tx in transactions:
            if tx["type"] != "income":
                continue
            desc = tx["description"].lower()

            if "salary payment" in desc:
                if "ncba" in desc or "kcb" in desc or "equity" in desc:
                    sources["salary_bank"].append(tx["amount"])
                else:
                    sources["salary_other"].append(tx["amount"])
            elif "deposit of funds at agent" in desc:
                sources["agent_deposit"].append(tx["amount"])
            elif "funds received from" in desc:
                sources["peer_transfer"].append(tx["amount"])
            elif "platinum credit" in desc or "loan" in desc:
                sources["loan_disbursement"].append(tx["amount"])
            elif "business payment" in desc:
                sources["business_payment"].append(tx["amount"])
            else:
                sources["other"].append(tx["amount"])

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

    # ─── AI Providers ─────────────────────────────────────────────────────────
    async def _try_ai_providers(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Try AI providers in sequence until one succeeds."""
        for provider in ["gemini", "claude", "deepseek", "openai"]:
            if provider not in self.available_providers:
                continue
            try:
                logger.info(f"🔍 Trying {provider.capitalize()}...")
                if provider == "gemini":
                    result = await self._analyze_with_gemini(
                        transactions, statement_type, deterministic
                    )
                elif provider == "claude":
                    result = await self._analyze_with_claude(
                        transactions, statement_type, deterministic
                    )
                elif provider == "deepseek":
                    result = await self._analyze_with_deepseek(
                        transactions, statement_type, deterministic
                    )
                else:
                    result = await self._analyze_with_openai(
                        transactions, statement_type, deterministic
                    )
                if result:
                    logger.info(f"✅ {provider.capitalize()} enrichment successful")
                    return result
            except Exception as e:
                msg = str(e).lower()
                if "402" in msg or "insufficient" in msg:
                    logger.warning(f"⚠️  {provider}: insufficient balance")
                elif "401" in msg or "authentication" in msg:
                    logger.warning(f"⚠️  {provider}: authentication failed")
                elif "404" in msg or "not found" in msg:
                    logger.warning(f"⚠️  {provider}: model not found")
                else:
                    logger.warning(f"⚠️  {provider} failed: {str(e)[:120]}")
                continue
        logger.info("ℹ️  No AI provider succeeded, using deterministic analysis only")
        return None

    def _build_ai_prompt(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> str:
        """Build the prompt for AI analysis."""
        summary = {
            "statement_type": statement_type,
            "total_transactions": deterministic["total_transactions"],
            "total_income": deterministic["total_income"],
            "total_expenses": deterministic["total_expenses"],
            "net_cash_flow": deterministic["net_cash_flow"],
            "savings_rate": deterministic["savings_rate"],
            "health_score": deterministic["health_score"],
            "top_categories": deterministic["category_data"][:6],
            "fuliza_count": deterministic["fuliza_count"],
            "fuliza_total": deterministic["fuliza_total"],
            "betting_total": deterministic["betting_total"],
            "betting_pct": deterministic["betting_pct"],
            "recurring": deterministic["recurring_payments"][:5],
            "sample_transactions": self._prepare_transaction_data(transactions)[:50],
        }
        return (
            self.analysis_prompt
            + f"\n\nPre-computed data:\n{json.dumps(summary, indent=2, default=str)}"
        )

    async def _analyze_with_gemini(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze with Google Gemini."""
        GEMINI_MODELS = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-8b",
        ]
        env_model = os.getenv("GEMINI_MODEL")
        if env_model:
            GEMINI_MODELS = [env_model] + GEMINI_MODELS

        prompt = self._build_ai_prompt(transactions, statement_type, deterministic)

        try:
            import google.genai as genai  # type: ignore

            client = genai.Client(api_key=self.gemini_api_key)
            for model_name in GEMINI_MODELS:
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=prompt,
                    )
                    return self._parse_json_response(response.text)
                except Exception as e:
                    if "404" in str(e) or "not found" in str(e).lower():
                        logger.warning(f"⚠️  Gemini model {model_name} not found")
                        continue
                    raise
        except ImportError:
            pass

        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=self.gemini_api_key)

        last_error: Optional[Exception] = None
        for model_name in GEMINI_MODELS:
            try:
                logger.info(f"🔍 Trying Gemini model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(model.generate_content, prompt)
                logger.info(f"✅ Gemini {model_name} succeeded")
                return self._parse_json_response(response.text)
            except Exception as e:
                last_error = e
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.warning(f"⚠️  Model {model_name} not found, trying next")
                    continue
                raise

        raise last_error or Exception("No Gemini models available")

    async def _analyze_with_claude(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze with Anthropic Claude."""
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=self.claude_api_key)
        prompt = self._build_ai_prompt(transactions, statement_type, deterministic)
        response = await asyncio.to_thread(
            client.messages.create,
            model=self.claude_model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_json_response(response.content[0].text)

    async def _analyze_with_deepseek(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze with DeepSeek."""
        import openai  # type: ignore

        client = openai.OpenAI(
            api_key=self.deepseek_api_key,
            base_url=self.deepseek_base_url,
        )
        prompt = self._build_ai_prompt(transactions, statement_type, deterministic)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=self.deepseek_model_name,
            messages=[
                {"role": "system", "content": "Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return self._parse_json_response(response.choices[0].message.content)

    async def _analyze_with_openai(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str,
        deterministic: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze with OpenAI."""
        import openai  # type: ignore

        client = openai.OpenAI(api_key=self.openai_api_key)
        prompt = self._build_ai_prompt(transactions, statement_type, deterministic)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=self.openai_model_name,
            messages=[
                {"role": "system", "content": "Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return self._parse_json_response(response.choices[0].message.content)

    # ─── Deterministic Analysis ──────────────────────────────────────────────
    def _deterministic_analysis(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Perform deterministic (non-AI) financial analysis.
        """

        if not transactions:
            logger.warning("⚠️ No transactions supplied.")
            return self._empty_result()

        logger.info(
            f"🔵 Running deterministic analysis on {len(transactions)} transactions"
        )

        classified = [self._classify_transaction(tx) for tx in transactions]

        # ===============================================================
        # INITIALIZE TOTALS
        # ===============================================================

        total_income = 0.0
        total_expenses = 0.0
        operating_expenses = 0.0
        total_fees = 0.0

        loan_inflows = 0.0
        loan_repayments = 0.0
        refunds = 0.0

        fuliza_total = 0.0
        fuliza_count = 0

        betting_total = 0.0
        p2p_total = 0.0
        p2p_count = 0

        highest_tx = 0.0
        highest_tx_date = ""

        balances = []

        categories: DefaultDict[str, float] = defaultdict(float)

        income_sources: DefaultDict[str, float] = defaultdict(float)

        true_income: DefaultDict[str, float] = defaultdict(float)
        loan_income: DefaultDict[str, float] = defaultdict(float)
        refund_income: DefaultDict[str, float] = defaultdict(float)

        # ===============================================================
        # MAIN PROCESSING LOOP
        # ===============================================================

        for tx, cls in zip(transactions, classified):
            amount = abs(float(tx.get("amount", 0) or 0))

            description = tx.get("description") or ""

            desc = description.lower()

            parsed = tx.get("parsed") or self._parse_transaction_details(description)

            tx_type = parsed.get("type")

            # -----------------------------------------------------------
            # BALANCE
            # -----------------------------------------------------------

            balance = tx.get("balance")

            if balance not in (None, "", 0):
                try:
                    balances.append(float(balance))
                except Exception:
                    pass

            # -----------------------------------------------------------
            # CATEGORY TOTALS
            # -----------------------------------------------------------

            categories[cls["category"]] += amount

            # -----------------------------------------------------------
            # BETTING
            # -----------------------------------------------------------

            if cls["category"] == "betting":
                betting_total += amount

            # -----------------------------------------------------------
            # PEER TRANSFERS
            # -----------------------------------------------------------

            if cls["subcategory"] == "peer_transfer":
                p2p_total += amount
                p2p_count += 1

            # -----------------------------------------------------------
            # FEES
            # -----------------------------------------------------------

            is_fee = (
                tx_type
                in (
                    "transfer_charge",
                    "merchant_charge",
                    "withdrawal_charge",
                    "paybill_charge",
                    "agent_charge",
                )
                or ("charge" in desc and "reversal" not in desc)
                or ("fee" in desc and "reversal" not in desc)
            )

            fee = abs(float(tx.get("fee", 0) or 0))

            if fee > 0:
                total_fees += fee
                total_expenses += fee

            # -----------------------------------------------------------
            # FULIZA / LOAN DISBURSEMENTS
            # -----------------------------------------------------------

            if tx_type in (
                "fuliza_credit",
                "loan_disbursement",
            ):
                loan_inflows += amount

                loan_income[tx_type] += amount

                if tx_type == "fuliza_credit":
                    fuliza_total += amount
                    fuliza_count += 1

                if amount > highest_tx:
                    highest_tx = amount
                    highest_tx_date = str(tx.get("date", ""))

                continue

            # -----------------------------------------------------------
            # LOAN REPAYMENTS
            # -----------------------------------------------------------

            if tx_type in (
                "fuliza_repayment",
                "loan_repayment",
            ):
                loan_repayments += amount

                if amount > highest_tx:
                    highest_tx = amount
                    highest_tx_date = str(tx.get("date", ""))

                continue

            # -----------------------------------------------------------
            # REVERSALS
            # -----------------------------------------------------------

            if tx_type == "reversal":
                refunds += amount

                refund_income["reversal"] += amount

                if amount > highest_tx:
                    highest_tx = amount
                    highest_tx_date = str(tx.get("date", ""))

                continue

            # -----------------------------------------------------------
            # TRUE INCOME
            # -----------------------------------------------------------

            if cls["direction"] == "in":
                total_income += amount

                income_sources[cls["subcategory"]] += amount

                true_income[cls["subcategory"]] += amount

            # -----------------------------------------------------------
            # OPERATING EXPENSES
            # -----------------------------------------------------------

            else:
                operating_expenses += amount
                total_expenses += amount + fee

            # -----------------------------------------------------------
            # HIGHEST TRANSACTION
            # -----------------------------------------------------------

            if amount > highest_tx:
                highest_tx = amount + fee
                highest_tx_date = str(tx.get("date", ""))

        # ===============================================================
        # SUMMARY CALCULATIONS
        # ===============================================================

        net_cash_flow = total_income - total_expenses

        avg_balance = mean(balances) if balances else 0.0

        savings_rate = (net_cash_flow / total_income) * 100 if total_income else 0.0

        burn_rate = operating_expenses / 30 if operating_expenses else 0.0

        betting_pct = (
            (betting_total / operating_expenses) * 100 if operating_expenses else 0.0
        )

        fee_pct = (total_fees / total_expenses) * 100 if total_expenses else 0.0

        logger.info(
            f"Income={total_income:.2f} "
            f"Expenses={total_expenses:.2f} "
            f"Fees={total_fees:.2f}"
        )

        # ===============================================================
        # MONTHLY ANALYSIS
        # ===============================================================

        monthly_data = self._monthly_breakdown(
            transactions,
            classified,
        )

        trend_data = [
            {
                "date": m["month"],
                "transactions": m["transaction_count"],
                "amount": m["expenses"],
            }
            for m in monthly_data
        ]

        # ===============================================================
        # PATTERN DETECTION
        # ===============================================================

        dow_spend = self._day_of_week_pattern(
            transactions,
            classified,
        )

        salary_day = self._detect_salary_day(
            transactions,
            classified,
        )

        recurring = self._detect_recurring(
            transactions,
            classified,
        )

        anomalies = self._detect_anomalies(
            transactions,
        )

        # ===============================================================
        # ADVANCED ANALYSIS
        # ===============================================================

        fuliza_cycles = self._detect_fuliza_cycles(transactions)

        income_analysis = self._classify_income_sources(transactions)

        health_score, health_breakdown = self._calculate_health_score_v2(
            fuliza_cycles=fuliza_cycles,
            income_sources=income_analysis,
            savings_rate=savings_rate,
            betting_pct=betting_pct,
            total_transactions=len(transactions),
        )

        detailed_metrics = self._extract_detailed_transaction_metrics(transactions)

        logger.info(f"📊 Health Score: {health_score}/100")
        logger.info(f"   Breakdown: {health_breakdown}")
        if fuliza_cycles["cycle_count"] > 0:
            logger.info(
                f"   Fuliza cycles: {fuliza_cycles['cycle_count']} (same-day rate: {fuliza_cycles['same_day_repayment_rate']}%)"
            )
        if income_analysis.get("loan_disbursement_warning"):
            logger.warning(
                f"   ⚠️  Loan income: {income_analysis['loan_as_pct_of_total_inflow']}% of inflows"
            )

        category_data = sorted(
            [{"name": k, "value": round(v, 2)} for k, v in categories.items()],
            key=lambda x: x["value"],
            reverse=True,
        )
        top_category = category_data[0]["name"] if category_data else "N/A"

        top_category_amount = category_data[0]["value"] if category_data else 0.0

        top_category_pct = (
            (top_category_amount / total_expenses) * 100 if total_expenses else 0.0
        )

        depositors: DefaultDict[str, float] = defaultdict(float)
        creditors: DefaultDict[str, float] = defaultdict(float)
        logger.info(
            "Transactions containing Charge: %d",
            sum(
                1
                for tx in transactions
                if "charge" in (tx.get("description") or "").lower()
            ),
        )
        charge_count = 0

        for tx in transactions:
            desc = tx.get("description", "")
            fee = tx.get("fee", 0)

            if "charge" in desc.lower():
                charge_count += 1

            # logger.info(
            #     "DESC=%s | AMOUNT=%s | FEE=%s",
            #     desc,
            #     tx.get("amount"),
            #     fee,
            # )

        logger.info(f"Transactions containing Charge: {charge_count}")
        for tx in transactions:
            desc = tx.get("description", "")
            if "charge" in desc.lower():
                logger.info(
                    "FEE TX -> %s | amount=%s",
                    desc,
                    tx.get("amount"),
                )
            parsed = self._parse_transaction_details(desc)

            who = parsed.get("name") or parsed.get("phone") or desc

            try:
                amt = float(tx.get("amount", 0) or 0)
            except Exception:
                amt = 0.0
            if tx.get("type") == "income":
                depositors[who] += amt
            else:
                creditors[who] += amt

        top_depositors = sorted(
            [{"who": k, "amount": round(v, 2)} for k, v in depositors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        top_creditors = sorted(
            [{"who": k, "amount": round(v, 2)} for k, v in creditors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        depositors = defaultdict(float)
        creditors = defaultdict(float)

        fee_transactions = 0

        for tx in transactions:
            if float(tx.get("fee", 0) or 0) > 0:
                fee_transactions += 1
                logger.info(tx)

        logger.info(f"Transactions with fee field: {fee_transactions}")

        for tx in transactions:
            parsed = tx.get("parsed") or self._parse_transaction_details(
                tx.get("description", "")
            )

            name = (
                parsed.get("name")
                or parsed.get("location")
                or parsed.get("agent")
                or parsed.get("till")
                or parsed.get("paybill")
                or parsed.get("phone")
                or tx.get("display_name")
                or tx.get("description")
                or "Unknown"
            )

            amount = abs(float(tx.get("amount", 0) or 0))

            parsed_type = parsed.get("type")

            # Ignore debt & reversals

            if parsed_type in (
                "fuliza_credit",
                "loan_disbursement",
                "fuliza_repayment",
                "loan_repayment",
                "reversal",
            ):
                continue

            if tx.get("type") == "income":
                depositors[name] += amount
            else:
                creditors[name] += amount

        top_depositors = sorted(
            [
                {
                    "who": k,
                    "amount": round(v, 2),
                }
                for k, v in depositors.items()
            ],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        top_creditors = sorted(
            [
                {
                    "who": k,
                    "amount": round(v, 2),
                }
                for k, v in creditors.items()
            ],
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        # ===============================================================
        # TOP INCOME SOURCE
        # ===============================================================

        if income_sources:
            top_source, top_source_amount = max(
                income_sources.items(),
                key=lambda item: item[1],
            )

            income_concentration = (
                (top_source_amount / total_income) * 100 if total_income > 0 else 0.0
            )
        else:
            top_source = "N/A"
            top_source_amount = 0.0
            income_concentration = 0.0

        # ===============================================================
        # INSIGHTS
        # ===============================================================

        insights = self._generate_insights(
            total_income,
            total_expenses,
            net_cash_flow,
            savings_rate,
            top_category,
            top_category_pct,
            betting_pct,
            fuliza_count,
            fuliza_total,
            burn_rate,
            health_score,
            salary_day,
            recurring,
        )

        warnings = self._generate_warnings(
            betting_pct,
            fuliza_count,
            fuliza_total,
            total_income,
            savings_rate,
            anomalies,
            fee_pct,
            income_analysis,
        )

        recommendations = self._generate_recommendations(
            savings_rate,
            betting_pct,
            fuliza_count,
            top_category,
            top_category_pct,
            recurring,
            health_score,
        )

        return {
            # ==========================================================
            # CORE METRICS
            # ==========================================================
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "operating_expenses": round(
                operating_expenses,
                2,
            ),
            "loan_inflows": round(
                loan_inflows,
                2,
            ),
            "loan_repayments": round(
                loan_repayments,
                2,
            ),
            "refunds": round(
                refunds,
                2,
            ),
            "net_cash_flow": round(
                net_cash_flow,
                2,
            ),
            "average_balance": round(
                avg_balance,
                2,
            ),
            "burn_rate_daily": round(
                burn_rate,
                2,
            ),
            "savings_rate": round(
                savings_rate,
                2,
            ),
            "total_fees": round(
                total_fees,
                2,
            ),
            "fee_pct": round(
                fee_pct,
                2,
            ),
            # ==========================================================
            # FULIZA
            # ==========================================================
            "fuliza_total": round(
                fuliza_total,
                2,
            ),
            "fuliza_count": fuliza_count,
            "fuliza_cycles": fuliza_cycles,
            # ==========================================================
            # BETTING
            # ==========================================================
            "betting_total": round(
                betting_total,
                2,
            ),
            "betting_pct": round(
                betting_pct,
                2,
            ),
            # ==========================================================
            # P2P
            # ==========================================================
            "p2p_total": round(
                p2p_total,
                2,
            ),
            "p2p_count": p2p_count,
            # ==========================================================
            # TRANSACTIONS
            # ==========================================================
            "total_transactions": len(transactions),
            "transaction_count": len(transactions),
            "highest_transaction": round(
                highest_tx,
                2,
            ),
            "highest_transaction_date": highest_tx_date,
            # ==========================================================
            # CATEGORY
            # ==========================================================
            "category_data": category_data,
            "top_category": top_category,
            "top_category_amount": round(
                top_category_amount,
                2,
            ),
            "top_category_percent": round(
                top_category_pct,
                2,
            ),
            # ==========================================================
            # INCOME
            # ==========================================================
            "top_income_source": top_source,
            "income_concentration": round(
                income_concentration,
                2,
            ),
            "income_analysis": {
                **income_analysis,
                "true_income": dict(true_income),
                "loan_income": dict(loan_income),
                "refund_income": dict(refund_income),
            },
            # ==========================================================
            # REPORTS
            # ==========================================================
            "monthly_data": monthly_data,
            "trend_data": trend_data,
            "day_of_week_spend": dow_spend,
            "salary_day": salary_day,
            "recurring_payments": recurring,
            "anomalies": anomalies,
            # ==========================================================
            # HEALTH
            # ==========================================================
            "health_score": health_score,
            "health_breakdown": health_breakdown,
            # ==========================================================
            # PEOPLE
            # ==========================================================
            "top_depositors": top_depositors,
            "top_creditors": top_creditors,
            # ==========================================================
            # AI
            # ==========================================================
            "insights": insights,
            "warnings": warnings,
            "recommendations": recommendations,
            # ==========================================================
            # TRENDS
            # ==========================================================
            "income_change": self._mom_change(
                monthly_data,
                "income",
            ),
            "expenses_change": self._mom_change(
                monthly_data,
                "expenses",
            ),
            "statement_type": statement_type,
            # ==========================================================
            # DETAILED TRANSACTION ANALYTICS
            # ==========================================================
            "detailed_transaction_metrics": detailed_metrics,
        }

    # ─── Detailed Transaction Metrics Extraction ──────────────────────────────
    def _extract_detailed_transaction_metrics(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract detailed transaction metrics based on parsed transaction details.
        """

        results: Dict[str, Any] = {}

        # =====================================================================
        # STEP 0: NORMALIZE EVERY TRANSACTION ONCE
        # =====================================================================

        for tx in transactions:
            parsed = self._parse_transaction_details(tx.get("description", ""))

            tx["parsed"] = parsed
            tx["parsed_type"] = parsed.get("type")

            tx["party_name"] = parsed.get("name")
            tx["party_phone"] = parsed.get("phone")

            tx["merchant_till"] = parsed.get("till")
            tx["paybill_number"] = parsed.get("paybill")

            tx["agent_number"] = parsed.get("agent")
            tx["agent_location"] = parsed.get("location")

            # Friendly display name used everywhere else
            if parsed["type"] == "merchant":
                tx["display_name"] = (
                    f'{parsed["till"]} - {parsed["name"]}'
                    if parsed.get("till")
                    else parsed.get("name")
                )

            elif parsed["type"] == "pochi":
                tx["display_name"] = (
                    f'{parsed["till"]} - {parsed["name"]}'
                    if parsed.get("till")
                    else parsed.get("name")
                )

            elif parsed["type"] == "paybill":
                tx["display_name"] = (
                    f'{parsed["paybill"]} - {parsed["name"]}'
                    if parsed.get("paybill")
                    else parsed.get("name")
                )

            elif parsed["type"] == "funds_received":
                if parsed.get("phone"):
                    tx["display_name"] = f'{parsed["name"]} ({parsed["phone"]})'
                else:
                    tx["display_name"] = parsed.get("name") or tx.get("description")

            elif parsed["type"] == "sent":
                if parsed.get("phone"):
                    tx["display_name"] = f'{parsed["name"]} ({parsed["phone"]})'
                else:
                    tx["display_name"] = parsed.get("name") or tx.get("description")

            elif parsed["type"] in (
                "withdrawal_agent",
                "deposit_agent",
            ):
                tx["display_name"] = (
                    f'{parsed["agent"]} - {parsed["location"]}'
                    if parsed.get("agent")
                    else parsed.get("location")
                )

            else:
                tx["display_name"] = parsed.get("name") or tx.get("description", "")

        # =====================================================================
        # 1. TOP 10 PAID IN
        # =====================================================================

        incoming = [t for t in transactions if t.get("type") == "income"]

        payer_totals = {}

        for tx in incoming:
            key = tx["display_name"] or "Unknown"

            if key not in payer_totals:
                payer_totals[key] = {
                    "name": tx.get("party_name"),
                    "phone": tx.get("party_phone"),
                    "who": key,
                    "count": 0,
                    "total": 0.0,
                }

            payer_totals[key]["count"] += 1
            payer_totals[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_paid_in"] = sorted(
            payer_totals.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 2. TOP 10 WITHDRAWALS
        # =====================================================================

        outgoing = [t for t in transactions if t.get("type") == "expense"]

        top_withdrawals = sorted(
            outgoing,
            key=lambda x: abs(x.get("amount", 0)),
            reverse=True,
        )[:10]

        results["top_10_withdrawals"] = [
            {
                "receipt": tx.get("receipt"),
                "date": tx.get("date"),
                "description": tx["display_name"],
                "amount": abs(tx.get("amount", 0)),
            }
            for tx in top_withdrawals
        ]

        results["top_10_withdrawals_sum"] = sum(
            abs(tx.get("amount", 0)) for tx in top_withdrawals
        )

        # =====================================================================
        # 3. PAYBILLS
        # =====================================================================

        paybills = [t for t in transactions if t.get("parsed_type") == "paybill"]

        results["paybill_total"] = sum(abs(t.get("amount", 0)) for t in paybills)

        results["paybill_count"] = len(paybills)

        paybill_summary = {}

        for tx in paybills:
            key = tx.get("paybill_number") or "Unknown"

            if key not in paybill_summary:
                paybill_summary[key] = {
                    "paybill": key,
                    "name": tx.get("party_name"),
                    "count": 0,
                    "total": 0.0,
                }

            paybill_summary[key]["count"] += 1
            paybill_summary[key]["total"] += abs(tx.get("amount", 0))

        results["paybill_breakdown"] = sorted(
            paybill_summary.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 4. TRANSFER CHARGES
        # =====================================================================

        transfer_charges = []

        for tx in transactions:
            desc = tx.get("description", "").lower().strip()

            if any(
                keyword in desc
                for keyword in (
                    "transfer charge",
                    "customer transfer of funds charge",
                    "send money charge",
                    "transaction charge",
                    "transaction cost",
                )
            ):
                transfer_charges.append(tx)

        results["total_transfer_charges"] = sum(
            abs(t.get("amount", 0)) for t in transfer_charges
        )

        results["transfer_charge_count"] = len(transfer_charges)

        # =====================================================================
        # 5. INDIVIDUAL TRANSFERS (SEND MONEY)
        # =====================================================================

        individual_transfers = [
            t for t in transactions if t.get("parsed_type") == "sent"
        ]

        results["total_sent_to_individuals"] = sum(
            abs(t.get("amount", 0)) for t in individual_transfers
        )

        results["individual_transfer_count"] = len(individual_transfers)

        recipient_totals = {}

        for tx in individual_transfers:
            key = tx.get("display_name") or "Unknown"

            if key not in recipient_totals:
                recipient_totals[key] = {
                    "name": tx.get("party_name"),
                    "phone": tx.get("party_phone"),
                    "who": key,
                    "count": 0,
                    "total": 0.0,
                }

            recipient_totals[key]["count"] += 1
            recipient_totals[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_individual_recipients"] = sorted(
            recipient_totals.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 6. POCHI LA BIASHARA
        # =====================================================================

        pochi_transactions = [
            t for t in transactions if t.get("parsed_type") == "pochi"
        ]

        results["total_pochi_la_biashara"] = sum(
            abs(t.get("amount", 0)) for t in pochi_transactions
        )

        results["pochi_la_biashara_count"] = len(pochi_transactions)

        pochi_summary = {}

        for tx in pochi_transactions:
            key = tx.get("merchant_till") or tx.get("display_name")

            if key not in pochi_summary:
                pochi_summary[key] = {
                    "business": tx.get("party_name"),
                    "till": tx.get("merchant_till"),
                    "count": 0,
                    "total": 0.0,
                }

            pochi_summary[key]["count"] += 1
            pochi_summary[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_small_businesses"] = sorted(
            pochi_summary.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 7. MERCHANT PAYMENTS (BUY GOODS)
        # =====================================================================

        merchant_transactions = [
            t for t in transactions if t.get("parsed_type") == "merchant"
        ]

        results["total_till_payments"] = sum(
            abs(t.get("amount", 0)) for t in merchant_transactions
        )

        results["till_payment_count"] = len(merchant_transactions)

        till_summary = {}

        for tx in merchant_transactions:
            key = tx.get("merchant_till") or tx.get("display_name")

            if key not in till_summary:
                till_summary[key] = {
                    "merchant": tx.get("party_name"),
                    "till_number": tx.get("merchant_till"),
                    "count": 0,
                    "total": 0.0,
                }

            till_summary[key]["count"] += 1
            till_summary[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_tills"] = sorted(
            till_summary.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 8. MERCHANT CHARGES
        # =====================================================================

        merchant_charge_transactions = []

        merchant_charge_keywords = (
            "merchant payment charge",
            "buy goods charge",
            "merchant transaction charge",
            "merchant fee",
            "merchant payment fee",
        )

        for tx in transactions:
            desc = tx.get("description", "").lower().strip()

            if any(keyword in desc for keyword in merchant_charge_keywords):
                merchant_charge_transactions.append(tx)

        results["total_merchant_charges"] = sum(
            abs(t.get("amount", 0)) for t in merchant_charge_transactions
        )

        results["merchant_charge_count"] = len(merchant_charge_transactions)

        merchant_charge_summary = {}

        for tx in merchant_charge_transactions:
            key = tx.get("display_name") or tx.get("description")

            if key not in merchant_charge_summary:
                merchant_charge_summary[key] = {
                    "merchant": key,
                    "count": 0,
                    "total": 0.0,
                }

            merchant_charge_summary[key]["count"] += 1
            merchant_charge_summary[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_merchant_charges"] = sorted(
            merchant_charge_summary.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]
        # =====================================================================
        # 9. AGENT WITHDRAWALS
        # =====================================================================

        agent_withdrawals = [
            t for t in transactions if t.get("parsed_type") == "withdrawal_agent"
        ]

        results["total_agent_withdrawals"] = sum(
            abs(t.get("amount", 0)) for t in agent_withdrawals
        )

        results["agent_withdrawal_count"] = len(agent_withdrawals)

        withdrawal_locations = {}

        for tx in agent_withdrawals:
            key = tx.get("display_name") or "Unknown Agent"

            if key not in withdrawal_locations:
                withdrawal_locations[key] = {
                    "agent": tx.get("agent_number"),
                    "location": tx.get("agent_location"),
                    "count": 0,
                    "total": 0.0,
                }

            withdrawal_locations[key]["count"] += 1
            withdrawal_locations[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_agent_locations"] = sorted(
            withdrawal_locations.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 10. AGENT DEPOSITS
        # =====================================================================

        agent_deposits = [
            t for t in transactions if t.get("parsed_type") == "deposit_agent"
        ]

        results["total_agent_deposits"] = sum(
            abs(t.get("amount", 0)) for t in agent_deposits
        )

        results["agent_deposit_count"] = len(agent_deposits)

        deposit_locations = {}

        for tx in agent_deposits:
            key = tx.get("display_name") or "Unknown Agent"

            if key not in deposit_locations:
                deposit_locations[key] = {
                    "agent": tx.get("agent_number"),
                    "location": tx.get("agent_location"),
                    "count": 0,
                    "total": 0.0,
                }

            deposit_locations[key]["count"] += 1
            deposit_locations[key]["total"] += abs(tx.get("amount", 0))

        results["top_10_deposit_locations"] = sorted(
            deposit_locations.values(),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 11. FULIZA ANALYSIS
        # =====================================================================

        fuliza_drawn = []
        fuliza_repayments = []

        for tx in transactions:
            desc = tx.get("description", "").lower().strip()

            parsed_type = tx.get("parsed_type")

            if (
                parsed_type == "fuliza_credit"
                or "overdraft of credit party" in desc
                or "fuliza disbursement" in desc
            ):
                fuliza_drawn.append(tx)

            elif (
                parsed_type == "fuliza_repayment"
                or "od loan repayment" in desc
                or "fuliza repayment" in desc
            ):
                fuliza_repayments.append(tx)

        total_drawn = sum(abs(t.get("amount", 0)) for t in fuliza_drawn)

        total_repaid = sum(abs(t.get("amount", 0)) for t in fuliza_repayments)

        cycle_count = min(
            len(fuliza_drawn),
            len(fuliza_repayments),
        )

        same_day_cycles = 0

        repayment_dates = {tx.get("date") for tx in fuliza_repayments}

        for tx in fuliza_drawn:
            if tx.get("date") in repayment_dates:
                same_day_cycles += 1

        results["fuliza_cycles"] = {
            "total_fuliza_drawn": round(total_drawn, 2),
            "total_repaid": round(total_repaid, 2),
            "cycle_count": cycle_count,
            "same_day_repayment_rate": round(
                (same_day_cycles / cycle_count * 100) if cycle_count else 0,
                1,
            ),
            "avg_cycle_amount": round(
                (total_drawn / cycle_count) if cycle_count else 0,
                2,
            ),
            "interpretation": (
                "Severe Fuliza dependency — same-day repayment cycles"
                if cycle_count >= 10
                else "Moderate Fuliza usage" if cycle_count >= 3 else "Low Fuliza usage"
            ),
        }

        # =====================================================================
        # TOP 10 TRANSACTIONS
        # =====================================================================

        top_transactions = sorted(
            transactions,
            key=lambda tx: abs(float(tx.get("amount", 0) or 0)),
            reverse=True,
        )[:10]

        results["top_10_transactions"] = []

        for tx in top_transactions:
            parsed = tx.get("parsed") or {}

            # ---------------------------------------------------------------
            # Build the best description available
            # ---------------------------------------------------------------

            description = (
                tx.get("display_name")
                or parsed.get("name")
                or tx.get("description")
                or ""
            )

            parsed_type = tx.get("parsed_type")

            if parsed_type == "funds_received":
                description = f"Funds received from {parsed.get('name','Unknown')}" + (
                    f" ({parsed['phone']})" if parsed.get("phone") else ""
                )

            elif parsed_type == "sent":
                description = f"Sent to {parsed.get('name','Unknown')}" + (
                    f" ({parsed['phone']})" if parsed.get("phone") else ""
                )

            elif parsed_type == "merchant":
                description = (
                    f"{parsed.get('till')} - {parsed.get('name')}"
                    if parsed.get("till")
                    else parsed.get("name")
                )

            elif parsed_type == "pochi":
                description = (
                    f"{parsed.get('till')} - {parsed.get('name')}"
                    if parsed.get("till")
                    else parsed.get("name")
                )

            elif parsed_type == "paybill":
                description = (
                    f"{parsed.get('paybill')} - {parsed.get('name')}"
                    if parsed.get("paybill")
                    else parsed.get("name")
                )

            elif parsed_type in (
                "withdrawal_agent",
                "deposit_agent",
            ):
                description = (
                    f"{parsed.get('agent')} - {parsed.get('location')}"
                    if parsed.get("agent")
                    else parsed.get("location")
                )

            results["top_10_transactions"].append(
                {
                    "receipt": tx.get("receipt"),
                    "date": tx.get("date"),
                    "time": tx.get("time"),
                    "status": tx.get("status"),
                    "description": description,
                    "amount": abs(float(tx.get("amount", 0) or 0)),
                    "type": tx.get("type"),
                    "category": (parsed_type or tx.get("category") or "other"),
                    "phone": parsed.get("phone"),
                    "merchant_till": parsed.get("till"),
                    "paybill": parsed.get("paybill"),
                    "agent": parsed.get("agent"),
                    "location": parsed.get("location"),
                    "fee": tx.get("fee", 0),
                    "balance": tx.get("balance"),
                }
            )

        # =====================================================================
        # 13. TOP DEPOSITORS
        # =====================================================================

        depositors = defaultdict(float)

        for tx in transactions:
            if tx.get("type") != "income":
                continue

            who = tx.get("display_name") or tx.get("party_name") or "Unknown"

            depositors[who] += abs(tx.get("amount", 0))

        results["top_depositors"] = sorted(
            (
                {
                    "who": who,
                    "amount": round(amount, 2),
                }
                for who, amount in depositors.items()
            ),
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]

        # =====================================================================
        # 14. TOP CREDITORS
        # =====================================================================

        creditors = defaultdict(float)

        for tx in transactions:
            if tx.get("type") != "expense":
                continue

            who = tx.get("display_name") or tx.get("party_name") or "Unknown"

            creditors[who] += abs(tx.get("amount", 0))

        results["top_creditors"] = sorted(
            (
                {
                    "who": who,
                    "amount": round(amount, 2),
                }
                for who, amount in creditors.items()
            ),
            key=lambda x: x["amount"],
            reverse=True,
        )[:10]
        # =====================================================================
        # 15. TOP CUSTOMERS (ALL COUNTERPARTIES)
        # =====================================================================

        customer_totals = {}

        for tx in transactions:
            who = tx.get("display_name") or tx.get("party_name") or "Unknown"

            if who not in customer_totals:
                customer_totals[who] = {
                    "who": who,
                    "phone": tx.get("party_phone"),
                    "income": 0.0,
                    "expenses": 0.0,
                    "transactions": 0,
                    "net": 0.0,
                }

            amount = abs(tx.get("amount", 0))

            customer_totals[who]["transactions"] += 1

            if tx.get("type") == "income":
                customer_totals[who]["income"] += amount
                customer_totals[who]["net"] += amount
            else:
                customer_totals[who]["expenses"] += amount
                customer_totals[who]["net"] -= amount

        results["top_customers"] = sorted(
            customer_totals.values(),
            key=lambda x: (x["income"] + x["expenses"]),
            reverse=True,
        )[:20]

        # =====================================================================
        # 16. MONTHLY SUMMARY
        # =====================================================================

        monthly_summary = {}

        for tx in transactions:
            try:
                month = pd.to_datetime(tx["date"]).strftime("%Y-%m")
            except Exception:
                continue

            if month not in monthly_summary:
                monthly_summary[month] = {
                    "month": month,
                    "income": 0.0,
                    "expenses": 0.0,
                    "transactions": 0,
                    "merchant": 0.0,
                    "paybill": 0.0,
                    "pochi": 0.0,
                    "individual": 0.0,
                    "fuliza": 0.0,
                    "withdrawals": 0.0,
                    "deposits": 0.0,
                }

            amount = abs(tx.get("amount", 0))

            monthly_summary[month]["transactions"] += 1

            if tx.get("type") == "income":
                monthly_summary[month]["income"] += amount
            else:
                monthly_summary[month]["expenses"] += amount

            parsed_type = tx.get("parsed_type")

            if parsed_type == "merchant":
                monthly_summary[month]["merchant"] += amount

            elif parsed_type == "paybill":
                monthly_summary[month]["paybill"] += amount

            elif parsed_type == "pochi":
                monthly_summary[month]["pochi"] += amount

            elif parsed_type == "sent":
                monthly_summary[month]["individual"] += amount

            elif parsed_type in (
                "fuliza_credit",
                "fuliza_repayment",
            ):
                monthly_summary[month]["fuliza"] += amount

            elif parsed_type == "withdrawal_agent":
                monthly_summary[month]["withdrawals"] += amount

            elif parsed_type == "deposit_agent":
                monthly_summary[month]["deposits"] += amount

        results["monthly_transaction_summary"] = sorted(
            monthly_summary.values(),
            key=lambda x: x["month"],
        )

        # =====================================================================
        # 17. OVERALL STATISTICS
        # =====================================================================

        amounts = [abs(t.get("amount", 0)) for t in transactions]

        if amounts:
            results["largest_transaction"] = max(amounts)
            results["smallest_transaction"] = min(amounts)
            results["average_transaction"] = round(
                sum(amounts) / len(amounts),
                2,
            )
            results["median_transaction"] = round(
                statistics.median(amounts),
                2,
            )
        else:
            results["largest_transaction"] = 0
            results["smallest_transaction"] = 0
            results["average_transaction"] = 0
            results["median_transaction"] = 0

        results["income_transaction_count"] = sum(
            1 for t in transactions if t.get("type") == "income"
        )

        results["expense_transaction_count"] = sum(
            1 for t in transactions if t.get("type") == "expense"
        )

        results["largest_income"] = max(
            (
                abs(t.get("amount", 0))
                for t in transactions
                if t.get("type") == "income"
            ),
            default=0,
        )

        results["largest_expense"] = max(
            (
                abs(t.get("amount", 0))
                for t in transactions
                if t.get("type") == "expense"
            ),
            default=0,
        )

        # =====================================================================
        # 18. TRANSACTION TYPE BREAKDOWN
        # =====================================================================

        type_breakdown = {}

        for tx in transactions:
            tx_type = tx.get("parsed_type") or "unknown"

            if tx_type not in type_breakdown:
                type_breakdown[tx_type] = {
                    "type": tx_type,
                    "count": 0,
                    "total": 0.0,
                }

            type_breakdown[tx_type]["count"] += 1
            type_breakdown[tx_type]["total"] += abs(tx.get("amount", 0))

        results["transaction_type_breakdown"] = sorted(
            type_breakdown.values(),
            key=lambda x: x["total"],
            reverse=True,
        )

        # =====================================================================
        # 19. DAILY SPENDING
        # =====================================================================

        daily_spending = defaultdict(float)

        for tx in transactions:
            if tx.get("type") != "expense":
                continue

            daily_spending[tx.get("date")] += abs(tx.get("amount", 0))

        results["daily_spending"] = [
            {
                "date": date,
                "amount": amount,
            }
            for date, amount in sorted(daily_spending.items())
        ]

        # =====================================================================
        # 20. SUMMARY TOTALS
        # =====================================================================

        results["total_income"] = round(
            sum(
                abs(t.get("amount", 0))
                for t in transactions
                if t.get("type") == "income"
            ),
            2,
        )

        results["total_expenses"] = round(
            sum(
                abs(t.get("amount", 0))
                for t in transactions
                if t.get("type") == "expense"
            ),
            2,
        )

        results["net_cash_flow"] = round(
            results["total_income"] - results["total_expenses"],
            2,
        )

        results["total_transactions"] = len(transactions)

        # =====================================================================
        # RETURN RESULTS
        # =====================================================================

        logger.info("✅ Detailed transaction metrics generated successfully.")

        return results

    # ─── Classification ───────────────────────────────────────────────────────
    def _classify_transaction(self, tx: Dict[str, Any]) -> Dict[str, str]:
        """Classify a single transaction using category rules."""
        desc = (tx.get("description") or "").lower()
        for pattern, category, subcategory, direction in CATEGORY_RULES:
            if re.search(pattern, desc):
                return {
                    "category": category,
                    "subcategory": subcategory,
                    "direction": direction,
                }
        direction = "in" if tx.get("type") == "income" else "out"
        return {"category": "other", "subcategory": "other", "direction": direction}

    # ─── Monthly breakdown ────────────────────────────────────────────────────
    def _monthly_breakdown(
        self,
        transactions: List[Dict[str, Any]],
        classified: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Calculate monthly income and expense breakdown."""
        months: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"income": 0.0, "expenses": 0.0, "transaction_count": 0}
        )
        for tx, cls in zip(transactions, classified):
            raw_date = str(tx.get("date", ""))
            month = raw_date[:7] if len(raw_date) >= 7 else "unknown"
            amount = float(tx.get("amount", 0) or 0)
            months[month]["transaction_count"] += 1
            if cls["direction"] == "in":
                months[month]["income"] += amount
            else:
                months[month]["expenses"] += amount

        result = []
        for month, data in sorted(months.items()):
            result.append(
                {
                    "month": month,
                    "income": round(data["income"], 2),
                    "expenses": round(data["expenses"], 2),
                    "balance": round(data["income"] - data["expenses"], 2),
                    "transaction_count": data["transaction_count"],
                }
            )
        return result

    # ─── Version 2 Health Score ──────────────────────────────────────────────
    def _calculate_health_score_v2(
        self,
        fuliza_cycles: Dict[str, Any],
        income_sources: Dict[str, Any],
        savings_rate: float,
        betting_pct: float,
        total_transactions: int,
    ) -> Tuple[int, Dict[str, int]]:
        """
        Enhanced health score that penalises:
        1. Same-day Fuliza cycling (more dangerous than just Fuliza count)
        2. Loan disguised as income (false financial health)
        3. Negative savings rate
        """
        breakdown = {}

        same_day_rate = fuliza_cycles["same_day_repayment_rate"]
        cycle_count = fuliza_cycles["cycle_count"]

        if same_day_rate > 70:
            breakdown["fuliza_dependency"] = -30
        elif same_day_rate > 40:
            breakdown["fuliza_dependency"] = -15
        elif cycle_count > 0:
            breakdown["fuliza_dependency"] = -5
        else:
            breakdown["fuliza_dependency"] = 15

        loan_pct = income_sources.get("loan_as_pct_of_total_inflow", 0)
        if loan_pct > 20:
            breakdown["income_quality"] = -20
        elif loan_pct > 5:
            breakdown["income_quality"] = -5
        else:
            breakdown["income_quality"] = 15

        if savings_rate >= 10:
            breakdown["savings_rate"] = 20
        elif savings_rate >= 5:
            breakdown["savings_rate"] = 10
        elif savings_rate >= 0:
            breakdown["savings_rate"] = 0
        else:
            breakdown["savings_rate"] = -10

        if betting_pct == 0:
            breakdown["betting"] = 15
        elif betting_pct < 5:
            breakdown["betting"] = 8
        else:
            breakdown["betting"] = -20

        if total_transactions >= 30:
            breakdown["transaction_volume"] = 5
        elif total_transactions >= 10:
            breakdown["transaction_volume"] = 2
        else:
            breakdown["transaction_volume"] = 0

        score = max(0, min(100, 50 + sum(breakdown.values())))
        return score, breakdown

    # ─── Day-of-week pattern ──────────────────────────────────────────────────
    def _day_of_week_pattern(
        self,
        transactions: List[Dict[str, Any]],
        classified: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Calculate spending by day of week."""
        dow: Dict[int, float] = defaultdict(float)
        dow_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        for tx, cls in zip(transactions, classified):
            if cls["direction"] != "out":
                continue
            raw = str(tx.get("date", ""))
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    d = datetime.strptime(raw, fmt)
                    dow[d.weekday()] += float(tx.get("amount", 0) or 0)
                    break
                except ValueError:
                    continue
        return [
            {"day": dow_names[i], "spend": round(dow.get(i, 0.0), 2)} for i in range(7)
        ]

    # ─── Salary day detection ─────────────────────────────────────────────────
    def _detect_salary_day(
        self,
        transactions: List[Dict[str, Any]],
        classified: List[Dict[str, str]],
    ) -> Optional[int]:
        """Detect the most common salary day of month."""
        salary_days: List[int] = []
        for tx, cls in zip(transactions, classified):
            if cls["subcategory"] != "salary":
                continue
            raw = str(tx.get("date", ""))
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    salary_days.append(datetime.strptime(raw, fmt).day)
                    break
                except ValueError:
                    continue
        if not salary_days:
            return None
        return max(set(salary_days), key=salary_days.count)

    # ─── Recurring detection ──────────────────────────────────────────────────
    def _detect_recurring(
        self,
        transactions: List[Dict[str, Any]],
        classified: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Detect recurring payments based on description and amount consistency."""
        groups: Dict[str, List[float]] = defaultdict(list)
        for tx, cls in zip(transactions, classified):
            if cls["direction"] != "out":
                continue
            desc = (tx.get("description") or "")[:40].strip()
            amount = float(tx.get("amount", 0) or 0)
            if amount > 0:
                groups[desc].append(amount)

        recurring = []
        for desc, amounts in groups.items():
            if len(amounts) < 2:
                continue
            avg = mean(amounts)
            cv = stdev(amounts) / avg if len(amounts) > 1 and avg > 0 else 0
            if cv < 0.15:
                recurring.append(
                    {
                        "description": desc,
                        "average_amount": round(avg, 2),
                        "occurrences": len(amounts),
                        "total": round(sum(amounts), 2),
                    }
                )
        return sorted(recurring, key=lambda x: x["total"], reverse=True)[:10]

    # ─── Anomaly detection ────────────────────────────────────────────────────
    def _detect_anomalies(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect unusually large transactions (outliers)."""
        amounts = [float(tx.get("amount", 0) or 0) for tx in transactions]
        if len(amounts) < 3:
            return []
        avg = mean(amounts)
        sd = stdev(amounts)
        threshold = avg + 2 * sd

        anomalies = []
        for tx in transactions:
            amount = float(tx.get("amount", 0) or 0)
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

    # ─── Insights ─────────────────────────────────────────────────────────────
    def _generate_insights(
        self,
        total_income: float,
        total_expenses: float,
        net_cash_flow: float,
        savings_rate: float,
        top_category: str,
        top_category_pct: float,
        betting_pct: float,
        fuliza_count: int,
        fuliza_total: float,
        burn_rate: float,
        health_score: int,
        salary_day: Optional[int],
        recurring: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate actionable insights from the data."""
        insights = []

        direction = "positive" if net_cash_flow >= 0 else "negative"
        insights.append(
            f"Your net cash flow is {direction}: KES {abs(net_cash_flow):,.0f} "
            f"({'surplus' if net_cash_flow >= 0 else 'deficit'}) "
            f"with a {savings_rate:.1f}% savings rate."
        )

        insights.append(
            f"Your biggest spending category is {top_category} "
            f"({top_category_pct:.1f}% of total spend, "
            f"KES {total_expenses * top_category_pct / 100:,.0f})."
        )

        if salary_day:
            insights.append(
                f"Your salary typically arrives around day {salary_day} of the month. "
                f"Plan your large payments (rent, bills) for the days immediately after."
            )

        if burn_rate > 0:
            insights.append(
                f"You spend approximately KES {burn_rate:,.0f} per day. "
                f"At this rate, KES 10,000 lasts about {10000/burn_rate:.0f} days."
            )
        else:
            insights.append("No expense data available to calculate burn rate.")

        if recurring:
            top_r = recurring[0]
            insights.append(
                f"Your largest recurring payment is '{top_r['description']}' "
                f"averaging KES {top_r['average_amount']:,.0f} "
                f"({top_r['occurrences']} times)."
            )

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

    # ─── Warnings ─────────────────────────────────────────────────────────────
    def _generate_warnings(
        self,
        betting_pct: float,
        fuliza_count: int,
        fuliza_total: float,
        total_income: float,
        savings_rate: float,
        anomalies: List[Dict[str, Any]],
        fee_pct: float,
        income_analysis: Dict[str, Any] = None,
    ) -> List[str]:
        """Generate warning messages for concerning patterns."""
        warnings = []

        if betting_pct > 20:
            warnings.append(
                f"🚨 Betting accounts for {betting_pct:.1f}% of your total spend "
                f"(KES {total_income * betting_pct / 100:,.0f}). "
                f"This is significantly impacting your financial health."
            )
        elif betting_pct > 5:
            warnings.append(
                f"⚠️  Betting is {betting_pct:.1f}% of your spend. "
                f"Consider reducing this to below 5%."
            )

        if fuliza_count > 5:
            warnings.append(
                f"🚨 You used Fuliza {fuliza_count} times (KES {fuliza_total:,.0f} total). "
                f"Frequent Fuliza use indicates cash flow gaps — consider an emergency fund."
            )
        elif fuliza_count > 0:
            warnings.append(
                f"⚠️  {fuliza_count} Fuliza usage(s) detected. "
                f"Reducing reliance on credit improves your score."
            )

        if savings_rate < 0:
            warnings.append(
                "🚨 You are spending more than you earn. "
                "Review your expenses immediately to avoid debt accumulation."
            )
        elif savings_rate < 5:
            warnings.append(
                f"⚠️  Your savings rate is only {savings_rate:.1f}%. "
                f"Aim for at least 10% (KES {total_income * 0.10:,.0f}/month)."
            )

        if fee_pct > 5:
            warnings.append(
                f"⚠️  M-PESA fees are {fee_pct:.1f}% of your income. "
                f"Use Mpesa Ratiba or bank transfers for large amounts to save on fees."
            )

        if anomalies:
            warnings.append(
                f"⚠️  {len(anomalies)} unusually large transaction(s) detected. "
                f"Largest: KES {anomalies[0]['amount']:,.0f} on {anomalies[0]['date']}."
            )

        if income_analysis and income_analysis.get("loan_disbursement_warning"):
            loan_pct = income_analysis.get("loan_as_pct_of_total_inflow", 0)
            if loan_pct > 20:
                warnings.append(
                    f"🚨 {loan_pct:.1f}% of your 'income' is actually loan disbursements. "
                    f"This masks your true financial position."
                )
            elif loan_pct > 5:
                warnings.append(
                    f"⚠️  {loan_pct:.1f}% of inflows are loan disbursements. "
                    f"Don't treat loans as income."
                )

        return warnings

    # ─── Recommendations ──────────────────────────────────────────────────────
    def _generate_recommendations(
        self,
        savings_rate: float,
        betting_pct: float,
        fuliza_count: int,
        top_category: str,
        top_category_pct: float,
        recurring: List[Dict[str, Any]],
        health_score: int,
    ) -> List[str]:
        """Generate concrete recommendations."""
        recs = []

        if savings_rate < 10:
            target = max(10.0, savings_rate + 5)
            recs.append(
                f"Set up automatic savings of {target:.0f}% of each income received. "
                f"Use M-Shwari Lock Savings to make it harder to spend."
            )

        if betting_pct > 5:
            recs.append(
                f"Reduce betting from {betting_pct:.1f}% to under 5% of spend. "
                f"Redirect those funds to a Sacco or money market fund."
            )

        if fuliza_count > 0:
            recs.append(
                "Build a KES 5,000–10,000 emergency buffer in M-Shwari to eliminate "
                "Fuliza dependency. Even KES 200/day savings builds this in 25–50 days."
            )

        if top_category_pct > 30:
            recs.append(
                f"Your top category ({top_category}) is {top_category_pct:.1f}% of spend. "
                f"Set a monthly budget cap and track it weekly."
            )

        if recurring:
            total_recurring = sum(r["total"] for r in recurring[:5])
            recs.append(
                f"You have KES {total_recurring:,.0f} in recurring payments. "
                f"Review each one — cancel any subscriptions you no longer use."
            )

        recs.append(
            "Use the 50/30/20 rule adapted for Kenya: "
            "50% needs (rent, food, transport), 30% wants, 20% savings/investment."
        )

        return recs[:5]

    # ─── Helpers ──────────────────────────────────────────────────────────────
    def _mom_change(self, monthly_data: List[Dict[str, Any]], key: str) -> float:
        """Calculate month-over-month percentage change."""
        if len(monthly_data) < 2:
            return 0.0
        prev = monthly_data[-2].get(key, 0) or 0
        curr = monthly_data[-1].get(key, 0) or 0
        if prev == 0:
            return 0.0
        return round((curr - prev) / prev * 100, 2)

    def _prepare_transaction_data(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prepare transaction data for AI prompt."""
        return [
            {
                "date": str(tx.get("date", "")),
                "description": str(tx.get("description", ""))[:80],
                "amount": float(tx.get("amount", 0) or 0),
                "type": str(tx.get("type", "unknown")),
                "balance": float(tx.get("balance", 0) or 0),
            }
            for tx in transactions[:200]
        ]

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from AI response, handling markdown code blocks."""
        clean = re.sub(r"```json\s*", "", text or "")
        clean = re.sub(r"```\s*", "", clean).strip()
        return json.loads(clean)

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
            "detailed_transaction_metrics": {
                "top_10_paid_in": [],
                "top_10_paid_in_sum": 0,
                "top_10_withdrawals": [],
                "top_10_withdrawals_sum": 0,
                "paybill_total": 0,
                "paybill_count": 0,
                "paybill_breakdown": [],
                "total_transfer_charges": 0,
                "transfer_charge_count": 0,
                "total_sent_to_individuals": 0,
                "individual_transfer_count": 0,
                "top_10_individual_recipients": [],
                "total_pochi_la_biashara": 0,
                "pochi_la_biashara_count": 0,
                "top_10_small_businesses": [],
                "total_till_payments": 0,
                "till_payment_count": 0,
                "top_10_tills": [],
                "total_merchant_charges": 0,
                "merchant_charge_count": 0,
                "top_10_merchant_charges": [],
                "total_agent_withdrawals": 0,
                "agent_withdrawal_count": 0,
                "top_10_agent_locations": [],
                "total_agent_deposits": 0,
                "agent_deposit_count": 0,
                "top_10_deposit_locations": [],
                "total_fuliza_drawn": 0,
                "fuliza_count": 0,
                "total_fuliza_repaid": 0,
                "fuliza_repayment_count": 0,
                "fuliza_utilization_rate": 0,
                "top_10_transactions_by_amount": [],
                "top_customers_by_transaction_amount": [],
                "monthly_summary": [],
            },
        }

    def _parse_transaction_details(self, description: str) -> dict[str, Any]:
        """
        Extract structured information from an M-PESA transaction description.
        """

        desc = re.sub(r"\s+", " ", (description or "")).strip()

        result = {
            "type": "unknown",
            "name": None,
            "phone": None,
            "till": None,
            "paybill": None,
            "agent": None,
            "location": None,
        }

        patterns = [
            # ---------------------------------------------------------
            # Funds received
            # Funds received from - 254712345678 JOHN DOE
            # Funds received from 0712345678 JOHN DOE
            # Funds received from JOHN DOE
            # ---------------------------------------------------------
            (
                "funds_received",
                r"^Funds received from\s*-?\s*(?:(?P<phone>(?:254|0)\d{9})\s+)?(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Sent to individual
            # Sent to 254712345678 JOHN DOE
            # ---------------------------------------------------------
            (
                "sent",
                r"^Sent to\s+(?P<phone>(?:254|0)\d{9})\s+(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Merchant / Buy Goods
            # Merchant Payment to 7679753 - SHOP
            # Merchant Payment Fuliza M-Pesa to 7679753 - SHOP
            # Merchant Payment to 7679753 SHOP
            # ---------------------------------------------------------
            (
                "merchant",
                r"^Merchant Payment(?: Fuliza M-Pesa)? to\s+"
                r"(?P<till>\d+)"
                r"(?:\s*-\s*|\s+)"
                r"(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Pochi
            # ---------------------------------------------------------
            (
                "pochi",
                r"^Customer Payment to Small Business(?: to)?\s+"
                r"(?P<till>\d+)"
                r"(?:\s*-\s*|\s+)"
                r"(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Paybill
            # Pay Bill Online to 247247 - SAFARICOM
            # Pay Bill to 247247 SAFARICOM
            # ---------------------------------------------------------
            (
                "paybill",
                r"^Pay Bill(?: Online)? to\s+"
                r"(?P<paybill>\d+)"
                r"(?:\s*-\s*|\s+)"
                r"(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Withdrawal at agent
            # ---------------------------------------------------------
            (
                "withdrawal_agent",
                r"^(?:Withdrawal at Agent|Agent Withdrawal)\s+"
                r"(?:(?P<agent>\d+)"
                r"(?:\s*-\s*|\s+))?"
                r"(?P<location>.+)$",
            ),
            # ---------------------------------------------------------
            # Deposit at agent
            # ---------------------------------------------------------
            (
                "deposit_agent",
                r"^(?:Deposit at Agent|Agent Deposit)\s+"
                r"(?:(?P<agent>\d+)"
                r"(?:\s*-\s*|\s+))?"
                r"(?P<location>.+)$",
            ),
            # ---------------------------------------------------------
            # Airtime
            # ---------------------------------------------------------
            (
                "airtime",
                r"^Airtime Purchase.*?(?P<phone>(?:254|0)\d{9})?$",
            ),
            # ---------------------------------------------------------
            # Fuliza repayment
            # ---------------------------------------------------------
            (
                "fuliza_repayment",
                r"^OD Loan Repayment to\s+(?P<paybill>\d+)\s*-\s*(?P<name>.+)$",
            ),
            # ---------------------------------------------------------
            # Overdraft credit
            # ---------------------------------------------------------
            (
                "fuliza_credit",
                r"^OverDraft of Credit Party$",
            ),
        ]

        for tx_type, pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)

            if not match:
                continue

            result["type"] = tx_type

            for key, value in match.groupdict().items():
                if value is None:
                    continue

                value = value.strip(" -")

                if key == "phone":
                    value = value.replace(" ", "")

                result[key] = value

            return result

        # Fallback
        result["name"] = desc

        return result
