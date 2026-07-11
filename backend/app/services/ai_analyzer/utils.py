"""
Shared utilities for the AI Analyzer.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from .models import TransactionDict, NormalizedTransaction

logger = logging.getLogger(__name__)


def normalize_transaction(tx: Any) -> Dict[str, Any]:
    """
    Normalize a transaction to a dict, handling both dict and Transaction objects.
    """
    if hasattr(tx, "to_dict"):
        # It's a Transaction object - convert to dict
        return tx.to_dict()
    elif isinstance(tx, dict):
        return tx
    else:
        # Try to convert using __dict__
        try:
            return tx.__dict__
        except:
            return {"amount": 0, "description": "", "type": "unknown"}


def get_tx_type(tx: Dict[str, Any]) -> str:
    """
    Get transaction type, handling both 'type' and 'direction' fields.
    """
    tx_type = tx.get("type")
    if tx_type:
        return tx_type
    # Try direction
    direction = tx.get("direction")
    if direction == "in":
        return "income"
    elif direction == "out":
        return "expense"
    return "unknown"


def get_tx_amount(tx: Dict[str, Any]) -> float:
    """
    Get transaction amount, handling 'amount', 'principal', 'paid_in', 'withdrawn'.
    """
    amount = tx.get("amount", 0) or tx.get("principal", 0) or 0
    if amount == 0:
        # Try paid_in or withdrawn
        paid_in = tx.get("paid_in", 0) or 0
        withdrawn = tx.get("withdrawn", 0) or 0
        amount = paid_in or withdrawn or 0
    return abs(float(amount))


def normalize_transactions(transactions: List[Any]) -> List[Dict[str, Any]]:
    """Normalize a list of transactions."""
    return [normalize_transaction(tx) for tx in transactions]


def safe_get(tx: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a transaction dict."""
    return tx.get(key, default)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None


def get_month(date_str: str) -> str:
    """Get month from date string."""
    dt = parse_date(date_str)
    if dt:
        return dt.strftime("%Y-%m")
    return date_str[:7] if len(date_str) >= 7 else "unknown"


def is_valid_amount(value: Any) -> bool:
    """Check if value is a valid amount."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    from .patterns import PHONE_PATTERN

    match = PHONE_PATTERN.search(text)
    return match.group() if match else None


def is_fuliza_transaction(description: str) -> bool:
    """Check if description indicates a Fuliza transaction."""
    from .patterns import FULIZA_KEYWORDS

    desc_lower = description.lower()
    return any(kw in desc_lower for kw in FULIZA_KEYWORDS)


def is_charge_transaction(description: str) -> bool:
    """Check if description indicates a charge/fee transaction."""
    from .patterns import CHARGE_KEYWORDS

    desc_lower = description.lower()
    return any(kw in desc_lower for kw in CHARGE_KEYWORDS)


def is_mechanic_entry(description: str) -> bool:
    """Check if description is a mechanic/internal entry."""
    from .patterns import MECHANIC_KEYWORDS

    desc_lower = description.lower()
    return any(kw in desc_lower for kw in MECHANIC_KEYWORDS)


def is_income_transaction(tx: Dict[str, Any]) -> bool:
    """Check if transaction is income."""
    return get_tx_type(tx) == "income"


def is_expense_transaction(tx: Dict[str, Any]) -> bool:
    """Check if transaction is expense."""
    return get_tx_type(tx) == "expense"


def is_fuliza_drawdown(tx: Dict[str, Any]) -> bool:
    return bool(tx.get("fuliza_used", False))


def is_fuliza_repayment(tx: Dict[str, Any]) -> bool:
    return bool(tx.get("fuliza_repayment", False))


def get_transaction_type(tx: Dict[str, Any]) -> str:
    return tx.get("transaction_type", "")


def get_funding_source(tx: Dict[str, Any]) -> str:
    return tx.get("funding_source", "")


def get_category(tx: Dict[str, Any]) -> str:
    return tx.get("category", "")
