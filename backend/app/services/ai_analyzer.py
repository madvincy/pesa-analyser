import os
import json
import asyncio
import re
import logging
import concurrent.futures
from collections import defaultdict
from datetime import datetime
from statistics import mean, stdev
from typing import Dict, List, Any, Optional, Tuple, Callable, Awaitable

logger = logging.getLogger(__name__)


# ─── Kenyan PayBill → Merchant lookup ────────────────────────────────────────
KNOWN_PAYBILLS: Dict[str, Tuple[str, str, str]] = {
    "888880": ("KPLC Prepaid",        "utilities",     "electricity"),
    "888884": ("KPLC Postpaid",       "utilities",     "electricity"),
    "888861": ("Nairobi Water",       "utilities",     "water"),
    "200222": ("KCB Bank",            "finance",       "bank_transfer"),
    "522522": ("Equity Bank",         "finance",       "bank_transfer"),
    "400200": ("DSTV",                "entertainment", "subscription"),
    "969696": ("Safaricom Data",      "airtime",       "mobile_data"),
    "290290": ("Fuliza Repay",        "loan",          "fuliza_repayment"),
    "300300": ("M-Shwari",            "loan",          "mshwari"),
    "601600": ("Zuku",                "utilities",     "internet"),
    "802900": ("Faiba",               "utilities",     "internet"),
    "185185": ("Startimes",           "entertainment", "subscription"),
    "111222": ("Stanbic Bank",        "finance",       "bank_transfer"),
    "303030": ("NCBA Bank",           "finance",       "bank_transfer"),
}

# ─── Category rules: (pattern, category, subcategory, direction) ─────────────
CATEGORY_RULES: List[Tuple[str, str, str, str]] = [
    (r"received from",                    "income",        "peer_transfer",     "in"),
    (r"salary|wages|payroll",             "income",        "salary",            "in"),
    (r"reversal",                         "income",        "reversal",          "in"),
    (r"pay bill received|paybill received","income",       "business_receipt",  "in"),
    (r"mshwari deposit|m-shwari deposit", "income",        "mshwari",           "in"),
    (r"sent to|transfer to",              "transfer",      "peer_transfer",     "out"),
    (r"kplc|kenya power",                 "utilities",     "electricity",       "out"),
    (r"nairobi water|nwsc",               "utilities",     "water",             "out"),
    (r"zuku|faiba|safaricom home",        "utilities",     "internet",          "out"),
    (r"dstv|startimes|showmax|netflix",   "entertainment", "subscription",      "out"),
    (r"fuliza",                           "loan",          "fuliza",            "out"),
    (r"fuliza repay|repay fuliza",        "loan",          "fuliza_repayment",  "out"),
    (r"m-shwari|mshwari",                 "loan",          "mshwari",           "out"),
    (r"kcb mpesa|kcb m-pesa",             "loan",          "kcb_mpesa",         "out"),
    (r"withdraw.*agent|agent.*withdraw",  "cash",          "withdrawal",        "out"),
    (r"airtime|scratch card",             "airtime",       "airtime",           "out"),
    (r"data bundle|data pack",            "airtime",       "data",              "out"),
    (r"uber|bolt|little cab|faras",       "transport",     "ride_hailing",      "out"),
    (r"fuel|petrol|diesel|total energies|kenol|rubis", "transport", "fuel",    "out"),
    (r"matatu|bus|sacco",                 "transport",     "public_transport",  "out"),
    (r"naivas|quickmart|carrefour|chandarana|cleanshelf|uchumi",
                                          "food",          "grocery",           "out"),
    (r"java|kfc|chicken inn|pizza|burger|cafe|restaurant|hotel",
                                          "food",          "dining",            "out"),
    (r"jumia|kilimall|amazon",            "shopping",      "ecommerce",         "out"),
    (r"buy goods|till",                   "shopping",      "till_payment",      "out"),
    (r"hospital|clinic|pharmacy|chemist|doctor|nhif",
                                          "health",        "medical",           "out"),
    (r"school|university|college|tuition|kcse|knec",
                                          "education",     "tuition",           "out"),
    (r"sportpesa|betika|shabiki|mcheza|odibets|premiumbetting",
                                          "betting",       "betting",           "out"),
    (r"sacco|chama|investment|shares|nse|cma",
                                          "savings",       "investment",        "out"),
    (r"mshwari lock|fixed deposit",       "savings",       "fixed_deposit",     "out"),
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
            "phone": re.compile(r'(\+?254|0)?[7-9]\d{8}\b'),
            "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            "receipt": re.compile(r'^([A-Z0-9]{10})\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$'),
            "amount": re.compile(r'(Completed|Failed|Pending|Complete)\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s*$'),
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
                logger.info(f"✅ {name.capitalize()} API key configured")
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
        transactions = self._extract_transactions(text)
        result = self._deterministic_analysis(transactions, statement_type)

        try:
            ai_result = await self._try_ai_providers(transactions, statement_type, result)
            if ai_result:
                logger.info("✅ AI enrichment successful, merging results")
                result.update(ai_result)
            else:
                logger.info("ℹ️  AI enrichment returned no results, using deterministic analysis")
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            logger.info("ℹ️  Continuing with deterministic analysis only")

        return result

    async def analyze_transactions(
        self,
        transactions: List[Dict[str, Any]],
        statement_type: str = "unknown"
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

        logger.info(f"🔵 Analyzing {len(transactions)} pre-parsed transactions")

        result = self._deterministic_analysis(transactions, statement_type)

        try:
            ai_result = await self._try_ai_providers(transactions, statement_type, result)
            if ai_result:
                logger.info("✅ AI enrichment successful, merging results")
                result.update(ai_result)
            else:
                logger.info("ℹ️  AI enrichment returned no results, using deterministic analysis")
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            logger.info("ℹ️  Continuing with deterministic analysis only")

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
        if not transactions:
            empty = self._empty_result()
            if on_stage:
                await on_stage("basic_summary", empty)
            return empty

        logger.info(f"🔵 Running staged analysis on {len(transactions)} transactions")

        # The deterministic pass itself is a single cheap O(n) computation —
        # we're not re-running it per stage, just revealing pre-computed
        # pieces of it in order so the frontend can render progressively
        # instead of blocking on the slow AI call at the very end.
        full = self._deterministic_analysis(transactions, statement_type)

        basic_summary = {
            k: full[k] for k in (
                "total_income", "total_expenses", "net_cash_flow", "average_balance",
                "savings_rate", "burn_rate_daily", "total_fees", "fee_pct",
                "fuliza_total", "fuliza_count", "betting_total", "betting_pct",
                "p2p_total", "p2p_count", "highest_transaction",
                "highest_transaction_date", "total_transactions", "transaction_count",
            )
        }
        if on_stage:
            await on_stage("basic_summary", basic_summary)

        category_breakdown = {
            k: full[k] for k in (
                "category_data", "monthly_data", "trend_data",
                "top_category", "top_category_amount", "top_category_percent",
                "top_income_source", "income_concentration",
                "top_depositors", "top_creditors",
            )
        }
        if on_stage:
            await on_stage("category_breakdown", category_breakdown)

        behavior_metrics = {
            k: full[k] for k in (
                "health_score", "health_breakdown", "fuliza_cycles",
                "income_analysis", "day_of_week_spend", "salary_day",
                "recurring_payments", "anomalies",
            )
        }
        if on_stage:
            await on_stage("behavior_metrics", behavior_metrics)

        insights_stage = {
            k: full[k] for k in (
                "insights", "warnings", "recommendations",
                "income_change", "expenses_change",
            )
        }
        if on_stage:
            await on_stage("insights", insights_stage)

        # ─── Slowest step: AI enrichment (real network calls) ───────────────
        try:
            ai_result = await self._try_ai_providers(transactions, statement_type, full)
            if ai_result:
                logger.info("✅ AI enrichment successful — merging + re-pushing insights")
                full.update(ai_result)
                enriched_keys = [
                    k for k in (
                        "insights", "warnings", "recommendations",
                        "income_change", "expenses_change",
                        "top_income_source", "income_concentration",
                    )
                    if k in full
                ]
                enriched_insights = {k: full[k] for k in enriched_keys}
                if on_stage:
                    await on_stage("insights", enriched_insights)
            else:
                logger.info("ℹ️  AI enrichment returned no results — deterministic insights stand")
        except Exception as e:
            logger.warning(f"⚠️  AI enrichment failed: {e}")
            logger.info("ℹ️  Continuing with deterministic insights only")

        return full

    # ─── Transaction Extraction ──────────────────────────────────────────────
    def _extract_transactions(self, text: str) -> List[Dict[str, Any]]:
        """
        Parses the official Safaricom M-PESA statement format.

        Key insight: transactions sharing the same Receipt No. are sub-legs
        of ONE logical event (e.g. Fuliza drawdown + fee + overdraft credit).
        We group by receipt, then classify the GROUP, not each leg.
        """
        transactions: List[Dict[str, Any]] = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        receipt_start = self.patterns["receipt"]
        amount_pattern = self.patterns["amount"]

        # ── Step 1: parse every leg, grouped by receipt number ─────────────
        receipt_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        i = 0
        while i < len(lines):
            match = receipt_start.match(lines[i])
            if not match:
                i += 1
                continue

            receipt, date_str, time_str, rest = match.groups()
            block_lines = [rest]
            j = i + 1
            has_amounts = bool(amount_pattern.search(rest))

            while j < len(lines) and not has_amounts:
                next_line = lines[j]
                if receipt_start.match(next_line):
                    break
                block_lines.append(next_line)
                has_amounts = bool(amount_pattern.search(next_line))
                j += 1

            full_text = " ".join(block_lines)
            amt_match = amount_pattern.search(full_text)

            if amt_match:
                status, amount_str, balance_str = amt_match.groups()
                details = re.sub(r'\s+', ' ', full_text[:amt_match.start()].strip())
                try:
                    amount = float(amount_str.replace(",", ""))
                    balance = float(balance_str.replace(",", ""))
                    receipt_groups[receipt].append({
                        "date": date_str,
                        "time": time_str,
                        "description": details,
                        "amount": amount,  # signed
                        "balance": balance,
                        "status": status,
                    })
                except ValueError:
                    pass

            i = j if j > i else i + 1

        # ── Step 2: classify each receipt GROUP as one logical event ───────
        for receipt, legs in receipt_groups.items():
            if not legs:
                continue

            mechanic_keywords = ["overdraft of credit party", "pay merchant charge",
                                 "pay bill charge", "withdrawal charge",
                                 "customer transfer of funds charge"]

            primary = None
            fee_total = 0.0
            is_fuliza = False

            for leg in legs:
                desc_lower = leg["description"].lower()
                is_mechanic = any(kw in desc_lower for kw in mechanic_keywords)

                if "fuliza" in desc_lower or "overdraft" in desc_lower or "od loan" in desc_lower:
                    is_fuliza = True

                if "charge" in desc_lower and is_mechanic:
                    fee_total += abs(leg["amount"])
                    continue

                if not is_mechanic and primary is None:
                    primary = leg

            if primary is None:
                primary = max(legs, key=lambda l: abs(l["amount"]))

            amount = primary["amount"]
            is_income = amount > 0
            tx_type = "income" if is_income else "expense"

            tx: Dict[str, Any] = {
                "date": primary["date"],
                "time": primary["time"],
                "description": primary["description"],
                "amount": abs(amount),
                "balance": primary["balance"],
                "type": tx_type,
                "receipt": receipt,
                "status": primary["status"],
                "fee": fee_total,
            }

            if is_fuliza:
                tx["fuliza"] = True
                tx["category"] = "Fuliza"

            desc_lower = primary["description"].lower()

            if "salary payment" in desc_lower:
                tx["category"] = "Salary"
            elif "funds received" in desc_lower or "received from" in desc_lower:
                tx["category"] = tx.get("category", "Received Money")
            elif "agent" in desc_lower and "withdraw" in desc_lower:
                tx["category"] = "Agent Withdrawal"
            elif "deposit of funds at agent" in desc_lower:
                tx["category"] = "Agent Deposit"
            elif "pay bill" in desc_lower:
                tx["category"] = tx.get("category", "PayBill")
                paybill_match = re.search(r'to (\d{4,7})', primary["description"])
                if paybill_match:
                    tx["paybill"] = paybill_match.group(1)
            elif "merchant payment" in desc_lower or "buy goods" in desc_lower:
                tx["category"] = tx.get("category", "Buy Goods")
                till_match = re.search(r'to (\d{4,7})', primary["description"])
                if till_match:
                    tx["till"] = till_match.group(1)
            elif "customer transfer" in desc_lower or "customer send money" in desc_lower:
                tx["category"] = tx.get("category", "Send Money")
            elif "business payment" in desc_lower:
                tx["category"] = tx.get("category", "Business Payment")
            elif "international transfer" in desc_lower:
                tx["category"] = "International Transfer"
            elif "promotion payment" in desc_lower:
                tx["category"] = "Promotion/Reward"
            elif "airtime" in desc_lower:
                tx["category"] = "Airtime"
            elif "bundle purchase" in desc_lower:
                tx["category"] = "Data Bundle"
            elif "m-shwari" in desc_lower:
                tx["category"] = "M-Shwari"

            phone_match = self.patterns["phone"].search(primary["description"])
            if phone_match:
                tx["phone"] = phone_match.group()

            transactions.append(tx)

        transactions.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
        logger.info(f"📊 Extracted {len(transactions)} logical transactions from {len(receipt_groups)} receipts")
        return transactions

    # ─── Fuliza Cycle Detection ──────────────────────────────────────────────
    def _detect_fuliza_cycles(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detects the drawdown→repayment pattern visible throughout this statement.
        A 'cycle' = a Fuliza-tagged expense followed within minutes by an
        OD Loan Repayment of a similar amount, funded by a fresh deposit.
        """
        fuliza_legs = [t for t in transactions if t.get("fuliza")]
        repayments = [t for t in transactions
                      if "od loan repayment" in t["description"].lower()]

        total_drawn = sum(t["amount"] for t in fuliza_legs)
        total_repaid = sum(t["amount"] for t in repayments)
        cycle_count = len(repayments)

        same_day_cycles = 0
        for r in repayments:
            r_date = r["date"]
            same_day_drawdowns = [
                f for f in fuliza_legs if f["date"] == r_date
            ]
            if same_day_drawdowns:
                same_day_cycles += 1

        return {
            "total_fuliza_drawn": round(total_drawn, 2),
            "total_repaid": round(total_repaid, 2),
            "cycle_count": cycle_count,
            "same_day_repayment_rate": round(
                same_day_cycles / cycle_count * 100, 1
            ) if cycle_count else 0,
            "avg_cycle_amount": round(
                total_drawn / cycle_count, 2
            ) if cycle_count else 0,
            "interpretation": (
                "Severe Fuliza dependency — same-day repayment cycles"
                if same_day_cycles / max(cycle_count, 1) > 0.7
                else "Moderate Fuliza usage"
            )
        }

    # ─── Income Source Classification ────────────────────────────────────────
    def _classify_income_sources(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            "loan_as_pct_of_total_inflow": round(
                loan_total / (loan_total + true_income_total) * 100, 1
            ) if (loan_total + true_income_total) > 0 else 0,
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
        Perform deterministic (non-AI) analysis of transactions.
        This always runs and provides baseline results.
        """
        if not transactions:
            logger.warning("⚠️  No transactions passed to _deterministic_analysis")
            return self._empty_result()

        logger.info(f"🔵 Running deterministic analysis on {len(transactions)} txns")

        classified = [self._classify_transaction(tx) for tx in transactions]

        total_income: float = 0.0
        total_expenses: float = 0.0
        total_fees: float = 0.0
        fuliza_total: float = 0.0
        fuliza_count: int = 0
        betting_total: float = 0.0
        p2p_total: float = 0.0
        p2p_count: int = 0
        highest_tx: float = 0.0
        highest_tx_date: str = ""
        balances: List[float] = []
        categories: Dict[str, float] = defaultdict(float)
        income_sources: Dict[str, float] = defaultdict(float)

        for tx, cls in zip(transactions, classified):
            amount = float(tx.get("amount", 0) or 0)
            balance = tx.get("balance")
            if balance:
                balances.append(float(balance))

            if cls["direction"] == "in":
                total_income += amount
                income_sources[cls["subcategory"]] += amount
            else:
                total_expenses += amount

            categories[cls["category"]] += amount

            desc = (tx.get("description") or "").lower()
            if "fee" in desc or "charge" in desc:
                total_fees += amount
            if cls["subcategory"] == "fuliza":
                fuliza_total += amount
                fuliza_count += 1
            if cls["category"] == "betting":
                betting_total += amount
            if cls["subcategory"] == "peer_transfer":
                p2p_total += amount
                p2p_count += 1

            if amount > highest_tx:
                highest_tx = amount
                highest_tx_date = str(tx.get("date", ""))

        # ─── ADD: Extended transaction metrics ─────────────────────────────────
        detailed_metrics = self._extract_detailed_transaction_metrics(transactions)

        net_cash_flow = total_income - total_expenses
        avg_balance = mean(balances) if balances else 0.0
        savings_rate = (net_cash_flow / total_income * 100) if total_income > 0 else 0.0
        burn_rate = total_expenses / 30 if total_expenses > 0 else 0.0
        betting_pct = (betting_total / total_expenses * 100) if total_expenses > 0 else 0.0
        fee_pct = (total_fees / total_income * 100) if total_income > 0 else 0.0

        monthly_data = self._monthly_breakdown(transactions, classified)
        dow_spend = self._day_of_week_pattern(transactions, classified)
        salary_day = self._detect_salary_day(transactions, classified)
        recurring = self._detect_recurring(transactions, classified)
        anomalies = self._detect_anomalies(transactions)

        fuliza_cycles = self._detect_fuliza_cycles(transactions)
        income_analysis = self._classify_income_sources(transactions)

        health_score, health_breakdown = self._calculate_health_score_v2(
            fuliza_cycles=fuliza_cycles,
            income_sources=income_analysis,
            savings_rate=savings_rate,
            betting_pct=betting_pct,
            total_transactions=len(transactions),
        )

        logger.info(f"📊 Health Score v2: {health_score}/100")
        logger.info(f"   Breakdown: {health_breakdown}")
        if fuliza_cycles["cycle_count"] > 0:
            logger.info(f"   Fuliza cycles: {fuliza_cycles['cycle_count']} (same-day rate: {fuliza_cycles['same_day_repayment_rate']}%)")
        if income_analysis.get("loan_disbursement_warning"):
            logger.warning(f"   ⚠️  Loan income: {income_analysis['loan_as_pct_of_total_inflow']}% of inflows")

        category_data = sorted(
            [{"name": k, "value": round(v, 2)} for k, v in categories.items()],
            key=lambda x: x["value"],
            reverse=True,
        )

        depositors: Dict[str, float] = defaultdict(float)
        creditors: Dict[str, float] = defaultdict(float)
        for tx in transactions:
            who = tx.get("phone") or tx.get("description") or "unknown"
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

        top_category = category_data[0]["name"] if category_data else "N/A"
        top_category_amount = category_data[0]["value"] if category_data else 0.0
        top_category_pct = (
            top_category_amount / total_expenses * 100
            if total_expenses > 0 else 0.0
        )

        top_source = max(income_sources, key=income_sources.get) if income_sources else "N/A"
        top_source_amount = income_sources.get(top_source, 0.0)
        income_conc = (top_source_amount / total_income * 100) if total_income > 0 else 0.0

        trend_data = [
            {
                "date": m["month"],
                "transactions": m["transaction_count"],
                "amount": m["expenses"],
            }
            for m in monthly_data
        ]

        insights = self._generate_insights(
            total_income, total_expenses, net_cash_flow, savings_rate,
            top_category, top_category_pct, betting_pct, fuliza_count,
            fuliza_total, burn_rate, health_score, salary_day, recurring,
        )
        warnings = self._generate_warnings(
            betting_pct, fuliza_count, fuliza_total, total_income,
            savings_rate, anomalies, fee_pct, income_analysis,
        )
        recommendations = self._generate_recommendations(
            savings_rate, betting_pct, fuliza_count, top_category,
            top_category_pct, recurring, health_score,
        )

        return {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_cash_flow": round(net_cash_flow, 2),
            "average_balance": round(avg_balance, 2),
            "savings_rate": round(savings_rate, 2),
            "burn_rate_daily": round(burn_rate, 2),
            "total_fees": round(total_fees, 2),
            "fee_pct": round(fee_pct, 2),
            "fuliza_total": round(fuliza_total, 2),
            "fuliza_count": fuliza_count,
            "betting_total": round(betting_total, 2),
            "betting_pct": round(betting_pct, 2),
            "p2p_total": round(p2p_total, 2),
            "p2p_count": p2p_count,
            "highest_transaction": round(highest_tx, 2),
            "highest_transaction_date": highest_tx_date,
            "top_category": top_category,
            "top_category_amount": round(top_category_amount, 2),
            "top_category_percent": round(top_category_pct, 2),
            "top_income_source": top_source,
            "income_concentration": round(income_conc, 2),
            "total_transactions": len(transactions),
            "transaction_count": len(transactions),
            "category_data": category_data,
            "monthly_data": monthly_data,
            "trend_data": trend_data,
            "health_score": health_score,
            "health_breakdown": health_breakdown,
            "day_of_week_spend": dow_spend,
            "salary_day": salary_day,
            "recurring_payments": recurring,
            "anomalies": anomalies,
            "insights": insights,
            "warnings": warnings,
            "recommendations": recommendations,
            "income_change": self._mom_change(monthly_data, "income"),
            "expenses_change": self._mom_change(monthly_data, "expenses"),
            "statement_type": statement_type,
            "fuliza_cycles": fuliza_cycles,
            "income_analysis": income_analysis,
            "top_depositors": top_depositors,
            "top_creditors": top_creditors,
            # ─── NEW: Extended metrics ──────────────────────────────────────────
            "detailed_transaction_metrics": detailed_metrics,
        }

    # ─── Detailed Transaction Metrics Extraction ──────────────────────────────
    def _extract_detailed_transaction_metrics(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract detailed transaction metrics based on specific patterns in the description column.
        Returns comprehensive analysis including top transactions, cumulative sums, and merchant breakdowns.
        """
        results = {}
        
        # ─── 1. Top 10 Paid In (Income) Transactions ──────────────────────────
        income_txs = [t for t in transactions if t.get("type") == "income"]
        top_paid_in = sorted(income_txs, key=lambda x: x.get("amount", 0), reverse=True)[:10]
        results["top_10_paid_in"] = [
            {
                "receipt": tx.get("receipt", ""),
                "date": tx.get("date", ""),
                "description": tx.get("description", "")[:80],
                "amount": tx.get("amount", 0),
                "phone": tx.get("phone", "")
            }
            for tx in top_paid_in
        ]
        results["top_10_paid_in_sum"] = sum(tx.get("amount", 0) for tx in top_paid_in)
        
        # ─── 2. Top 10 Withdrawals (Expense) Transactions ──────────────────────
        expense_txs = [t for t in transactions if t.get("type") == "expense"]
        top_withdrawals = sorted(expense_txs, key=lambda x: x.get("amount", 0), reverse=True)[:10]
        results["top_10_withdrawals"] = [
            {
                "receipt": tx.get("receipt", ""),
                "date": tx.get("date", ""),
                "description": tx.get("description", "")[:80],
                "amount": tx.get("amount", 0),
            }
            for tx in top_withdrawals
        ]
        results["top_10_withdrawals_sum"] = sum(tx.get("amount", 0) for tx in top_withdrawals)
        
        # ─── 3. PayBill Payments (Pay Bill to / Pay Bill Online to) ──────────
        paybill_txs = [
            t for t in transactions 
            if "Pay Bill to" in t.get("description", "") or "Pay Bill Online to" in t.get("description", "")
        ]
        results["paybill_total"] = sum(t.get("amount", 0) for t in paybill_txs)
        results["paybill_count"] = len(paybill_txs)
        
        # Get PayBill numbers and amounts
        paybill_details = {}
        for tx in paybill_txs:
            desc = tx.get("description", "")
            # Extract PayBill number (typically 6-7 digits after "to")
            match = re.search(r'to (\d{4,7})', desc)
            if match:
                paybill_id = match.group(1)
                if paybill_id not in paybill_details:
                    paybill_details[paybill_id] = {"count": 0, "total": 0, "description": desc}
                paybill_details[paybill_id]["count"] += 1
                paybill_details[paybill_id]["total"] += tx.get("amount", 0)
        
        results["paybill_breakdown"] = [
            {"paybill": k, "total": v["total"], "count": v["count"], "sample": v["description"][:60]}
            for k, v in sorted(paybill_details.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]  # Top 10 PayBills
        
        # ─── 4. Transfer Charges (Customer Transfer of Funds Charge) ──────────
        transfer_charges = [
            t for t in transactions 
            if t.get("description", "").startswith("Customer Transfer of Funds Charge")
        ]
        results["total_transfer_charges"] = sum(t.get("amount", 0) for t in transfer_charges)
        results["transfer_charge_count"] = len(transfer_charges)
        
        # ─── 5. Money Sent to Individuals (Customer Transfer to) ──────────────
        individual_transfers = [
            t for t in transactions 
            if t.get("description", "").startswith("Customer Transfer to")
        ]
        results["total_sent_to_individuals"] = sum(t.get("amount", 0) for t in individual_transfers)
        results["individual_transfer_count"] = len(individual_transfers)
        
        # Top 10 individuals receiving money
        recipient_totals = {}
        for tx in individual_transfers:
            desc = tx.get("description", "")
            # Extract phone number or name
            phone_match = re.search(r'07\d{8}|2547\d{8}', desc)
            recipient = phone_match.group() if phone_match else desc[20:40].strip()
            
            if recipient not in recipient_totals:
                recipient_totals[recipient] = {"count": 0, "total": 0, "sample": desc}
            recipient_totals[recipient]["count"] += 1
            recipient_totals[recipient]["total"] += tx.get("amount", 0)
        
        results["top_10_individual_recipients"] = [
            {"recipient": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(recipient_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 6. Customer Payment to Small Business (Pochi La Biashara) ────────
        small_business = [
            t for t in transactions 
            if t.get("description", "").startswith("Customer Payment to Small Business to")
        ]
        results["total_pochi_la_biashara"] = sum(t.get("amount", 0) for t in small_business)
        results["pochi_la_biashara_count"] = len(small_business)
        
        # Top 10 small businesses
        business_totals = {}
        for tx in small_business:
            desc = tx.get("description", "")
            # Extract business name or till number
            match = re.search(r'to (.+?)(?:\s+at|\s+on|\s*$)', desc[40:])
            business = match.group(1).strip()[:30] if match else desc[40:60].strip()
            
            if business not in business_totals:
                business_totals[business] = {"count": 0, "total": 0}
            business_totals[business]["count"] += 1
            business_totals[business]["total"] += tx.get("amount", 0)
        
        results["top_10_small_businesses"] = [
            {"business": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(business_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 7. Till/Merchant Payments (Merchant Payment to) ──────────────────
        till_payments = [
            t for t in transactions 
            if t.get("description", "").startswith("Merchant Payment to")
        ]
        results["total_till_payments"] = sum(t.get("amount", 0) for t in till_payments)
        results["till_payment_count"] = len(till_payments)
        
        # Top 10 tills
        till_totals = {}
        for tx in till_payments:
            desc = tx.get("description", "")
            match = re.search(r'to (\d{4,7})', desc)
            till_number = match.group(1) if match else desc[18:30].strip()
            
            if till_number not in till_totals:
                till_totals[till_number] = {"count": 0, "total": 0, "sample": desc}
            till_totals[till_number]["count"] += 1
            till_totals[till_number]["total"] += tx.get("amount", 0)
        
        results["top_10_tills"] = [
            {"till_number": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(till_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 8. Merchant Charges (Pay Merchant Charge) ─────────────────────────
        merchant_charges = [
            t for t in transactions 
            if t.get("description", "").startswith("Pay Merchant Charge")
        ]
        results["total_merchant_charges"] = sum(t.get("amount", 0) for t in merchant_charges)
        results["merchant_charge_count"] = len(merchant_charges)
        
        # Top 10 merchants (extract from description)
        merchant_totals = {}
        for tx in merchant_charges:
            desc = tx.get("description", "")
            # Extract merchant name after "to"
            match = re.search(r'to (.+?)(?:\s+at|\s+for|\s*$)', desc)
            merchant = match.group(1).strip()[:30] if match else desc[20:50].strip()
            
            if merchant not in merchant_totals:
                merchant_totals[merchant] = {"count": 0, "total": 0}
            merchant_totals[merchant]["count"] += 1
            merchant_totals[merchant]["total"] += tx.get("amount", 0)
        
        results["top_10_merchant_charges"] = [
            {"merchant": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(merchant_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 9. Agent Withdrawals (Customer Withdrawal At Agent Till) ─────────
        agent_withdrawals = [
            t for t in transactions 
            if t.get("description", "").startswith("Customer Withdrawal At Agent Till")
        ]
        results["total_agent_withdrawals"] = sum(t.get("amount", 0) for t in agent_withdrawals)
        results["agent_withdrawal_count"] = len(agent_withdrawals)
        
        # Top 10 agent locations
        agent_totals = {}
        for tx in agent_withdrawals:
            desc = tx.get("description", "")
            # Extract agent name/location after "Till"
            match = re.search(r'Till\s+(\w+)', desc)
            agent = match.group(1) if match else desc[40:60].strip()
            
            if agent not in agent_totals:
                agent_totals[agent] = {"count": 0, "total": 0}
            agent_totals[agent]["count"] += 1
            agent_totals[agent]["total"] += tx.get("amount", 0)
        
        results["top_10_agent_locations"] = [
            {"agent_location": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(agent_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 10. Agent Deposits (Deposit of Funds at Agent Till) ──────────────
        agent_deposits = [
            t for t in transactions 
            if t.get("description", "").startswith("Deposit of Funds at Agent Till")
        ]
        results["total_agent_deposits"] = sum(t.get("amount", 0) for t in agent_deposits)
        results["agent_deposit_count"] = len(agent_deposits)
        
        # Top 10 depositing locations
        deposit_totals = {}
        for tx in agent_deposits:
            desc = tx.get("description", "")
            match = re.search(r'Till\s+(\w+)', desc)
            location = match.group(1) if match else desc[35:55].strip()
            
            if location not in deposit_totals:
                deposit_totals[location] = {"count": 0, "total": 0}
            deposit_totals[location]["count"] += 1
            deposit_totals[location]["total"] += tx.get("amount", 0)
        
        results["top_10_deposit_locations"] = [
            {"location": k, "total": v["total"], "count": v["count"]}
            for k, v in sorted(deposit_totals.items(), key=lambda x: x[1]["total"], reverse=True)
        ][:10]
        
        # ─── 11. Fuliza Analysis ────────────────────────────────────────────────
        fuliza_drawdowns = [
            t for t in transactions 
            if t.get("description", "").startswith("OverDraft of Credit Party")
        ]
        results["total_fuliza_drawn"] = sum(t.get("amount", 0) for t in fuliza_drawdowns)
        results["fuliza_count"] = len(fuliza_drawdowns)
        
        fuliza_repayments = [
            t for t in transactions 
            if t.get("description", "").startswith("OD Loan Repayment to")
        ]
        results["total_fuliza_repaid"] = sum(t.get("amount", 0) for t in fuliza_repayments)
        results["fuliza_repayment_count"] = len(fuliza_repayments)
        
        # Calculate Fuliza utilization
        results["fuliza_utilization_rate"] = (
            results["total_fuliza_drawn"] / results["total_fuliza_repaid"] * 100
            if results["total_fuliza_repaid"] > 0 else 0
        )
        
        # ─── 12. Top 10 Transactions by Amount (Overall) ──────────────────────
        all_txs_sorted = sorted(transactions, key=lambda x: x.get("amount", 0), reverse=True)
        results["top_10_transactions_by_amount"] = [
            {
                "receipt": tx.get("receipt", ""),
                "date": tx.get("date", ""),
                "description": tx.get("description", "")[:80],
                "amount": tx.get("amount", 0),
                "type": tx.get("type", ""),
            }
            for tx in all_txs_sorted[:10]
        ]
        
        # ─── 13. Top Customers by Total Amount (Unique per customer) ──────────
        customer_totals = {}
        for tx in transactions:
            # Try to get customer identifier
            customer = tx.get("phone", "")
            if not customer:
                desc = tx.get("description", "")
                phone_match = re.search(r'07\d{8}|2547\d{8}', desc)
                if phone_match:
                    customer = phone_match.group()
                else:
                    # Try to extract name or other identifier
                    if "Customer Transfer from" in desc:
                        match = re.search(r'from (.+?)(?:\s+on|\s+at|\s*$)', desc)
                        customer = match.group(1).strip()[:20] if match else desc[20:40].strip()
                    elif "Customer Transfer to" in desc:
                        match = re.search(r'to (.+?)(?:\s+on|\s+at|\s*$)', desc)
                        customer = match.group(1).strip()[:20] if match else desc[18:38].strip()
                    else:
                        customer = desc[:20].strip()
            
            if customer not in customer_totals:
                customer_totals[customer] = {
                    "total_in": 0,
                    "total_out": 0,
                    "count_in": 0,
                    "count_out": 0,
                    "net": 0
                }
            
            amount = tx.get("amount", 0)
            if tx.get("type") == "income":
                customer_totals[customer]["total_in"] += amount
                customer_totals[customer]["count_in"] += 1
            else:
                customer_totals[customer]["total_out"] += amount
                customer_totals[customer]["count_out"] += 1
            customer_totals[customer]["net"] = (
                customer_totals[customer]["total_in"] - 
                customer_totals[customer]["total_out"]
            )
        
        results["top_customers_by_transaction_amount"] = [
            {
                "customer": k,
                "total_received": v["total_in"],
                "total_sent": v["total_out"],
                "net": v["net"],
                "transactions": v["count_in"] + v["count_out"]
            }
            for k, v in sorted(
                customer_totals.items(),
                key=lambda x: x[1]["total_in"] + x[1]["total_out"],
                reverse=True
            )
        ][:10]
        
        # ─── 14. Monthly Summary ──────────────────────────────────────────────
        monthly_data = {}
        for tx in transactions:
            date_str = tx.get("date", "")
            if date_str:
                month_key = date_str[:7]  # YYYY-MM
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "income": 0,
                        "expenses": 0,
                        "count": 0,
                        "fuliza": 0,
                        "paybill": 0,
                        "agent_withdrawal": 0,
                        "agent_deposit": 0,
                    }
                
                monthly_data[month_key]["income"] += tx.get("amount", 0) if tx.get("type") == "income" else 0
                monthly_data[month_key]["expenses"] += tx.get("amount", 0) if tx.get("type") == "expense" else 0
                monthly_data[month_key]["count"] += 1
                
                desc = tx.get("description", "")
                if "OverDraft" in desc:
                    monthly_data[month_key]["fuliza"] += tx.get("amount", 0)
                if "Pay Bill" in desc:
                    monthly_data[month_key]["paybill"] += tx.get("amount", 0)
                if "Withdrawal At Agent" in desc:
                    monthly_data[month_key]["agent_withdrawal"] += tx.get("amount", 0)
                if "Deposit of Funds at Agent" in desc:
                    monthly_data[month_key]["agent_deposit"] += tx.get("amount", 0)
        
        results["monthly_summary"] = [
            {
                "month": k,
                "income": v["income"],
                "expenses": v["expenses"],
                "net": v["income"] - v["expenses"],
                "transactions": v["count"],
                "fuliza": v["fuliza"],
                "paybill": v["paybill"],
                "agent_withdrawal": v["agent_withdrawal"],
                "agent_deposit": v["agent_deposit"],
            }
            for k, v in sorted(monthly_data.items())
        ]
        
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
            result.append({
                "month": month,
                "income": round(data["income"], 2),
                "expenses": round(data["expenses"], 2),
                "balance": round(data["income"] - data["expenses"], 2),
                "transaction_count": data["transaction_count"],
            })
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
        dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
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
            {"day": dow_names[i], "spend": round(dow.get(i, 0.0), 2)}
            for i in range(7)
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
                recurring.append({
                    "description": desc,
                    "average_amount": round(avg, 2),
                    "occurrences": len(amounts),
                    "total": round(sum(amounts), 2),
                })
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
                anomalies.append({
                    "date": str(tx.get("date", "")),
                    "description": (tx.get("description") or "")[:60],
                    "amount": round(amount, 2),
                    "reason": f"Amount is {amount/avg:.1f}× the average",
                })
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
            "excellent" if health_score >= 80
            else "good" if health_score >= 65
            else "fair" if health_score >= 50
            else "needs attention"
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
    def _mom_change(
        self, monthly_data: List[Dict[str, Any]], key: str
    ) -> float:
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