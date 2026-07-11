"""
Production-grade transaction builder for M-PESA statements.

This module handles the reconstruction of financial transactions from
raw ledger entries with high accuracy and performance.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable, Pattern
from dataclasses import dataclass
from enum import IntEnum, Flag, auto

from .models import (
    Transaction,
    Merchant,
    Customer,
    MerchantCache,
    CustomerCache,
)
from .patterns import (
    PHONE_PATTERNS,
    FULIZA_PATTERNS,
    CHARGE_PATTERNS,
    MECHANIC_KEYWORDS,
    SMALL_FEE_LIMIT,
    FOOTER_PATTERNS,
)

logger = logging.getLogger(__name__)


# ─── Enums ──────────────────────────────────────────────────────────────────


class Priority(IntEnum):
    """Priority scores for transaction type selection."""

    MERCHANT_PAYMENT = 100
    PAYBILL = 95
    POCHI = 94
    SENT_MONEY = 92
    FUNDS_RECEIVED = 90
    SALARY = 90
    DEPOSIT_AGENT = 85
    WITHDRAWAL_AGENT = 85
    LOAN_DISBURSEMENT = 82
    LOAN_REPAYMENT = 80
    AIRTIME = 75
    DATA_BUNDLE = 70
    FULIZA_BORROW = 65
    FULIZA_REPAYMENT = 60
    REVERSAL = 55
    PROMOTION = 50
    CASHBACK = 45
    CHARGE = 0
    ACCOUNTING = 0
    UNKNOWN = 10


class TransactionFlags(Flag):
    """Flags for transaction characteristics."""

    NONE = 0
    FULIZA = auto()
    REVERSAL = auto()
    CHARGE = auto()
    ACCOUNTING = auto()
    ONLINE = auto()
    PROMOTION = auto()
    CASHBACK = auto()


# ─── Rule Registry ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TransactionRule:
    """Classification rule for a transaction type."""

    name: str
    pattern: Pattern
    priority: Priority
    flags: TransactionFlags = TransactionFlags.NONE


@dataclass(frozen=True)
class MatchedRule:
    """Result of matching a rule against a description."""

    rule: TransactionRule
    specificity: int  # Length of pattern for tie-breaking
    matched_text: str


@dataclass
class ParsedLeg:
    """Immutable parsed leg with all computed data."""

    raw_description: str
    normalized_description: str
    lower_description: str
    amount: float
    balance: float
    date: str
    time: str
    status: str
    receipt: str
    flags: TransactionFlags
    transaction_type: str
    direction: str
    entities: Optional["EntityExtraction"] = None


@dataclass
class EntityExtraction:
    """Extracted entities from transaction description."""

    merchant_name: Optional[str] = None
    merchant_number: Optional[str] = None
    till_number: Optional[str] = None
    paybill_number: Optional[str] = None
    paybill_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    agent_number: Optional[str] = None
    agent_location: Optional[str] = None
    reference: Optional[str] = None
    branch: Optional[str] = None
    store_name: Optional[str] = None
    funding_source: Optional[str] = None

    @property
    def name(self) -> Optional[str]:
        """Get the primary name from extracted entities."""
        return self.merchant_name or self.customer_name or self.agent_location

    @property
    def phone(self) -> Optional[str]:
        """Get the primary phone from extracted entities."""
        return self.customer_phone


@dataclass
class ReconciliationResult:
    """Result of transaction reconciliation."""

    principal: float
    fee: float
    paid_in: float
    withdrawn: float
    net_cash_movement: float
    validation_failed: bool
    message: str = ""


# ─── Direction Rules ──────────────────────────────────────────────────────

_DIRECTION_RULES = {
    "merchant_payment": "out",
    "merchant_payment_fuliza": "out",
    "paybill": "out",
    "paybill_online": "out",
    "pochi": "out",
    "funds_received": "in",
    "sent_money": "out",
    "withdrawal": "out",
    "deposit": "in",
    "salary": "in",
    "promotion": "in",
    "loan_disbursement": "in",
    "loan_repayment": "out",
    "loan": "in",
    "fuliza_borrow": "in",
    "fuliza_repayment": "out",
    "reversal": "in",
    "buy_goods_reversal": "in",
    "paybill_reversal": "in",
    "merchant_reversal": "in",
    "b2b": "out",
    "b2c": "in",
    "agency_float": "out",
    "airtime": "out",
    "data_bundle": "out",
    "m_shwari": "out",
    "m_shwari_deposit": "in",
    "m_shwari_withdrawal": "out",
    "kcb_mpesa": "out",
    "kcb_mpesa_loan": "in",
    "kcb_mpesa_repayment": "out",
    "bank_transfer": "out",
    "standing_order": "out",
    "international_remittance": "in",
    "fee": "out",
    "unknown": "unknown",
}


# ─── Normalizer ──────────────────────────────────────────────────────────


class Normalizer:
    """Normalization utilities."""

    _BRAND_FIXES = {
        r"M-Kopa": "M-KOPA",
        r"Kcb": "KCB",
        r"M-Pesa": "M-PESA",
        r"Ncba": "NCBA",
        r"M-Shwari": "M-Shwari",
        r"Safaricom": "Safaricom",
        r"Equity": "Equity",
        r"Kplc": "KPLC",
    }

    @classmethod
    def normalize_description(cls, description: str) -> str:
        """Normalize a description once."""
        if not description:
            return ""
        return re.sub(r"\s+", " ", description).strip()

    @classmethod
    def normalize_merchant_name(cls, name: str) -> str:
        """Normalize merchant name - preserve brand names."""
        if not name:
            return ""

        normalized = re.sub(r"\s+", " ", name).strip()

        suffixes = [" LTD", " LIMITED", " PLC", " KENYA", " KENYA LTD"]
        for suffix in suffixes:
            if normalized.upper().endswith(suffix):
                normalized = normalized[: -len(suffix)]

        normalized = normalized.title()

        for pattern, replacement in cls._BRAND_FIXES.items():
            normalized = re.sub(pattern, replacement, normalized)

        return normalized.strip()

    @classmethod
    def normalize_customer_name(cls, name: str) -> str:
        """Normalize customer name."""
        if not name:
            return ""
        normalized = re.sub(r"\s+", " ", name).strip()
        return normalized.title()

    @classmethod
    def normalize_phone(cls, phone: str) -> str:
        """Normalize phone number."""
        if not phone:
            return ""

        cleaned = re.sub(r"[\s\-()]", "", phone)

        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        elif cleaned.startswith("0"):
            cleaned = "254" + cleaned[1:]
        elif not cleaned.startswith("254"):
            cleaned = "254" + cleaned

        return cleaned


# ─── Rule Builder ─────────────────────────────────────────────────────────


class RuleBuilder:
    """Build the transaction rules registry."""

    @classmethod
    def build_rules(cls) -> List[TransactionRule]:
        """Build all transaction rules."""
        rules = [
            # Specific rules first
            TransactionRule(
                name="merchant_payment_fuliza",
                pattern=re.compile(r"merchant payment.*fuliza", re.IGNORECASE),
                priority=Priority.MERCHANT_PAYMENT,
                flags=TransactionFlags.FULIZA,
            ),
            TransactionRule(
                name="paybill_online",
                pattern=re.compile(r"pay bill online", re.IGNORECASE),
                priority=Priority.PAYBILL,
                flags=TransactionFlags.ONLINE,
            ),
            TransactionRule(
                name="buy_goods_reversal",
                pattern=re.compile(r"buy goods reversal", re.IGNORECASE),
                priority=Priority.REVERSAL,
                flags=TransactionFlags.REVERSAL,
            ),
            TransactionRule(
                name="paybill_reversal",
                pattern=re.compile(r"paybill reversal", re.IGNORECASE),
                priority=Priority.REVERSAL,
                flags=TransactionFlags.REVERSAL,
            ),
            TransactionRule(
                name="merchant_reversal",
                pattern=re.compile(
                    r"merchant payment reversal|merchant reversal", re.IGNORECASE
                ),
                priority=Priority.REVERSAL,
                flags=TransactionFlags.REVERSAL,
            ),
            TransactionRule(
                name="kcb_mpesa_loan",
                pattern=re.compile(r"kcb mpesa loan|kcb m-pesa loan", re.IGNORECASE),
                priority=Priority.LOAN_DISBURSEMENT,
            ),
            TransactionRule(
                name="kcb_mpesa_repayment",
                pattern=re.compile(
                    r"kcb mpesa repayment|kcb m-pesa repayment", re.IGNORECASE
                ),
                priority=Priority.LOAN_REPAYMENT,
            ),
            TransactionRule(
                name="m_shwari_deposit",
                pattern=re.compile(r"m-shwari deposit", re.IGNORECASE),
                priority=Priority.DEPOSIT_AGENT,
            ),
            TransactionRule(
                name="m_shwari_withdrawal",
                pattern=re.compile(r"m-shwari withdrawal", re.IGNORECASE),
                priority=Priority.WITHDRAWAL_AGENT,
            ),
            TransactionRule(
                name="fuliza_borrow",
                pattern=re.compile(
                    r"overdraft of credit party|fuliza borrow", re.IGNORECASE
                ),
                priority=Priority.FULIZA_BORROW,
                flags=TransactionFlags.FULIZA,
            ),
            TransactionRule(
                name="fuliza_repayment",
                pattern=re.compile(
                    r"od loan repayment|fuliza repayment", re.IGNORECASE
                ),
                priority=Priority.FULIZA_REPAYMENT,
                flags=TransactionFlags.FULIZA,
            ),
            TransactionRule(
                name="international_remittance",
                pattern=re.compile(r"international remittance", re.IGNORECASE),
                priority=Priority.FUNDS_RECEIVED,
            ),
            TransactionRule(
                name="standing_order",
                pattern=re.compile(r"standing order", re.IGNORECASE),
                priority=Priority.PAYBILL,
            ),
            TransactionRule(
                name="bank_transfer",
                pattern=re.compile(r"bank transfer", re.IGNORECASE),
                priority=Priority.SENT_MONEY,
            ),
            TransactionRule(
                name="promotion",
                pattern=re.compile(r"promotion payment", re.IGNORECASE),
                priority=Priority.PROMOTION,
                flags=TransactionFlags.PROMOTION,
            ),
            TransactionRule(
                name="cashback",
                pattern=re.compile(r"cashback", re.IGNORECASE),
                priority=Priority.CASHBACK,
                flags=TransactionFlags.CASHBACK,
            ),
            # Generic rules last
            TransactionRule(
                name="merchant_payment",
                pattern=re.compile(r"merchant payment", re.IGNORECASE),
                priority=Priority.MERCHANT_PAYMENT,
            ),
            TransactionRule(
                name="paybill",
                pattern=re.compile(r"pay bill", re.IGNORECASE),
                priority=Priority.PAYBILL,
            ),
            TransactionRule(
                name="pochi",
                pattern=re.compile(
                    r"customer payment to small business", re.IGNORECASE
                ),
                priority=Priority.POCHI,
            ),
            TransactionRule(
                name="funds_received",
                pattern=re.compile(r"funds received from", re.IGNORECASE),
                priority=Priority.FUNDS_RECEIVED,
            ),
            TransactionRule(
                name="sent_money",
                pattern=re.compile(r"sent to|send money", re.IGNORECASE),
                priority=Priority.SENT_MONEY,
            ),
            TransactionRule(
                name="withdrawal",
                pattern=re.compile(
                    r"withdrawal at agent|agent withdrawal", re.IGNORECASE
                ),
                priority=Priority.WITHDRAWAL_AGENT,
            ),
            TransactionRule(
                name="deposit",
                pattern=re.compile(r"deposit at agent|agent deposit", re.IGNORECASE),
                priority=Priority.DEPOSIT_AGENT,
            ),
            TransactionRule(
                name="salary",
                pattern=re.compile(r"salary", re.IGNORECASE),
                priority=Priority.SALARY,
            ),
            TransactionRule(
                name="loan_disbursement",
                pattern=re.compile(r"loan disbursement", re.IGNORECASE),
                priority=Priority.LOAN_DISBURSEMENT,
            ),
            TransactionRule(
                name="loan_repayment",
                pattern=re.compile(r"loan repayment", re.IGNORECASE),
                priority=Priority.LOAN_REPAYMENT,
            ),
            TransactionRule(
                name="loan",
                pattern=re.compile(r"loan", re.IGNORECASE),
                priority=Priority.LOAN_DISBURSEMENT,
            ),
            TransactionRule(
                name="reversal",
                pattern=re.compile(r"reversal", re.IGNORECASE),
                priority=Priority.REVERSAL,
                flags=TransactionFlags.REVERSAL,
            ),
            TransactionRule(
                name="b2b",
                pattern=re.compile(r"b2b", re.IGNORECASE),
                priority=Priority.SENT_MONEY,
            ),
            TransactionRule(
                name="b2c",
                pattern=re.compile(r"b2c", re.IGNORECASE),
                priority=Priority.FUNDS_RECEIVED,
            ),
            TransactionRule(
                name="agency_float",
                pattern=re.compile(r"agency float", re.IGNORECASE),
                priority=Priority.WITHDRAWAL_AGENT,
            ),
            TransactionRule(
                name="airtime",
                pattern=re.compile(r"airtime purchase", re.IGNORECASE),
                priority=Priority.AIRTIME,
            ),
            TransactionRule(
                name="data_bundle",
                pattern=re.compile(r"bundle purchase|data bundle", re.IGNORECASE),
                priority=Priority.DATA_BUNDLE,
            ),
            TransactionRule(
                name="m_shwari",
                pattern=re.compile(r"m-shwari", re.IGNORECASE),
                priority=Priority.WITHDRAWAL_AGENT,
            ),
            TransactionRule(
                name="kcb_mpesa",
                pattern=re.compile(r"kcb mpesa|kcb m-pesa", re.IGNORECASE),
                priority=Priority.PAYBILL,
            ),
            TransactionRule(
                name="charge",
                pattern=re.compile(r"charge|fee", re.IGNORECASE),
                priority=Priority.CHARGE,
                flags=TransactionFlags.CHARGE,
            ),
        ]
        return rules


# ─── Main Builder ─────────────────────────────────────────────────────────


class TransactionBuilder:
    """
    Production-grade transaction builder for M-PESA statements.

    Reconstructs financial transactions from raw ledger entries with:
    - Rule-based primary transaction selection (not max amount)
    - Entity extraction before classification
    - Mathematical reconciliation
    - Fuliza detection and classification
    - Cache population for merchants and customers
    """

    # Class-level compiled rules (compiled once)
    RULES = RuleBuilder.build_rules()

    # Use patterns from patterns.py
    _PHONE_PATTERNS = PHONE_PATTERNS
    _FULIZA_PATTERNS = FULIZA_PATTERNS
    _CHARGE_PATTERNS = CHARGE_PATTERNS
    _MECHANIC_KEYWORDS = MECHANIC_KEYWORDS

    _ACCOUNTING_PATTERNS = [
        re.compile(r"overdraft of credit party", re.IGNORECASE),
        re.compile(r"internal settlement", re.IGNORECASE),
        re.compile(r"accounting entry", re.IGNORECASE),
        re.compile(r"balance adjustment", re.IGNORECASE),
        re.compile(r"mechanic entry", re.IGNORECASE),
        re.compile(r"od loan repayment", re.IGNORECASE),
    ]

    # Entity extraction patterns
    _MERCHANT_PATTERN = re.compile(
        r"^(?:Merchant Payment(?: Fuliza M-Pesa)?|Customer Payment to Small Business) to\s+(?P<number>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
        re.IGNORECASE,
    )
    _PAYBILL_PATTERN = re.compile(
        r"^Pay Bill(?: Online)? to\s+(?P<paybill>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
        re.IGNORECASE,
    )
    _FUNDS_RECEIVED_PATTERN = re.compile(
        r"^Funds received from\s*-?\s*(?:(?P<phone>(?:254|0)\d{9})\s+)?(?P<name>.+)$",
        re.IGNORECASE,
    )
    _SENT_MONEY_PATTERN = re.compile(
        r"^Sent to\s+(?P<phone>(?:254|0)\d{9})\s+(?P<name>.+)$", re.IGNORECASE
    )
    _AGENT_PATTERN = re.compile(
        r"^(?:Withdrawal at Agent|Agent Withdrawal|Deposit at Agent|Agent Deposit)\s+(?:(?P<agent>\d+)(?:\s*-\s*|\s+))?(?P<location>.+)$",
        re.IGNORECASE,
    )
    _AIRTIME_PATTERN = re.compile(
        r"^Airtime Purchase.*?(?P<phone>(?:254|0)\d{9})?$", re.IGNORECASE
    )
    _FULIZA_REPAYMENT_PATTERN = re.compile(
        r"^OD Loan Repayment to\s+(?P<paybill>\d+)\s*-\s*(?P<name>.+)$", re.IGNORECASE
    )

    # Fallback patterns for unknown types
    _FALLBACK_PATTERNS = [
        (_FUNDS_RECEIVED_PATTERN, "customer"),
        (_SENT_MONEY_PATTERN, "customer"),
        (_MERCHANT_PATTERN, "merchant"),
        (_PAYBILL_PATTERN, "merchant"),
        (_AGENT_PATTERN, "agent"),
        (_AIRTIME_PATTERN, "customer"),
        (_FULIZA_REPAYMENT_PATTERN, "merchant"),
    ]

    def __init__(self):
        self.small_fee_limit = SMALL_FEE_LIMIT
        self._rules = self.RULES  # Reference class-level rules
        self._extractors = {
            "merchant_payment": self._extract_merchant,
            "merchant_payment_fuliza": self._extract_merchant,
            "pochi": self._extract_merchant,
            "paybill": self._extract_paybill,
            "paybill_online": self._extract_paybill,
            "funds_received": self._extract_customer,
            "salary": self._extract_customer,
            "sent_money": self._extract_sent_money,
            "withdrawal": self._extract_agent,
            "deposit": self._extract_agent,
            "airtime": self._extract_airtime,
        }

    # ─── Stage 1: Leg Classification ──────────────────────────────────────────

    def _classify_legs(self, legs: List[Dict[str, Any]]) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """
        Classify legs into categories.

        Returns:
            Tuple of (principal_legs, charge_legs, accounting_legs, ignored_legs)
        """
        logger.debug(f"Classifying {len(legs)} legs")

        principal_legs: List[Dict[str, Any]] = []
        charge_legs: List[Dict[str, Any]] = []
        accounting_legs: List[Dict[str, Any]] = []
        ignored_legs: List[Dict[str, Any]] = []

        for leg in legs:
            desc = leg.get("description", "")
            receipt = leg.get("receipt", "unknown")

            if self._is_accounting(desc):
                logger.debug(f"Leg {receipt} classified as ACCOUNTING: {desc[:50]}")
                accounting_legs.append(leg)
                continue

            if self._is_charge(desc):
                logger.debug(f"Leg {receipt} classified as CHARGE: {desc[:50]}")
                charge_legs.append(leg)
                continue

            if self._should_ignore(leg):
                logger.debug(f"Leg {receipt} classified as IGNORED: {desc[:50]}")
                ignored_legs.append(leg)
                continue

            principal_legs.append(leg)

        logger.debug(
            f"Classification results: principal={len(principal_legs)}, "
            f"charge={len(charge_legs)}, accounting={len(accounting_legs)}, "
            f"ignored={len(ignored_legs)}"
        )

        return principal_legs, charge_legs, accounting_legs, ignored_legs

    def _is_accounting(self, description: str) -> bool:
        """Check if description is an accounting entry."""
        if not description:
            return False

        for pattern in self._ACCOUNTING_PATTERNS:
            if pattern.search(description):
                return True

        return False

    def _is_charge(self, description: str) -> bool:
        """Check if description is a charge/fee."""
        if not description:
            return False

        for pattern in self._CHARGE_PATTERNS:
            if pattern.search(description):
                return True

        return False

    def _is_fuliza(self, description: str) -> bool:
        """Check if description is Fuliza-related."""
        if not description:
            return False

        for pattern in self._FULIZA_PATTERNS:
            if pattern.search(description):
                return True

        return False

    def _should_ignore(self, leg: Dict[str, Any]) -> bool:
        """Check if leg should be ignored."""
        if abs(leg.get("amount", 0)) == 0:
            return True

        desc = leg.get("description", "").strip()
        if not desc:
            return True

        return False

    # ─── Stage 2: Transaction Scoring ──────────────────────────────────────────

    def _match_rule(self, description: str) -> Optional[MatchedRule]:
        """Match a description against all rules."""
        for rule in self._rules:
            match = rule.pattern.search(description)
            if match:
                # Calculate specificity (longer pattern = more specific)
                specificity = len(match.group(0)) if match else 0
                logger.debug(
                    f"Matched rule '{rule.name}' with specificity {specificity}"
                )
                return MatchedRule(
                    rule=rule,
                    specificity=specificity,
                    matched_text=match.group(0) if match else "",
                )
        logger.debug(f"No rule matched description: {description[:50]}")
        return None

    def _score_leg(self, leg: Dict[str, Any]) -> ParsedLeg:
        """
        Score a leg using the rule registry.

        Returns a ParsedLeg with all computed data.
        """
        raw_desc = leg.get("description", "")
        normalized_desc = Normalizer.normalize_description(raw_desc)
        lower_desc = normalized_desc.lower()
        receipt = leg.get("receipt", "unknown")

        logger.debug(f"Scoring leg {receipt}: {raw_desc[:50]}")

        matched = self._match_rule(lower_desc)

        if matched:
            rule = matched.rule
            flags = rule.flags

            # Check for additional flags
            if self._is_fuliza(lower_desc):
                flags |= TransactionFlags.FULIZA
                logger.debug(f"Leg {receipt} has FULIZA flag")
            if "reversal" in lower_desc:
                flags |= TransactionFlags.REVERSAL
                logger.debug(f"Leg {receipt} has REVERSAL flag")
            if "online" in lower_desc:
                flags |= TransactionFlags.ONLINE
            if "promotion" in lower_desc:
                flags |= TransactionFlags.PROMOTION
            if "cashback" in lower_desc:
                flags |= TransactionFlags.CASHBACK

            # Determine direction from transaction type
            direction = _DIRECTION_RULES.get(rule.name, "unknown")
            logger.debug(
                f"Leg {receipt} classified as {rule.name} with direction {direction}"
            )

            return ParsedLeg(
                raw_description=raw_desc,
                normalized_description=normalized_desc,
                lower_description=lower_desc,
                amount=leg.get("amount", 0),
                balance=leg.get("balance", 0),
                date=leg.get("date", ""),
                time=leg.get("time", ""),
                status=leg.get("status", "Completed"),
                receipt=receipt,
                flags=flags,
                transaction_type=rule.name,
                direction=direction,
                entities=None,
            )

        # Unknown transaction
        logger.warning(f"Leg {receipt} classified as UNKNOWN: {raw_desc[:50]}")
        return ParsedLeg(
            raw_description=raw_desc,
            normalized_description=normalized_desc,
            lower_description=lower_desc,
            amount=leg.get("amount", 0),
            balance=leg.get("balance", 0),
            date=leg.get("date", ""),
            time=leg.get("time", ""),
            status=leg.get("status", "Completed"),
            receipt=receipt,
            flags=TransactionFlags.NONE,
            transaction_type="unknown",
            direction="unknown",
            entities=None,
        )

    def _select_primary_leg(
        self, principal_legs: List[Dict[str, Any]]
    ) -> Optional[ParsedLeg]:
        """
        Select the primary transaction leg using scoring.

        Returns ParsedLeg to avoid re-scoring.
        """
        if not principal_legs:
            logger.debug("No principal legs to select from")
            return None

        logger.debug(f"Selecting primary leg from {len(principal_legs)} principal legs")

        parsed_legs: List[ParsedLeg] = []

        for leg in principal_legs:
            parsed = self._score_leg(leg)
            parsed_legs.append(parsed)

        # Filter out charges and accounting
        filtered = [
            p
            for p in parsed_legs
            if not (p.flags & TransactionFlags.CHARGE)
            and not (p.flags & TransactionFlags.ACCOUNTING)
        ]

        if not filtered:
            logger.debug("No non-charge/non-accounting legs found")
            return None

        # Prefer known transaction types over unknown
        known = [p for p in filtered if p.transaction_type != "unknown"]

        if known:
            filtered = known

        # Select highest priority, then largest amount
        best = max(
            filtered,
            key=lambda p: (
                next(
                    (
                        r.priority.value
                        for r in self._rules
                        if r.name == p.transaction_type
                    ),
                    0,
                ),
                abs(p.amount),
            ),
        )

        return best

    # ─── Stage 3: Entity Extraction ──────────────────────────────────────────

    def _extract_entities(
        self,
        parsed_leg: ParsedLeg,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """
        Extract entities from a parsed leg.

        Uses the extractor registry if available, otherwise falls back to generic.
        """
        logger.debug(
            f"Extracting entities for {parsed_leg.transaction_type}: {parsed_leg.raw_description[:50]}"
        )

        extractor = self._extractors.get(parsed_leg.transaction_type)
        if extractor:
            result = extractor(
                parsed_leg.normalized_description, merchant_cache, customer_cache
            )
            self._apply_caches(result, merchant_cache, customer_cache)
            logger.debug(
                f"Extracted entities: merchant={result.merchant_name}, customer={result.customer_name}"
            )
            return result

        # Fallback
        logger.debug(
            f"No specific extractor for {parsed_leg.transaction_type}, using fallback"
        )
        result = self._extract_fallback(
            parsed_leg.normalized_description, merchant_cache, customer_cache
        )
        self._apply_caches(result, merchant_cache, customer_cache)
        return result

    def _extract_merchant(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract merchant information."""
        result = EntityExtraction()
        match = self._MERCHANT_PATTERN.search(description)
        if match:
            result.merchant_name = Normalizer.normalize_merchant_name(
                match.group("name").strip()
            )
            result.merchant_number = match.group("number").strip()
            result.till_number = result.merchant_number
            logger.debug(
                f"Extracted merchant: {result.merchant_name} ({result.merchant_number})"
            )
        return result

    def _extract_paybill(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract paybill information."""
        result = EntityExtraction()
        match = self._PAYBILL_PATTERN.search(description)
        if match:
            result.merchant_name = Normalizer.normalize_merchant_name(
                match.group("name").strip()
            )
            result.paybill_number = match.group("paybill").strip()
            result.merchant_number = result.paybill_number
            logger.debug(
                f"Extracted paybill: {result.merchant_name} ({result.paybill_number})"
            )
        return result

    def _extract_customer(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract customer information (incoming)."""
        result = EntityExtraction()
        match = self._FUNDS_RECEIVED_PATTERN.search(description)
        if match:
            result.customer_name = Normalizer.normalize_customer_name(
                match.group("name").strip()
            )
            if match.groupdict().get("phone"):
                result.customer_phone = Normalizer.normalize_phone(
                    match.group("phone").strip()
                )
            logger.debug(
                f"Extracted customer: {result.customer_name} ({result.customer_phone})"
            )
        return result

    def _extract_sent_money(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract customer information (outgoing)."""
        result = EntityExtraction()
        match = self._SENT_MONEY_PATTERN.search(description)
        if match:
            result.customer_name = Normalizer.normalize_customer_name(
                match.group("name").strip()
            )
            result.customer_phone = Normalizer.normalize_phone(
                match.group("phone").strip()
            )
            logger.debug(
                f"Extracted sent money recipient: {result.customer_name} ({result.customer_phone})"
            )
        return result

    def _extract_agent(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract agent information."""
        result = EntityExtraction()
        match = self._AGENT_PATTERN.search(description)
        if match:
            if match.groupdict().get("agent"):
                result.agent_number = match.group("agent").strip()
            if match.groupdict().get("location"):
                result.agent_location = match.group("location").strip()
            logger.debug(
                f"Extracted agent: {result.agent_number} at {result.agent_location}"
            )
        return result

    def _extract_airtime(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Extract phone number for airtime purchase."""
        result = EntityExtraction()
        match = self._AIRTIME_PATTERN.search(description)
        if match and match.groupdict().get("phone"):
            result.customer_phone = Normalizer.normalize_phone(
                match.group("phone").strip()
            )
            logger.debug(f"Extracted airtime phone: {result.customer_phone}")
        return result

    def _extract_fallback(
        self,
        description: str,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> EntityExtraction:
        """Fallback entity extraction."""
        result = EntityExtraction()

        for pattern, entity_type in self._FALLBACK_PATTERNS:
            match = pattern.search(description)
            if match:
                if match.groupdict().get("name"):
                    name = match.group("name").strip()
                    if entity_type == "merchant":
                        result.merchant_name = Normalizer.normalize_merchant_name(name)
                    elif entity_type == "customer":
                        result.customer_name = Normalizer.normalize_customer_name(name)
                    elif entity_type == "agent":
                        result.agent_location = name

                if match.groupdict().get("phone"):
                    result.customer_phone = Normalizer.normalize_phone(
                        match.group("phone").strip()
                    )

                if "number" in match.groupdict():
                    result.merchant_number = match.group("number").strip()
                    result.till_number = result.merchant_number

                if "paybill" in match.groupdict():
                    result.paybill_number = match.group("paybill").strip()
                    result.merchant_number = result.paybill_number

                if "location" in match.groupdict():
                    result.agent_location = match.group("location").strip()

                break

        return result

    def _apply_caches(
        self,
        entities: EntityExtraction,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> None:
        """Apply cached data to entities."""
        if entities.merchant_number:
            cached = merchant_cache.get(entities.merchant_number)
            if cached and not entities.merchant_name:
                entities.merchant_name = cached.name
                logger.debug(f"Applied merchant cache: {entities.merchant_name}")

        if entities.paybill_number:
            cached = merchant_cache.get(entities.paybill_number)
            if cached and not entities.merchant_name:
                entities.merchant_name = cached.name
                logger.debug(f"Applied paybill cache: {entities.merchant_name}")

        if entities.customer_phone:
            cached = customer_cache.get(entities.customer_phone)
            if cached and not entities.customer_name:
                entities.customer_name = cached.name
                logger.debug(f"Applied customer cache: {entities.customer_name}")

    # ─── Stage 4-5: Direction and Type ──────────────────────────────────────

    def _determine_direction_and_type(self, parsed_leg: ParsedLeg) -> Tuple[str, str]:
        """
        Determine direction and transaction type from the parsed leg.

        Never infers direction from amount alone - uses business event.
        """
        transaction_type = parsed_leg.transaction_type
        direction = parsed_leg.direction

        logger.debug(
            f"Determining direction for {parsed_leg.receipt}: type={transaction_type}, direction={direction}"
        )

        # Handle reversals - preserve specific reversal types
        if parsed_leg.flags & TransactionFlags.REVERSAL:
            if transaction_type in [
                "buy_goods_reversal",
                "paybill_reversal",
                "merchant_reversal",
            ]:
                pass
            else:
                transaction_type = "reversal"

            amount = parsed_leg.amount
            direction = "in" if amount > 0 else "out"
            logger.debug(
                f"REVERSAL: direction set to {direction} based on amount {amount}"
            )
            return direction, transaction_type

        # Fuliza: keep transaction_type as merchant_payment, but track funding
        if (
            parsed_leg.flags & TransactionFlags.FULIZA
        ) and transaction_type == "merchant_payment":
            direction = "out"
            logger.debug(f"FULIZA merchant payment: direction={direction}")
            return direction, transaction_type

        # Unknown type fallback - but don't use amount
        if transaction_type == "unknown":
            desc_lower = parsed_leg.lower_description
            if any(kw in desc_lower for kw in ["received", "credited", "deposit"]):
                direction = "in"
                logger.debug(f"UNKNOWN: inferred direction IN from description")
            elif any(
                kw in desc_lower for kw in ["payment", "withdrawal", "sent", "purchase"]
            ):
                direction = "out"
                logger.debug(f"UNKNOWN: inferred direction OUT from description")
            else:
                direction = "unknown"
                logger.debug(f"UNKNOWN: could not infer direction, leaving as unknown")

        logger.debug(f"Final direction: {direction}, type: {transaction_type}")
        return direction, transaction_type

    # ─── Stage 6: Amount Calculation ──────────────────────────────────────────

    def _calculate_amounts(
        self,
        primary_leg: ParsedLeg,
        charge_legs: List[Dict[str, Any]],
        sorted_legs: List[Dict[str, Any]],
        direction: str,
        transaction_type: str,
    ) -> ReconciliationResult:
        """
        Calculate principal, fee, paid_in, withdrawn, and net cash movement.

        Performs reconciliation against ledger balances (source of truth).
        """
        principal_amount = abs(primary_leg.amount)
        fee_total = sum(abs(leg.get("amount", 0)) for leg in charge_legs)

        logger.debug(
            f"Calculating amounts for {primary_leg.receipt}: principal={principal_amount}, fee_total={fee_total}, direction={direction}"
        )

        if direction == "in":
            paid_in = principal_amount
            withdrawn = 0.0
            net_cash_movement = paid_in
        elif direction == "out":
            paid_in = 0.0
            withdrawn = principal_amount
            net_cash_movement = -(principal_amount + fee_total)
        else:
            paid_in = 0.0
            withdrawn = 0.0
            net_cash_movement = 0.0

        validation_failed = False
        message = ""

        # Reconciliation against ledger balances (source of truth)
        if len(sorted_legs) >= 2:
            first_balance = sorted_legs[0].get("balance", 0)
            last_balance = sorted_legs[-1].get("balance", 0)
            actual_balance_change = last_balance - first_balance

            expected_change = net_cash_movement

            if abs(actual_balance_change - expected_change) > 0.01:
                validation_failed = True
                message = (
                    f"Balance reconciliation failed: balance change={actual_balance_change:.2f}, "
                    f"expected={expected_change:.2f}"
                )
                logger.warning(f"Receipt {primary_leg.receipt}: {message}")
            else:
                logger.debug(
                    f"Receipt {primary_leg.receipt}: balance reconciled (change={actual_balance_change:.2f}, expected={expected_change:.2f})"
                )

        return ReconciliationResult(
            principal=principal_amount,
            fee=round(fee_total, 2),
            paid_in=round(paid_in, 2),
            withdrawn=round(withdrawn, 2),
            net_cash_movement=round(net_cash_movement, 2),
            validation_failed=validation_failed,
            message=message,
        )

    # ─── Stage 7: Fuliza Detection ──────────────────────────────────────────

    def _detect_fuliza_status(
        self, sorted_legs: List[Dict[str, Any]], parsed_leg: ParsedLeg
    ) -> Tuple[bool, str, float]:
        """
        Detect Fuliza status, amount, and funding source.

        Uses parsed leg flags to avoid rescanning.
        """
        fuliza_used = bool(parsed_leg.flags & TransactionFlags.FULIZA)
        funding_source = "own_funds"
        fuliza_amount = 0.0

        logger.debug(
            f"Detecting Fuliza status for {parsed_leg.receipt}: fuliza_used={fuliza_used}"
        )

        if fuliza_used:
            for leg in sorted_legs:
                desc = leg.get("description", "")
                if self._is_fuliza(desc):
                    amount = abs(leg.get("amount", 0))
                    if amount > fuliza_amount:
                        fuliza_amount = amount

                    desc_lower = desc.lower()
                    if "repayment" in desc_lower:
                        funding_source = "fuliza_repayment"
                    elif "merchant payment" in desc_lower:
                        funding_source = "fuliza"
                    else:
                        funding_source = "fuliza"

            logger.debug(
                f"Fuliza detected: amount={fuliza_amount}, funding_source={funding_source}"
            )

        return fuliza_used, funding_source, fuliza_amount

    # ─── Stage 8: Cache Population ──────────────────────────────────────────

    def _populate_caches(
        self,
        entities: EntityExtraction,
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> None:
        """Populate merchant and customer caches."""
        if entities.merchant_name:
            merchant_key = (
                entities.merchant_number
                or entities.till_number
                or entities.paybill_number
            )
            if merchant_key and not merchant_cache.get(merchant_key):
                merchant_cache.set(
                    merchant_key,
                    Merchant(
                        name=entities.merchant_name,
                        till_number=entities.till_number,
                        paybill_number=entities.paybill_number,
                    ),
                )
                logger.debug(
                    f"Cached merchant: {entities.merchant_name} ({merchant_key})"
                )

        if entities.customer_name and entities.customer_phone:
            if entities.customer_phone and not customer_cache.get(
                entities.customer_phone
            ):
                customer_cache.set(
                    entities.customer_phone,
                    Customer(
                        name=entities.customer_name,
                        phone=entities.customer_phone,
                    ),
                )
                logger.debug(
                    f"Cached customer: {entities.customer_name} ({entities.customer_phone})"
                )

    # ─── Main Builder ──────────────────────────────────────────────────────

    def build_transaction(
        self,
        receipt: str,
        legs: List[Dict[str, Any]],
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> Optional[Transaction]:
        """
        Build a single transaction from receipt legs.

        This is the main entry point for transaction reconstruction.
        """
        if not legs:
            logger.warning(f"No legs provided for receipt {receipt}")
            return None

        # Sort legs once
        sorted_legs = sorted(legs, key=lambda l: (l.get("date", ""), l.get("time", "")))

        # ─── Stage 1: Classify legs ──────────────────────────────────────────
        principal_legs, charge_legs, accounting_legs, ignored_legs = (
            self._classify_legs(sorted_legs)
        )

        # ─── Stage 2: Select primary leg ─────────────────────────────────────
        parsed_leg = self._select_primary_leg(principal_legs)

        if not parsed_leg and charge_legs:
            return self._create_fee_transaction(receipt, sorted_legs, charge_legs)

        if not parsed_leg:
            logger.warning(f"Receipt {receipt}: No primary leg found, skipping")
            return None

        # ─── Stage 3: Extract entities ──────────────────────────────────────────
        entities = self._extract_entities(parsed_leg, merchant_cache, customer_cache)

        # ─── Stage 4-5: Direction and Type ──────────────────────────────────
        direction, transaction_type = self._determine_direction_and_type(parsed_leg)

        # ─── Stage 6: Calculate amounts ─────────────────────────────────────
        reconciliation = self._calculate_amounts(
            parsed_leg, charge_legs, sorted_legs, direction, transaction_type
        )

        # ─── Stage 7: Fuliza detection ──────────────────────────────────────
        fuliza_used, funding_source, fuliza_amount = self._detect_fuliza_status(
            sorted_legs, parsed_leg
        )

        # ─── Stage 8: Populate caches ──────────────────────────────────────
        self._populate_caches(entities, merchant_cache, customer_cache)

        # ─── Get final balance ──────────────────────────────────────────────
        final_balance = sorted_legs[-1].get("balance", 0.0) if sorted_legs else 0.0
        final_status = (
            sorted_legs[-1].get("status", "Completed") if sorted_legs else "Completed"
        )

        # ─── Build Transaction ──────────────────────────────────────────────
        transaction = Transaction(
            receipt=receipt,
            date=parsed_leg.date,
            time=parsed_leg.time,
            description=parsed_leg.raw_description,
            details=parsed_leg.raw_description,
            transaction_type=transaction_type,
            direction=direction,
            principal=reconciliation.principal,
            fee=reconciliation.fee,
            paid_in=reconciliation.paid_in,
            withdrawn=reconciliation.withdrawn,
            balance=final_balance,
            customer_name=entities.customer_name,
            customer_phone=entities.customer_phone,
            merchant_name=entities.merchant_name,
            merchant_number=entities.merchant_number,
            till_number=entities.till_number,
            paybill_number=entities.paybill_number,
            account_reference=entities.reference,
            agent_number=entities.agent_number,
            location=entities.agent_location,
            fuliza_used=fuliza_used,
            fuliza_amount=fuliza_amount,
            funding_source=funding_source,
            status=final_status,
            raw_entries=[leg.get("description", "") for leg in sorted_legs],
            parsed={
                "type": transaction_type,
                "name": entities.name,
                "phone": entities.phone,
                "till": entities.till_number,
                "paybill": entities.paybill_number,
                "agent": entities.agent_number,
                "location": entities.agent_location,
                "direction": direction,
                "funding_source": funding_source,
                "reconciliation_message": reconciliation.message,
            },
            validation_failed=reconciliation.validation_failed,
        )

        return transaction

    def _create_fee_transaction(
        self,
        receipt: str,
        sorted_legs: List[Dict[str, Any]],
        charge_legs: List[Dict[str, Any]],
    ) -> Optional[Transaction]:
        """Create a transaction from only fee legs."""
        if not charge_legs:
            return None

        fee_total = sum(abs(leg.get("amount", 0)) for leg in charge_legs)
        descriptions = [leg.get("description", "") for leg in charge_legs[:3]]

        return Transaction(
            receipt=receipt,
            date=charge_legs[0].get("date", ""),
            time=charge_legs[0].get("time", ""),
            description=", ".join(descriptions),
            details=", ".join(descriptions),
            transaction_type="fee",
            direction="out",
            principal=0.0,
            fee=round(fee_total, 2),
            paid_in=0.0,
            withdrawn=0.0,
            balance=sorted_legs[-1].get("balance", 0.0) if sorted_legs else 0.0,
            status=(
                sorted_legs[-1].get("status", "Completed")
                if sorted_legs
                else "Completed"
            ),
            fuliza_used=False,
            raw_entries=[leg.get("description", "") for leg in sorted_legs],
            parsed={
                "type": "fee",
                "name": "Fee",
                "phone": None,
                "till": None,
                "paybill": None,
                "agent": None,
                "location": None,
                "direction": "out",
                "funding_source": None,
                "reconciliation_message": "",
            },
        )
