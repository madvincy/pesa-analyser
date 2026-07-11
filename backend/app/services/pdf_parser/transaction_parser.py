"""
Transaction parsing engine - extracts transactions from raw text.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .patterns import (
    RECEIPT_PATTERN,
    AMOUNT_PATTERN,
    PHONE_PATTERNS,
    FULIZA_PATTERNS,
    CATEGORY_PATTERNS,
    CHARGE_PATTERNS,
    MECHANIC_KEYWORDS,
    SMALL_FEE_LIMIT,
    FOOTER_PATTERNS,
)
from .models import (
    Transaction,
    Merchant,
    Customer,
    MerchantCache,
    CustomerCache,
    TransactionDirection,
    TransactionType,
)
from .transaction_builder import TransactionBuilder

logger = logging.getLogger(__name__)


class TransactionParser:
    """Parse transactions from raw text."""

    def __init__(self):
        self.receipt_pattern = RECEIPT_PATTERN
        self.amount_pattern = AMOUNT_PATTERN
        self.phone_patterns = PHONE_PATTERNS
        self.fuliza_patterns = FULIZA_PATTERNS
        self.category_patterns = CATEGORY_PATTERNS
        self.charge_patterns = CHARGE_PATTERNS
        self.mechanic_keywords = MECHANIC_KEYWORDS
        self.small_fee_limit = SMALL_FEE_LIMIT
        self.builder = TransactionBuilder()

    def extract_ledger_rows(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract raw ledger rows from an M-PESA statement.

        Handles:
        • Multi-line descriptions
        • Description before amount
        • Description after amount
        • PDF page headers/footers
        • Verification code/footer pollution
        """

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        receipt_groups = defaultdict(list)
        ledger_rows = []

        stop_markers = [
            "Disclaimer:",
            "Statement Verification Code",
            "For self-help dial",
            "Receipt No.",
            "Page ",
        ]

        def is_footer(line: str) -> bool:
            line = line.strip()

            if line.startswith("Disclaimer:"):
                return True

            return any(p.search(line) for p in FOOTER_PATTERNS)

        def clean_description(description: str) -> str:
            if not description:
                return ""

            for marker in stop_markers:
                idx = description.find(marker)
                if idx != -1:
                    description = description[:idx]

            description = re.sub(r"\s+", " ", description).strip()

            return description

        i = 0

        while i < len(lines):

            receipt_match = self.receipt_pattern.match(lines[i])

            if not receipt_match:
                i += 1
                continue

            receipt, date_str, time_str, remainder = receipt_match.groups()

            receipt_lines = []

            if remainder.strip():
                receipt_lines.append(remainder.strip())

            j = i + 1

            while j < len(lines):

                if self.receipt_pattern.match(lines[j]):
                    break

                line = lines[j].strip()

                #
                # Footer starts here.
                # Everything afterwards belongs to the PDF footer.
                #
                if line.startswith("Disclaimer:"):
                    logger.info("Footer detected. Ending receipt.")
                    break

                #
                # Skip known footer/header lines.
                #
                if is_footer(line):
                    logger.debug("Skipping footer: %s", line)
                    j += 1
                    continue

                receipt_lines.append(line)

                j += 1

            description_parts = []

            status = None
            amount = None
            balance = None

            for idx, line in enumerate(receipt_lines):

                logger.debug("Processing line %d: %s", idx + 1, line)

                amt = self.amount_pattern.match(line)

                if amt:

                    logger.debug("Amount pattern matched")

                    description_line, status, amount_str, balance_str = amt.groups()

                    if description_line:
                        description_parts.append(description_line.strip())

                    try:
                        amount = float(amount_str.replace(",", ""))
                        balance = float(balance_str.replace(",", ""))

                    except ValueError:

                        logger.warning(
                            "Invalid amount/balance: %s %s",
                            amount_str,
                            balance_str,
                        )

                        status = None
                        break

                else:

                    description_parts.append(line)

            if status is not None:

                description = clean_description(" ".join(description_parts))

                row = {
                    "receipt": receipt,
                    "date": date_str,
                    "time": time_str,
                    "description": description,
                    "amount": amount,
                    "balance": balance,
                    "status": status,
                }

                receipt_groups[receipt].append(row)

            else:

                logger.warning(
                    "Receipt %s produced no ledger row.",
                    receipt,
                )

            i = j

        logger.info("=" * 100)

        for receipt, rows in receipt_groups.items():

            logger.info(
                "Receipt %s -> %d ledger rows",
                receipt,
                len(rows),
            )

            ledger_rows.extend(rows)

        if ledger_rows:

            logger.info("First five ledger rows:")

            for row in ledger_rows[:5]:
                logger.info("%s", row)

        else:

            logger.warning("NO LEDGER ROWS WERE CREATED")

        return ledger_rows

    def normalize_receipts(
        self,
        ledger_rows: List[Dict[str, Any]],
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> List[Transaction]:
        """
        Normalize ledger rows into financial transactions.

        This is the critical step that turns raw rows into meaningful
        transactions with correct amounts, directions, and fees.
        """
        # Group by receipt
        receipt_groups = defaultdict(list)
        for row in ledger_rows:
            receipt_groups[row["receipt"]].append(row)

        transactions = []

        for receipt, legs in receipt_groups.items():
            # Use the new builder
            tx = self.builder.build_transaction(
                receipt, legs, merchant_cache, customer_cache
            )
            if tx:
                transactions.append(tx)

        # Sort by date/time
        transactions.sort(key=lambda x: (x.date, x.time))

        logger.info(
            f"Normalized {len(ledger_rows)} rows into {len(transactions)} transactions"
        )
        return transactions

    # ─── Legacy / Compatibility Methods ─────────────────────────────────────

    def _build_transaction_from_legs(
        self,
        receipt: str,
        legs: List[Dict[str, Any]],
        merchant_cache: MerchantCache,
        customer_cache: CustomerCache,
    ) -> Optional[Transaction]:
        """
        Compatibility wrapper for the original method.

        This ensures any existing code that calls this method still works.
        """
        return self.builder.build_transaction(
            receipt, legs, merchant_cache, customer_cache
        )

    def _is_charge(self, description: str) -> bool:
        """Legacy method - delegates to builder."""
        return self.builder._is_charge(description)

    def _is_fuliza(self, description: str) -> bool:
        """Legacy method - delegates to builder."""
        return self.builder._is_fuliza(description)

    def _looks_like_fee(self, leg: Dict[str, Any]) -> bool:
        """Legacy method - kept for compatibility."""
        desc = leg.get("description", "").casefold().strip()
        if self._is_charge(desc):
            return True
        if len(desc) < 10 and desc in ["charge", "fee", "charges", "fees"]:
            return True
        return False

    def parse_transaction_details(self, description: str) -> Dict[str, Any]:
        """Legacy method - kept for compatibility."""
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
            (
                "funds_received",
                r"^Funds received from\s*-?\s*(?:(?P<phone>(?:254|0)\d{9})\s+)?(?P<name>.+)$",
            ),
            ("sent", r"^Sent to\s+(?P<phone>(?:254|0)\d{9})\s+(?P<name>.+)$"),
            (
                "merchant",
                r"^Merchant Payment(?: Fuliza M-Pesa)? to\s+(?P<till>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
            ),
            (
                "pochi",
                r"^Customer Payment to Small Business(?: to)?\s+(?P<till>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
            ),
            (
                "paybill",
                r"^Pay Bill(?: Online)? to\s+(?P<paybill>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
            ),
            (
                "withdrawal_agent",
                r"^(?:Withdrawal at Agent|Agent Withdrawal)\s+(?:(?P<agent>\d+)(?:\s*-\s*|\s+))?(?P<location>.+)$",
            ),
            (
                "deposit_agent",
                r"^(?:Deposit at Agent|Agent Deposit)\s+(?:(?P<agent>\d+)(?:\s*-\s*|\s+))?(?P<location>.+)$",
            ),
            ("airtime", r"^Airtime Purchase.*?(?P<phone>(?:254|0)\d{9})?$"),
            (
                "fuliza_repayment",
                r"^OD Loan Repayment to\s+(?P<paybill>\d+)\s*-\s*(?P<name>.+)$",
            ),
            ("fuliza_credit", r"^OverDraft of Credit Party$"),
        ]

        for tx_type, pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if not match:
                continue

            result["type"] = tx_type
            for key, value in match.groupdict().items():
                if value is not None:
                    value = value.strip(" -")
                    if key == "phone":
                        value = value.replace(" ", "")
                    result[key] = value
            return result

        result["name"] = desc
        return result

    def parse_bank(self, text: str) -> List[Transaction]:
        """Parse bank statement text into transactions."""
        transactions = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines:
            tx = self._parse_bank_line(line)
            if tx:
                transactions.append(tx)

        return transactions

    def parse_generic(self, text: str) -> List[Transaction]:
        """Generic parser for unknown statement types."""
        ledger_rows = self.extract_ledger_rows(text)
        if ledger_rows:
            return self.normalize_receipts(
                ledger_rows, MerchantCache(), CustomerCache()
            )
        return self.parse_bank(text)

    def _parse_bank_line(self, line: str) -> Optional[Transaction]:
        """Parse a single bank statement line."""
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 3:
            return None

        amount = None
        for part in parts:
            cleaned = re.sub(r"[^\d.]", "", part)
            if cleaned and len(cleaned) > 1:
                try:
                    amount = float(cleaned)
                    break
                except ValueError:
                    continue

        if amount is None:
            return None

        date = None
        for part in parts:
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", part) or re.search(
                r"\d{4}-\d{2}-\d{2}", part
            )
            if date_match:
                date = date_match.group()
                break

        description = " ".join(p for p in parts if p != date and str(amount) not in p)

        direction = "in" if amount > 0 else "out"

        receipt = f"BANK_{date}_{int(abs(amount))}" if date else f"BANK_{abs(amount)}"

        return Transaction(
            receipt=receipt,
            date=date or "",
            time="00:00:00",
            description=description[:200],
            details=description[:200],
            transaction_type="bank_transaction",
            direction=direction,
            principal=abs(amount),
            paid_in=amount if amount > 0 else 0.0,
            withdrawn=abs(amount) if amount < 0 else 0.0,
            raw_entries=[line],
        )

    def _categorize_transaction(self, description: str) -> str:
        """Categorize a transaction based on description."""
        desc_lower = description.lower()
        for pattern, category in self.category_patterns.items():
            if re.search(pattern, desc_lower):
                return category
        return "other"

    def _is_footer_line(self, line: str) -> bool:
        line = line.strip()

        for pattern in FOOTER_PATTERNS:
            if pattern.search(line):
                return True

        return False
