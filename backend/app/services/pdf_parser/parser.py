"""
Main PDFParser class - orchestrates parsing of financial statements.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
import pandas as pd
from collections import defaultdict

from .extractor import PDFExtractor, CSVExtractor, ExcelExtractor
from .transaction_parser import TransactionParser  # Fixed import
from .metadata import MetadataExtractor
from .validator import StatementValidator
from .models import (
    ParsedStatement,
    Transaction,
    StatementMetadata,
    MerchantCache,
    CustomerCache,
    Merchant,
    Customer,
    TransactionDirection,
    TransactionType,
)

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Main parser for financial statements.

    Supports:
    - M-PESA PDF statements
    - Bank PDF statements
    - CSV exports
    - Excel files
    """

    def __init__(self, debug: bool = False):
        """
        Initialize the PDF Parser.

        Args:
            debug: Enable debug logging
        """
        self.debug = debug
        self.pdf_extractor = PDFExtractor()
        self.csv_extractor = CSVExtractor()
        self.excel_extractor = ExcelExtractor()
        self.transaction_parser = TransactionParser()
        self.metadata_extractor = MetadataExtractor()
        self.validator = StatementValidator()

        # Caches
        self.merchant_cache = MerchantCache()
        self.customer_cache = CustomerCache()

        if debug:
            logging.getLogger().setLevel(logging.DEBUG)

    def parse_statement(
        self, file_path: Union[str, Path, bytes], password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse a financial statement file.

        Args:
            file_path: Path to file or bytes content
            password: Optional password for encrypted PDFs

        Returns:
            Dict containing:
            - transactions: List of parsed transactions
            - raw_text: Extracted raw text
            - statement_type: Type of statement
            - metadata: Statement metadata
            - summary: Summary statistics
        """
        if isinstance(file_path, (str, Path)):
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            ext = file_path.suffix.lower()
            content = file_path.read_bytes()
        else:
            content = file_path
            ext = ".pdf"  # Default

        # Step 1: Extract raw text
        raw_text, metadata = self.pdf_extractor.extract(content, password)

        # Step 2: Detect statement type early
        statement_type = self._detect_statement_type(raw_text)
        logger.info(f"Detected statement type: {statement_type}")

        # Step 3: Parse based on type
        transactions = []

        if statement_type == "mpesa":
            # Step 3a: Extract ledger rows
            ledger_rows = self.transaction_parser.extract_ledger_rows(raw_text)
            logger.info(f"Extracted {len(ledger_rows)} ledger rows")

            # Step 3b: Normalize receipts into transactions
            transactions = self.transaction_parser.normalize_receipts(
                ledger_rows, self.merchant_cache, self.customer_cache
            )
            logger.info(f"Normalized into {len(transactions)} transactions")

        elif statement_type == "bank":
            transactions = self.transaction_parser.parse_bank(raw_text)

        else:
            # Generic parser for unknown types
            transactions = self.transaction_parser.parse_generic(raw_text)

        # Step 4: Enrich transactions (add categories, etc.)
        transactions = self._enrich_transactions(transactions)

        # Step 5: Validate and reconcile
        self.validator.validate_transactions(transactions, metadata)

        # Step 6: Build receipt index for O(1) lookups
        receipt_index = {tx.receipt: tx for tx in transactions if tx.receipt}

        # Step 7: Create parsed statement
        parsed = ParsedStatement(
            statement_type=statement_type,
            transactions=transactions,
            raw_text=raw_text,
            metadata=StatementMetadata(
                account_name=metadata.get("account_name"),
                account_number=metadata.get("account_number"),
                bank_name=metadata.get("bank_name"),
                phone=metadata.get("phone"),
                period_start=metadata.get("period_start"),
                period_end=metadata.get("period_end"),
                opening_balance=float(metadata.get("opening_balance", 0)),
                closing_balance=float(metadata.get("closing_balance", 0)),
            ),
            merchant_cache=self.merchant_cache,
            customer_cache=self.customer_cache,
            receipt_index=receipt_index,
        )

        # Step 8: Generate summaries
        summary = parsed.get_summary()
        monthly_summary = parsed.get_monthly_summary()
        merchant_summary = parsed.get_merchant_summary()

        # Step 9: Return as dict
        return {
            "transactions": [t.to_dict() for t in transactions],
            "raw_text": raw_text,
            "statement_type": statement_type,
            "metadata": metadata,
            "summary": summary,
            "monthly_summary": monthly_summary,
            "merchant_summary": merchant_summary,
        }

    def parse_csv(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse a CSV file."""
        return self.parse_statement(file_path)

    def parse_excel(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse an Excel file."""
        return self.parse_statement(file_path)

    def _detect_statement_type(self, raw_text: str) -> str:
        """
        Detect the type of statement from raw text.

        Checks first few lines for faster detection.
        """
        # Check first 2000 characters for indicators
        preview = raw_text[:2000].lower()

        mpesa_indicators = ["mpesa", "m-pesa", "safaricom", "fuliza", "m-shwari"]
        if any(ind in preview for ind in mpesa_indicators):
            return "mpesa"

        bank_indicators = ["kcb", "equity", "stanbic", "ncba", "absa", "cooperative"]
        if any(ind in preview for ind in bank_indicators):
            return "bank"

        return "unknown"

    def _enrich_transactions(
        self, transactions: List[Transaction]
    ) -> List[Transaction]:
        """
        Enrich transactions with additional data.

        - Adds categories
        - Extracts merchant information
        - Determines funding source
        """
        for tx in transactions:
            if tx.description:
                # Parse details
                parsed = self.transaction_parser.parse_transaction_details(
                    tx.description
                )
                tx.parsed = parsed

                # Add category
                if not tx.parsed.get("category"):
                    category = self.transaction_parser._categorize_transaction(
                        tx.description
                    )
                    tx.parsed["category"] = category

                # Update merchant info
                if parsed.get("till"):
                    tx.till_number = parsed.get("till")
                    merchant = self.merchant_cache.get(parsed["till"])
                    if merchant and not tx.merchant_name:
                        tx.merchant_name = merchant.name

                if parsed.get("paybill"):
                    tx.paybill_number = parsed.get("paybill")
                    merchant = self.merchant_cache.get(parsed["paybill"])
                    if merchant and not tx.merchant_name:
                        tx.merchant_name = merchant.name

                # Update customer info
                if parsed.get("phone"):
                    tx.customer_phone = parsed.get("phone")
                    customer = self.customer_cache.get(parsed["phone"])
                    if customer and not tx.customer_name:
                        tx.customer_name = customer.name

                if parsed.get("name"):
                    if tx.direction == "in":
                        tx.customer_name = parsed.get("name")
                    else:
                        tx.merchant_name = parsed.get("name")

        return transactions
