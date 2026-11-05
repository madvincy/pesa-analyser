"""
File extraction modules for PDF, CSV, and Excel files.
"""

import io
import re
import logging
from typing import Callable, Optional, List, Dict, Any, Tuple, Union, Sequence
from pathlib import Path
import pdfplumber
import PyPDF2
import pandas as pd

from .models import Transaction, StatementMetadata

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract content from PDF files."""

    def __init__(self):
        self.encryption_check_pattern = re.compile(r"/Encrypt|/Encryption")

    def extract(
        self,
        content: Union[bytes, str, Path],
        password: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text and metadata from a PDF.

        Returns:
            Tuple of (raw_text, metadata)
        """
        raw_text_parts: List[str] = []
        metadata = {}
        source = (
            content
            if isinstance(content, (str, Path))
            else io.BytesIO(content)
        )

        # Try pdfplumber first (better table extraction)
        try:
            open_kwargs = {}
            if password:
                open_kwargs["password"] = password

            with pdfplumber.open(source, **open_kwargs) as pdf:
                metadata = pdf.metadata or {}
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        raw_text_parts.append(page_text)
                    else:
                        # Try table extraction
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    if row:
                                        # Convert None to empty string and join
                                        row_text = " ".join(
                                            str(c) if c is not None else "" for c in row
                                        )
                                        raw_text_parts.append(row_text)
                    if progress_callback:
                        progress_callback(page_num + 1, page_count)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

        # Fallback to PyPDF2 if needed
        raw_text = "\n".join(raw_text_parts)
        if len(raw_text.strip()) < 50:
            raw_text_parts = []
            try:
                if isinstance(source, io.BytesIO):
                    source.seek(0)
                reader = PyPDF2.PdfReader(source)
                if reader.is_encrypted and password:
                    reader.decrypt(password)

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        raw_text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"PyPDF2 extraction failed: {e}")

        raw_text = "\n".join(raw_text_parts)
        return raw_text, metadata

    def extract_tables(
        self, content: bytes, password: Optional[str] = None
    ) -> List[Transaction]:
        """
        Extract tables from PDF and convert to transactions.
        """
        transactions = []

        try:
            open_kwargs = {}
            if password:
                open_kwargs["password"] = password

            with pdfplumber.open(io.BytesIO(content), **open_kwargs) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            # Filter out None values and convert to list of strings
                            clean_row = [
                                str(cell) if cell is not None else "" for cell in row
                            ]
                            tx = self._parse_table_row(clean_row)
                            if tx:
                                transactions.append(tx)
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")

        return transactions

    def _parse_table_row(self, row: List[str]) -> Optional[Transaction]:
        """
        Parse a row from a table into a Transaction.

        Args:
            row: List of strings (empty strings for None values)
        """
        if not row or len(row) < 3:
            return None

        # Filter out empty strings
        non_empty = [cell for cell in row if cell and cell.strip()]
        if len(non_empty) < 3:
            return None

        # Try to identify columns
        try:
            # Look for amount
            amount = None
            for cell in non_empty:
                if cell and isinstance(cell, str):
                    # Try to parse as amount
                    cleaned = re.sub(r"[^\d.,\-]", "", cell)
                    if cleaned:
                        try:
                            # Handle both comma and dot decimal separators
                            cleaned = cleaned.replace(",", "")
                            amount = float(cleaned)
                            break
                        except ValueError:
                            continue

            if amount is None or amount == 0:
                return None

            # Look for date
            date = None
            for cell in non_empty:
                if cell and isinstance(cell, str):
                    # Try to parse as date
                    date_match = (
                        re.search(r"\d{4}-\d{2}-\d{2}", cell)
                        or re.search(r"\d{2}/\d{2}/\d{4}", cell)
                        or re.search(r"\d{2}-\d{2}-\d{4}", cell)
                    )
                    if date_match:
                        date = date_match.group()
                        break

            # If no date found, try to find a date-like pattern in the row
            if not date:
                row_text = " ".join(non_empty)
                date_match = re.search(r"\d{4}-\d{2}-\d{2}", row_text) or re.search(
                    r"\d{2}/\d{2}/\d{4}", row_text
                )
                if date_match:
                    date = date_match.group()

            # Use description from remaining cells
            description_parts = []
            for cell in non_empty:
                if cell and cell != date and str(amount) not in cell:
                    # Check if this cell might be the description
                    description_parts.append(cell)

            description = " ".join(description_parts)

            # Clean up description
            description = re.sub(r"\s+", " ", description).strip()
            if not description:
                description = " ".join(non_empty[:3])

            if date and amount:
                # Generate a dummy receipt for table-extracted transactions
                receipt = (
                    f"TBL_{date}_{int(abs(amount))}" if date else f"TBL_{abs(amount)}"
                )
                direction = "out" if amount < 0 else "in"

                return Transaction(
                    receipt=receipt,
                    date=date,
                    time="00:00:00",
                    description=description[:200],
                    details=description[:200],
                    direction=direction,
                    principal=abs(amount),
                    paid_in=amount if amount > 0 else 0.0,
                    withdrawn=abs(amount) if amount < 0 else 0.0,
                    transaction_type="unknown",
                )
        except Exception as e:
            logger.debug(f"Error parsing table row: {e}")

        return None


class CSVExtractor:
    """Extract content from CSV files."""

    def extract(
        self, content: Union[bytes, str, Path]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text and metadata from CSV.
        """
        try:
            source = content if isinstance(content, (str, Path)) else io.BytesIO(content)
            df = pd.read_csv(source, nrows=100)
            raw_text = " ".join(df.columns.astype(str))
            raw_text += " " + " ".join(df.head(100).astype(str).values.flatten())

            metadata = {
                "columns": df.columns.tolist(),
                "row_count": None,
                "shape": df.shape,
            }

            return raw_text, metadata
        except Exception as e:
            logger.error(f"CSV extraction failed: {e}")
            return "", {}

    def parse_transactions(
        self, content: Union[bytes, str, Path]
    ) -> List[Transaction]:
        """
        Parse transactions from CSV.
        """
        try:
            transactions = []
            source = content if isinstance(content, (str, Path)) else io.BytesIO(content)
            frames = (
                pd.read_csv(source, chunksize=5000)
                if isinstance(content, (str, Path))
                else [pd.read_csv(source)]
            )

            row_offset = 0
            for df in frames:
                amount_col = next(
                    (
                        col
                        for col in df.columns
                        if any(
                            key in str(col).lower()
                            for key in (
                                "amount",
                                "value",
                                "credit",
                                "debit",
                                "withdrawal",
                                "deposit",
                            )
                        )
                    ),
                    None,
                )
                date_col = next(
                    (
                        col
                        for col in df.columns
                        if any(
                            key in str(col).lower()
                            for key in ("date", "time", "transaction_date", "posting_date")
                        )
                    ),
                    None,
                )
                desc_col = next(
                    (
                        col
                        for col in df.columns
                        if any(
                            key in str(col).lower()
                            for key in (
                                "description",
                                "details",
                                "narration",
                                "particulars",
                                "memo",
                            )
                        )
                    ),
                    None,
                )
                if amount_col is None:
                    return []

                for row_number, (_, row) in enumerate(df.iterrows()):
                    try:
                        amount = (
                            float(row[amount_col])
                            if pd.notna(row[amount_col])
                            else 0
                        )
                        if amount == 0:
                            continue

                        date = ""
                        if date_col and pd.notna(row[date_col]):
                            date_val = row[date_col]
                            date = (
                                date_val.strftime("%Y-%m-%d")
                                if isinstance(date_val, pd.Timestamp)
                                else str(date_val)[:10]
                            )

                        description = (
                            str(row[desc_col])
                            if desc_col and pd.notna(row[desc_col])
                            else ""
                        )
                        row_id = row_offset + row_number
                        receipt = f"CSV_{date}_{row_id}" if date else f"CSV_{row_id}"
                        transactions.append(
                            Transaction(
                                receipt=receipt,
                                date=date,
                                time="00:00:00",
                                description=description[:200],
                                details=description[:200],
                                direction="in" if amount > 0 else "out",
                                principal=abs(amount),
                                paid_in=amount if amount > 0 else 0.0,
                                withdrawn=abs(amount) if amount < 0 else 0.0,
                                transaction_type="unknown",
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Error parsing CSV row: {e}")
                row_offset += len(df)

            return transactions
        except Exception as e:
            logger.error(f"CSV transaction parsing failed: {e}")
            return []


class ExcelExtractor:
    """Extract content from Excel files."""

    def extract(
        self, content: Union[bytes, str, Path]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text and metadata from Excel.
        """
        try:
            source = content if isinstance(content, (str, Path)) else io.BytesIO(content)
            df = pd.read_excel(source, nrows=100)
            raw_text = " ".join(df.columns.astype(str))
            raw_text += " " + " ".join(df.head(100).astype(str).values.flatten())

            metadata = {
                "columns": df.columns.tolist(),
                "row_count": None,
                "shape": df.shape,
            }

            return raw_text, metadata
        except Exception as e:
            logger.error(f"Excel extraction failed: {e}")
            return "", {}

    def parse_transactions(
        self, content: Union[bytes, str, Path]
    ) -> List[Transaction]:
        """
        Parse transactions from Excel.
        """
        if isinstance(content, (str, Path)) and Path(content).suffix.lower() == ".xlsx":
            return self._parse_xlsx_stream(content)

        try:
            source = content if isinstance(content, (str, Path)) else io.BytesIO(content)
            df = pd.read_excel(source)
            transactions = []

            # Try to identify columns
            amount_col = None
            date_col = None
            desc_col = None

            for col in df.columns:
                col_lower = col.lower()
                if any(
                    k in col_lower
                    for k in [
                        "amount",
                        "value",
                        "credit",
                        "debit",
                        "withdrawal",
                        "deposit",
                    ]
                ):
                    amount_col = col
                elif any(
                    k in col_lower
                    for k in ["date", "time", "transaction_date", "posting_date"]
                ):
                    date_col = col
                elif any(
                    k in col_lower
                    for k in [
                        "description",
                        "details",
                        "narration",
                        "particulars",
                        "memo",
                    ]
                ):
                    desc_col = col

            if not amount_col:
                return []

            for idx, row in df.iterrows():
                try:
                    amount = float(row[amount_col]) if pd.notna(row[amount_col]) else 0
                    if amount == 0:
                        continue

                    date = ""
                    if date_col and pd.notna(row[date_col]):
                        date_val = row[date_col]
                        if isinstance(date_val, pd.Timestamp):
                            date = date_val.strftime("%Y-%m-%d")
                        else:
                            date = str(date_val)[:10]

                    description = ""
                    if desc_col and pd.notna(row[desc_col]):
                        description = str(row[desc_col])

                    # Generate dummy receipt for Excel transactions
                    receipt = f"XLS_{date}_{idx}" if date else f"XLS_{idx}"
                    direction = "in" if amount > 0 else "out"

                    transactions.append(
                        Transaction(
                            receipt=receipt,
                            date=date,
                            time="00:00:00",
                            description=description[:200],
                            details=description[:200],
                            direction=direction,
                            principal=abs(amount),
                            paid_in=amount if amount > 0 else 0.0,
                            withdrawn=abs(amount) if amount < 0 else 0.0,
                            transaction_type="unknown",
                        )
                    )
                except Exception as e:
                    logger.debug(f"Error parsing Excel row: {e}")
                    continue

            return transactions
        except Exception as e:
            logger.error(f"Excel transaction parsing failed: {e}")
            return []

    def _parse_xlsx_stream(self, file_path: Union[str, Path]) -> List[Transaction]:
        from openpyxl import load_workbook

        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            rows = workbook.active.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                return []

            def column_index(keywords: Sequence[str]) -> Optional[int]:
                return next(
                    (
                        index
                        for index, value in enumerate(headers)
                        if any(
                            keyword in str(value or "").lower()
                            for keyword in keywords
                        )
                    ),
                    None,
                )

            amount_col = column_index(
                ("amount", "value", "credit", "debit", "withdrawal", "deposit")
            )
            date_col = column_index(
                ("date", "time", "transaction_date", "posting_date")
            )
            desc_col = column_index(
                ("description", "details", "narration", "particulars", "memo")
            )
            if amount_col is None:
                return []

            transactions = []
            for row_number, row in enumerate(rows):
                try:
                    value = row[amount_col] if amount_col < len(row) else None
                    amount = float(value) if value is not None else 0
                    if amount == 0:
                        continue

                    date_value = (
                        row[date_col]
                        if date_col is not None and date_col < len(row)
                        else None
                    )
                    date = (
                        date_value.strftime("%Y-%m-%d")
                        if hasattr(date_value, "strftime")
                        else str(date_value)[:10]
                        if date_value is not None
                        else ""
                    )
                    description_value = (
                        row[desc_col]
                        if desc_col is not None and desc_col < len(row)
                        else None
                    )
                    description = str(description_value or "")
                    receipt = (
                        f"XLS_{date}_{row_number}"
                        if date
                        else f"XLS_{row_number}"
                    )
                    transactions.append(
                        Transaction(
                            receipt=receipt,
                            date=date,
                            time="00:00:00",
                            description=description[:200],
                            details=description[:200],
                            direction="in" if amount > 0 else "out",
                            principal=abs(amount),
                            paid_in=amount if amount > 0 else 0.0,
                            withdrawn=abs(amount) if amount < 0 else 0.0,
                            transaction_type="unknown",
                        )
                    )
                except (TypeError, ValueError, IndexError) as e:
                    logger.debug("Error parsing Excel row %s: %s", row_number, e)
            return transactions
        finally:
            workbook.close()
