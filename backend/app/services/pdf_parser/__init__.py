"""
PDF Parser for M-PESA and financial statements.

This package handles parsing of various financial statement formats:
- PDF (M-PESA statements, bank statements)
- CSV
- Excel

It extracts transactions, metadata, and categorizes entries.
"""

from .parser import PDFParser
from .models import Transaction, StatementMetadata, ParsedStatement
from .patterns import (
    # M-PESA patterns
    RECEIPT_PATTERN,
    AMOUNT_PATTERN,
    TX_PATTERN_STRICT,
    TX_PATTERN_LENIENT,
    # Phone patterns
    PHONE_PATTERNS,
    # Date patterns
    DATE_PATTERNS,
    # Indicators
    M_PESA_INDICATORS,
    BANK_INDICATORS,
    # Financial keywords
    FINANCIAL_KEYWORDS,
    # Fuliza patterns
    FULIZA_PATTERNS,
    # Charge patterns
    CHARGE_PATTERNS,
    # Mechanic keywords
    MECHANIC_KEYWORDS,
    # Category patterns
    CATEGORY_PATTERNS,
    CATEGORY_RULES,
    # Known PayBills
    KNOWN_PAYBILLS,
    # Metadata patterns
    METADATA_PATTERNS,
    # Amount patterns
    AMOUNT_PATTERNS,
    # Email pattern
    EMAIL_PATTERN,
    # Fee detection constants
    SMALL_FEE_LIMIT,
)

__all__ = [
    # Main parser
    "PDFParser",
    # Models
    "Transaction",
    "StatementMetadata",
    "ParsedStatement",
    # M-PESA patterns
    "RECEIPT_PATTERN",
    "AMOUNT_PATTERN",
    "TX_PATTERN_STRICT",
    "TX_PATTERN_LENIENT",
    # Phone and date patterns
    "PHONE_PATTERNS",
    "DATE_PATTERNS",
    # Indicators
    "M_PESA_INDICATORS",
    "BANK_INDICATORS",
    "FINANCIAL_KEYWORDS",
    # Fuliza and charges
    "FULIZA_PATTERNS",
    "CHARGE_PATTERNS",
    "MECHANIC_KEYWORDS",
    # Category rules
    "CATEGORY_PATTERNS",
    "CATEGORY_RULES",
    "KNOWN_PAYBILLS",
    # Metadata
    "METADATA_PATTERNS",
    "AMOUNT_PATTERNS",
    "EMAIL_PATTERN",
    # Fee detection constants
    "SMALL_FEE_LIMIT",
]

__version__ = "1.0.0"
