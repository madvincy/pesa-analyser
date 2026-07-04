"""
Metadata extraction from financial statements.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .patterns import (
    DATE_PATTERNS,
    AMOUNT_PATTERNS,
    METADATA_PATTERNS,
)

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract metadata from statement text."""

    def __init__(self):
        self.date_patterns = DATE_PATTERNS
        self.amount_patterns = AMOUNT_PATTERNS
        self.metadata_patterns = METADATA_PATTERNS

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract metadata from statement text.

        Returns:
            Dict with keys like:
            - account_name
            - account_number
            - statement_period
            - opening_balance
            - closing_balance
            - currency
            - bank_name
            - phone_number
        """
        metadata = {}

        # Try each metadata pattern
        for key, pattern in self.metadata_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                metadata[key] = value.strip()

        # Extract dates
        dates = self._extract_dates(text)
        if dates:
            if len(dates) >= 2:
                metadata["period_start"] = dates[0]
                metadata["period_end"] = dates[-1]
            else:
                metadata["date"] = dates[0]

        # Extract statement period if not found
        if "period_start" not in metadata:
            period = self._extract_period(text)
            if period:
                metadata["statement_period"] = period

        return metadata

    def _extract_dates(self, text: str) -> List[str]:
        """Extract all dates from text."""
        dates = []

        for pattern in self.date_patterns:
            for match in re.finditer(pattern, text):
                dates.append(match.group())

        # Remove duplicates
        return list(dict.fromkeys(dates))

    def _extract_period(self, text: str) -> Optional[str]:
        """Extract statement period."""
        patterns = [
            r"statement\s+period\s*[:.]?\s*([\d/]+\s*[-to]+\s*[\d/]+)",
            r"period\s*[:.]?\s*([\d/]+\s*[-to]+\s*[\d/]+)",
            r"from\s+([\d/]+)\s+to\s+([\d/]+)",
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*[-to]+\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def extract_mpesa_metadata(self, text: str) -> Dict[str, Any]:
        """Extract M-PESA specific metadata."""
        metadata = {}

        # M-PESA specific patterns
        patterns = {
            "phone": r"phone\s*[:.]?\s*([\d\s]+)",
            "balance": r"balance\s*[:.]?\s*([\d,]+\.\d{2})",
            "full_name": r"(?:name|full name)\s*[:.]?\s*([A-Za-z\s]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key == "phone":
                    value = re.sub(r"\s", "", value)
                metadata[key] = value

        return metadata

    def extract_bank_metadata(self, text: str) -> Dict[str, Any]:
        """Extract bank statement specific metadata."""
        metadata = {}

        # Bank specific patterns
        patterns = {
            "account_number": r"account\s*(?:number|no)\s*[:.]?\s*([\d\s]+)",
            "account_name": r"account\s*(?:name|holder)\s*[:.]?\s*([A-Za-z\s]+)",
            "bank_name": r"bank\s*[:.]?\s*([A-Za-z\s]+)",
            "branch": r"branch\s*[:.]?\s*([A-Za-z\s]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key == "account_number":
                    value = re.sub(r"\s", "", value)
                metadata[key] = value

        return metadata
