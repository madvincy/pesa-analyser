"""
Statement validation utilities.
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple, Union
from pathlib import Path

from .patterns import (
    FINANCIAL_KEYWORDS,
    M_PESA_INDICATORS,
    BANK_INDICATORS,
    PHONE_PATTERNS,
    EMAIL_PATTERN,
)
from .models import Transaction

logger = logging.getLogger(__name__)


class StatementValidator:
    """Validate financial statement content and detect statement types."""

    def __init__(self):
        self.financial_keywords = FINANCIAL_KEYWORDS
        self.mpesa_indicators = M_PESA_INDICATORS
        self.bank_indicators = BANK_INDICATORS
        self.phone_patterns = PHONE_PATTERNS
        self.email_pattern = EMAIL_PATTERN

    def validate(
        self, text: str, filename: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate if text is a financial statement.

        Args:
            text: Text content to validate
            filename: Optional filename for additional validation

        Returns:
            Tuple of (is_financial, details)
        """
        details = {
            "keyword_count": 0,
            "found_keywords": [],
            "is_mpesa": False,
            "is_bank": False,
            "has_amounts": False,
            "has_dates": False,
            "has_receipts": False,
            "confidence": 0,
            "filename_indicators": [],
        }

        text_lower = text.lower()

        # Check for financial keywords
        for kw in self.financial_keywords:
            if kw in text_lower:
                details["keyword_count"] += 1
                details["found_keywords"].append(kw)

        # Check for M-PESA or bank indicators
        details["is_mpesa"] = any(ind in text_lower for ind in self.mpesa_indicators)
        details["is_bank"] = any(ind in text_lower for ind in self.bank_indicators)

        # Check for amounts (currency format)
        amount_pattern = r"[\d,]+\.\d{2}"
        amounts = re.findall(amount_pattern, text)
        details["has_amounts"] = len(amounts) >= 3

        # Check for dates
        date_pattern = r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}"
        dates = re.findall(date_pattern, text)
        details["has_dates"] = len(dates) >= 3

        # Check for receipt numbers (M-PESA format)
        receipt_pattern = r"[A-Z0-9]{10}"
        receipts = re.findall(receipt_pattern, text)
        details["has_receipts"] = len(receipts) >= 3

        # Check filename indicators
        if filename:
            filename_lower = filename.lower()
            for indicator in (
                self.mpesa_indicators
                + self.bank_indicators
                + ["statement", "transaction"]
            ):
                if indicator in filename_lower:
                    details["filename_indicators"].append(indicator)

        # Calculate confidence
        confidence = 0
        confidence += min(
            details["keyword_count"] * 5, 30
        )  # Up to 30 points for keywords
        confidence += 15 if details["is_mpesa"] or details["is_bank"] else 0
        confidence += 15 if details["has_amounts"] else 0
        confidence += 15 if details["has_dates"] else 0
        confidence += 15 if details["has_receipts"] else 0
        confidence += 10 if details["filename_indicators"] else 0

        details["confidence"] = min(confidence, 100)

        is_financial = details["confidence"] >= 40

        logger.info(
            f"Validation result: {is_financial} "
            f"(confidence={details['confidence']}%, "
            f"keywords={details['keyword_count']}, "
            f"mpesa={details['is_mpesa']}, "
            f"bank={details['is_bank']}, "
            f"receipts={details['has_receipts']})"
        )

        return is_financial, details

    def validate_mpesa(self, text: str) -> bool:
        """Validate if text is an M-PESA statement."""
        text_lower = text.lower()
        return any(ind in text_lower for ind in self.mpesa_indicators)

    def validate_bank(self, text: str) -> bool:
        """Validate if text is a bank statement."""
        text_lower = text.lower()
        return any(ind in text_lower for ind in self.bank_indicators)

    def validate_transaction_dict(self, transaction: Dict[str, Any]) -> bool:
        """
        Validate a single transaction dictionary.

        This is kept for backward compatibility.
        """
        required_fields = ["date", "details", "amount"]
        if not all(field in transaction for field in required_fields):
            return False

        # Validate amount is numeric
        try:
            float(transaction["amount"])
        except (ValueError, TypeError):
            return False

        # Validate date format (at least has some date-like string)
        date = str(transaction.get("date", ""))
        if not date or len(date) < 6:
            return False

        return True

    def validate_transactions(
        self, transactions: List[Transaction], metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Validate and reconcile a list of Transaction objects.

        Checks:
        - Opening balance + income - expenses = closing balance
        - No missing required fields
        - No duplicate receipts
        - Valid transaction directions
        - Valid amounts

        Args:
            transactions: List of Transaction objects to validate
            metadata: Optional metadata with opening/closing balances

        Returns:
            True if validation passes, False otherwise
        """
        if not transactions:
            logger.warning("No transactions to validate")
            return True

        # Validate each transaction
        all_valid = True
        receipts = set()
        duplicate_receipts = set()

        for tx in transactions:
            # Check for duplicate receipts
            if tx.receipt:
                if tx.receipt in receipts:
                    duplicate_receipts.add(tx.receipt)
                    logger.warning(f"Duplicate receipt found: {tx.receipt}")
                else:
                    receipts.add(tx.receipt)

            # Validate individual transaction
            if not self._validate_transaction(tx):
                all_valid = False

        if duplicate_receipts:
            logger.warning(f"Found {len(duplicate_receipts)} duplicate receipts")
            all_valid = False

        # Calculate totals using direction
        total_income = sum(t.principal for t in transactions if t.direction == "in")
        total_expenses = sum(
            t.principal + t.fee for t in transactions if t.direction == "out"
        )
        total_fees = sum(t.fee for t in transactions)
        net_flow = total_income - total_expenses

        logger.info(
            f"Validation: Income={total_income:.2f}, "
            f"Expenses={total_expenses:.2f}, "
            f"Fees={total_fees:.2f}, "
            f"Net={net_flow:.2f}"
        )

        # Reconcile with metadata if available
        if metadata:
            opening = float(metadata.get("opening_balance", 0))
            closing = float(metadata.get("closing_balance", 0))

            if opening and closing:
                expected = opening + net_flow
                diff = abs(expected - closing)

                if diff > 1.0:  # Allow 1 KES difference for rounding
                    logger.warning(
                        f"Balance mismatch: Opening={opening:.2f}, "
                        f"Expected={expected:.2f}, Actual={closing:.2f}, "
                        f"Diff={diff:.2f}"
                    )
                    all_valid = False
                else:
                    logger.info(
                        f"Balance reconciled: {opening:.2f} + {net_flow:.2f} = {closing:.2f}"
                    )

        logger.info(f"Validation {'passed' if all_valid else 'failed'}")
        return all_valid

    def _validate_transaction(self, tx: Transaction) -> bool:
        """
        Validate a single Transaction object.

        Checks:
        - Required fields exist
        - Valid direction
        - Valid amounts (non-negative)
        - Valid date format
        """
        # Check required fields - using details instead of description
        required_fields = ["date", "details", "principal", "direction"]
        for field in required_fields:
            if not getattr(tx, field, None):
                logger.info(f"Transaction {tx.receipt} missing required field: {tx}")
                logger.warning(f"Transaction {tx.receipt} missing field: {field}")
                return False

        # Validate direction
        if tx.direction not in ["in", "out"]:
            logger.warning(
                f"Transaction {tx.receipt} has invalid direction: {tx.direction}"
            )
            return False

        # Validate amounts (non-negative)
        if tx.principal < 0:
            logger.warning(
                f"Transaction {tx.receipt} has negative principal: {tx.principal}"
            )
            return False

        if tx.fee < 0:
            logger.warning(f"Transaction {tx.receipt} has negative fee: {tx.fee}")
            return False

        # Validate date format
        date_str = str(tx.date)
        if len(date_str) < 6:
            logger.warning(f"Transaction {tx.receipt} has invalid date: {tx.date}")
            return False

        # Validate direction matches amounts
        if tx.direction == "in" and tx.principal == 0 and tx.paid_in == 0:
            logger.warning(f"Transaction {tx.receipt} is income but has zero amount")
            return False

        if tx.direction == "out" and tx.principal == 0 and tx.withdrawn == 0:
            logger.warning(f"Transaction {tx.receipt} is expense but has zero amount")
            return False

        return True

    def get_statement_type(self, text: str) -> str:
        """Detect statement type from text."""
        text_lower = text.lower()

        # Check for M-PESA indicators
        if any(ind in text_lower for ind in self.mpesa_indicators):
            # Additional check: look for M-PESA specific patterns
            if re.search(r"[A-Z0-9]{10}\s+\d{4}-\d{2}-\d{2}", text):
                return "mpesa"
            return "mpesa"

        # Check for bank indicators
        if any(ind in text_lower for ind in self.bank_indicators):
            return "bank"

        # Check for common patterns
        if re.search(r"statement\s+of\s+account", text_lower):
            return "bank"

        return "unknown"

    def get_confidence_score(self, text: str) -> int:
        """Get confidence score (0-100) for financial statement detection."""
        _, details = self.validate(text)
        return details["confidence"]

    def check_encryption(self, content: bytes) -> bool:
        """Check if PDF content is encrypted."""
        try:
            import PyPDF2
            import io

            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return reader.is_encrypted
        except Exception:
            return False

    def validate_phone_number(self, phone: str) -> bool:
        """Validate a phone number format (Kenyan numbers)."""
        if not phone:
            return False

        # Clean the phone number
        cleaned = re.sub(r"[\s\-()]", "", phone)

        # Check against patterns
        for pattern in self.phone_patterns:
            if re.match(pattern, cleaned):
                return True

        # Additional Kenyan number validation
        if re.match(r"^(254|0)[7-9]\d{8}$", cleaned):
            return True

        return False

    def validate_email(self, email: str) -> bool:
        """Validate an email address."""
        if not email:
            return False
        return bool(self.email_pattern.match(email))

    def validate_statement_content(self, text: str) -> Dict[str, Any]:
        """
        Perform detailed validation and return structured results.

        Returns:
            Dict with validation results and statistics
        """
        results = {
            "is_valid": False,
            "confidence": 0,
            "statement_type": "unknown",
            "statistics": {},
            "issues": [],
            "warnings": [],
        }

        text_lower = text.lower()

        # Check minimum content length
        if len(text.strip()) < 100:
            results["issues"].append("Content is too short (minimum 100 characters)")
            return results

        # Count financial indicators
        keyword_count = sum(1 for kw in self.financial_keywords if kw in text_lower)
        results["statistics"]["keyword_count"] = keyword_count

        # Count amounts
        amounts = re.findall(r"[\d,]+\.\d{2}", text)
        results["statistics"]["amount_count"] = len(amounts)
        if len(amounts) < 3:
            results["warnings"].append(
                f"Only {len(amounts)} amounts found (minimum 3 recommended)"
            )

        # Count dates
        dates = re.findall(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", text)
        results["statistics"]["date_count"] = len(dates)
        if len(dates) < 3:
            results["warnings"].append(
                f"Only {len(dates)} dates found (minimum 3 recommended)"
            )

        # Detect statement type
        results["statement_type"] = self.get_statement_type(text)
        results["statistics"]["statement_type"] = results["statement_type"]

        # Calculate confidence
        confidence = 0
        confidence += min(keyword_count * 5, 35)
        confidence += 20 if len(amounts) >= 3 else 0
        confidence += 20 if len(dates) >= 3 else 0
        confidence += 15 if results["statement_type"] != "unknown" else 0
        results["confidence"] = min(confidence, 100)

        results["is_valid"] = results["confidence"] >= 45

        if not results["is_valid"]:
            results["issues"].append(
                f'Confidence score {results["confidence"]}% is below threshold (45%)'
            )

        return results

    def detect_format(self, content: bytes) -> Dict[str, Any]:
        """
        Detect the format of the file content.

        Returns:
            Dict with format detection results
        """
        result = {
            "format": "unknown",
            "confidence": 0,
            "details": {},
        }

        # Check if it's a PDF
        if content.startswith(b"%PDF"):
            result["format"] = "pdf"
            result["details"]["is_encrypted"] = self.check_encryption(content)

            # Try to get PDF metadata
            try:
                import PyPDF2
                import io

                reader = PyPDF2.PdfReader(io.BytesIO(content))
                result["details"]["page_count"] = len(reader.pages)
                result["details"]["metadata"] = reader.metadata
            except Exception:
                pass

            result["confidence"] = 90

        # Check if it's a CSV
        elif (
            content.startswith(b",")
            or content.startswith(b'"')
            or b"\n" in content[:1000]
        ):
            # Try to detect CSV by checking for comma-separated values
            text_sample = content[:5000].decode("utf-8", errors="ignore")
            lines = text_sample.split("\n")
            if len(lines) > 1:
                first_line = lines[0]
                if "," in first_line or ";" in first_line or "\t" in first_line:
                    result["format"] = "csv"
                    result["confidence"] = 70
                    result["details"]["separator"] = self._detect_csv_separator(
                        first_line
                    )

        # Check if it's Excel (XLS/XLSX)
        elif content.startswith(b"\xd0\xcf\x11\xe0") or content.startswith(
            b"PK\x03\x04"
        ):
            if content.startswith(b"PK\x03\x04"):
                # Check if it's XLSX (ZIP with specific structure)
                if b"xl/" in content[:1000]:
                    result["format"] = "xlsx"
                    result["confidence"] = 85
            else:
                result["format"] = "xls"
                result["confidence"] = 80

        return result

    def _detect_csv_separator(self, line: str) -> str:
        """Detect the separator used in a CSV file."""
        if "\t" in line:
            return "tab"
        elif ";" in line:
            return "semicolon"
        elif "," in line:
            return "comma"
        else:
            return "unknown"

    def validate_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Validate a file on disk.

        Args:
            file_path: Path to the file

        Returns:
            Dict with validation results
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return {"is_valid": False, "error": "File not found"}

        if not file_path.is_file():
            return {"is_valid": False, "error": "Not a file"}

        # Check extension
        ext = file_path.suffix.lower()
        allowed_extensions = [".pdf", ".csv", ".xls", ".xlsx"]
        if ext not in allowed_extensions:
            return {
                "is_valid": False,
                "error": f"Unsupported file type: {ext}",
                "allowed": allowed_extensions,
            }

        # Read and validate content
        try:
            content = file_path.read_bytes()
            text = ""

            if ext == ".pdf":
                try:
                    import pdfplumber

                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                except Exception:
                    # Try PyPDF2 as fallback
                    try:
                        import PyPDF2

                        with open(file_path, "rb") as f:
                            reader = PyPDF2.PdfReader(f)
                            for page in reader.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text += page_text + "\n"
                    except Exception:
                        pass

            elif ext == ".csv":
                try:
                    import pandas as pd

                    df = pd.read_csv(file_path)
                    text = " ".join(df.columns.astype(str))
                    text += " " + " ".join(df.head(10).astype(str).values.flatten())
                except Exception:
                    pass

            elif ext in [".xls", ".xlsx"]:
                try:
                    import pandas as pd

                    df = pd.read_excel(file_path)
                    text = " ".join(df.columns.astype(str))
                    text += " " + " ".join(df.head(10).astype(str).values.flatten())
                except Exception:
                    pass

            # Validate the extracted text
            is_valid, details = self.validate(text, file_path.name)

            return {
                "is_valid": is_valid,
                "details": details,
                "file_size": file_path.stat().st_size,
                "extension": ext,
                "text_length": len(text),
            }

        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Failed to read file: {str(e)}",
            }

    def reconcile_balances(
        self,
        transactions: List[Transaction],
        opening_balance: float,
        closing_balance: float,
    ) -> Dict[str, Any]:
        """
        Reconcile opening and closing balances with transactions.

        Args:
            transactions: List of transactions
            opening_balance: Opening balance from statement
            closing_balance: Closing balance from statement

        Returns:
            Dict with reconciliation results
        """
        total_income = sum(t.principal for t in transactions if t.direction == "in")
        total_expenses = sum(
            t.principal + t.fee for t in transactions if t.direction == "out"
        )
        net_flow = total_income - total_expenses

        expected = opening_balance + net_flow
        diff = expected - closing_balance

        result = {
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_fees": sum(t.fee for t in transactions),
            "net_flow": net_flow,
            "expected_closing": expected,
            "difference": diff,
            "reconciled": abs(diff) <= 1.0,
            "message": "",
        }

        if result["reconciled"]:
            result["message"] = "Balances reconciled successfully"
        else:
            result["message"] = (
                f"Balance mismatch: expected {expected:.2f}, got {closing_balance:.2f} (diff: {diff:.2f})"
            )

        logger.info(result["message"])
        return result
