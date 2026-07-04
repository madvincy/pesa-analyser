"""
Utility functions for the PDF parser.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing whitespace
    return text.strip()


def parse_amount(amount_str: str) -> float:
    """Parse amount string to float."""
    if not amount_str:
        return 0.0

    # Remove currency symbols and spaces
    cleaned = re.sub(r"[^\d.,\-]", "", amount_str)
    # Remove commas
    cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


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
        "%d %b %Y",
        "%b %d, %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"KES {amount:,.2f}"


def extract_numbers(text: str) -> List[float]:
    """Extract all numbers from text."""
    return [float(x) for x in re.findall(r"[\d,]+\.\d{2}", text.replace(",", ""))]


def is_float(value: Any) -> bool:
    """Check if value can be converted to float."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def safe_get(dict_obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dict."""
    if not dict_obj:
        return default
    return dict_obj.get(key, default)


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with dict2 taking precedence."""
    result = dict1.copy()
    result.update(dict2)
    return result


def normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format."""
    if not phone:
        return ""

    # Remove spaces and special characters
    cleaned = re.sub(r"[\s\-()]", "", phone)

    # Remove leading 0 or +254
    if cleaned.startswith("0"):
        cleaned = "254" + cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    elif cleaned.startswith("254"):
        pass
    else:
        # Assume it's a local number
        cleaned = "254" + cleaned

    return cleaned


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def is_valid_receipt(receipt: str) -> bool:
    """Check if receipt number is valid."""
    return bool(re.fullmatch(r"[A-Z0-9]{10}", receipt))


def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    if not filename:
        return ""
    parts = filename.rsplit(".", 1)
    return parts[-1].lower() if len(parts) > 1 else ""


def is_supported_format(filename: str) -> bool:
    """Check if file format is supported."""
    ext = get_file_extension(filename)
    return ext in ["pdf", "csv", "xls", "xlsx"]


def log_transaction_summary(transactions: List[Dict[str, Any]]) -> None:
    """Log a summary of transactions."""
    if not transactions:
        logger.info("No transactions to summarize")
        return

    total_income = sum(
        t.get("amount", 0) for t in transactions if t.get("type") == "income"
    )
    total_expenses = sum(
        t.get("amount", 0) for t in transactions if t.get("type") == "expense"
    )

    logger.info("=" * 60)
    logger.info("TRANSACTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total transactions: {len(transactions)}")
    logger.info(f"Total income: KES {total_income:,.2f}")
    logger.info(f"Total expenses: KES {total_expenses:,.2f}")
    logger.info(f"Net cash flow: KES {total_income - total_expenses:,.2f}")
    logger.info("=" * 60)
