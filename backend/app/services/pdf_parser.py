import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import magic
import pandas as pd
import pdfplumber
import PyPDF2

logger = logging.getLogger(__name__)


class PDFParser:
    def __init__(self) -> None:
        # ─── M-PESA Statement Patterns ──────────────────────────────────────
        self.patterns = {
            # Main M-PESA transaction pattern - matches each row in the table
            "mpesa_transaction": re.compile(
                r'([A-Z0-9]{10})\s+'           # Receipt No (e.g., UF3PZ6NAAG)
                r'(\d{4}-\d{2}-\d{2})\s+'      # Date (e.g., 2026-06-03)
                r'(\d{2}:\d{2}:\d{2})\s+'      # Time (e.g., 19:25:51)
                r'(.+?)\s+'                    # Details
                r'(Completed|Failed|Pending)\s+'  # Status
                r'(-?[\d,]+\.\d{2})\s+'        # Paid In
                r'(-?[\d,]+\.\d{2})\s+'        # Withdrawn
                r'([\d,]+\.\d{2})'             # Balance
            ),
            "mpesa_receipt": re.compile(r'[A-Z0-9]{10}'),
            "fuliza": re.compile(r'(?:FULIZA|Fuliza|OverDraft|OD Loan)'),
            "m_shwari": re.compile(r'(?:M-SHWARI|MShwari)'),
            "paybill": re.compile(r'PayBill\s+(\d+)'),
            "till": re.compile(r'Till\s+(\d+)'),
            "amount": re.compile(r'([\d,]+\.\d{2})'),
            "phone": re.compile(r'07\d{8}|01\d{8}|2547\d{8}'),
            "balance": re.compile(r'Balance[:\s]*([\d,]+\.\d{2})', re.IGNORECASE),
            "date_range": re.compile(
                r'(\d{4}-\d{2}-\d{2})\s*[-to]+\s*(\d{4}-\d{2}-\d{2})',
                re.IGNORECASE,
            ),
            "account_number": re.compile(
                r'Account\s*(?:No|Number)[:\s]*([\d-]+)', re.IGNORECASE
            ),
            "customer_name": re.compile(
                r'(?:Customer|Name)[:\s]*([A-Za-z\s]+)', re.IGNORECASE
            ),
            "bank_name": re.compile(
                r'(KCB|Equity|Cooperative|Stanbic|ABSA|NCBA|I&M'
                r'|Standard Chartered|Barclays|Absa)',
                re.IGNORECASE,
            ),
            "mpesa": re.compile(r'(?:M-PESA|MPESA)', re.IGNORECASE),
            "transaction_fee": re.compile(
                r'(?:Fee|Charge)[:\s]*([\d,]+\.\d{2})', re.IGNORECASE
            ),
            "airtime": re.compile(r'(?:Airtime|Scratch Card|Bundle)', re.IGNORECASE),
            "betting": re.compile(
                r'(?:Bet|Gamble|Casino|Sportpesa|Betika|Shabiki)',
                re.IGNORECASE,
            ),
            "received_money": re.compile(
                r'Funds received from|Received from|Received Money',
                re.IGNORECASE
            ),
            "send_money": re.compile(r'Send Money|Transfer|Sent to', re.IGNORECASE),
            "agent_deposit": re.compile(r'Deposit of Funds at Agent', re.IGNORECASE),
            "agent_withdrawal": re.compile(r'Withdrawal At Agent', re.IGNORECASE),
            "merchant_payment": re.compile(r'Merchant Payment|Buy Goods|Till', re.IGNORECASE),
            "salary": re.compile(r'Salary Payment from', re.IGNORECASE),
        }

        self.financial_keywords = [
            "amount", "balance", "credit", "debit", "transaction",
            "mpesa", "m-pesa", "bank", "account", "withdrawal",
            "deposit", "payment", "transfer", "fee", "charge",
            "statement", "summary", "period", "date", "opening",
            "closing", "total", "currency", "kes", "shillings",
            "sender", "receiver", "recipient", "receipt",
        ]

        self.bank_keywords = [
            "kcb", "equity", "cooperative", "stanbic", "absa",
            "ncba", "i&m", "standard chartered", "barclays",
        ]

    # ─── Public parse methods ─────────────────────────────────────────────────

    def parse_statement(
        self, file_path: str, password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse a PDF financial statement"""
        logger.info("=" * 80)
        logger.info("🔵 [PDF PARSER] parse_statement() called")
        logger.info(f"   File: {file_path}")
        logger.info(f"   Password provided: {bool(password)}")
        logger.info("=" * 80)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("File is empty.")

        with open(file_path, "rb") as f:
            file_content = f.read()

        logger.info(f"📄 File size: {file_size} bytes")

        # Validate
        is_valid, message = self._validate_financial_statement(
            file_content, file_path, password
        )
        if not is_valid:
            raise ValueError(message)

        # Extract text
        logger.info("🔍 Extracting text from PDF...")
        text = self._extract_text_from_pdf(file_content, password)

        logger.info(f"📄 Extracted {len(text)} characters of text")
        if text:
            logger.info(f"📄 Text preview (first 500 chars):\n{text[:500]}...")
        else:
            logger.error("❌ No text extracted from PDF!")
            raise ValueError("Could not extract text from PDF. The file may be empty, scanned, or corrupted.")

        # Extract transactions
        logger.info("🔍 Extracting transactions from text...")
        transactions = self._extract_transactions(text)

        statement_type = self._detect_statement_type(text)
        metadata = self._extract_metadata(text)
        summary = self._calculate_summary(transactions)

        logger.info("=" * 80)
        logger.info(f"✅ [PDF PARSER] parse_statement() complete")
        logger.info(f"   Transactions: {len(transactions)}")
        logger.info(f"   Statement type: {statement_type}")
        logger.info("=" * 80)

        return {
            "transactions": transactions,
            "statement_type": statement_type,
            "metadata": metadata,
            "summary": summary,
            "total_pages": self._estimate_pages(text),
            "text_preview": text[:1000],
            "file_size": file_size,
            "file_name": os.path.basename(file_path),
            "parsed_at": datetime.now().isoformat(),
            "raw_text": text,  # Include full raw text for debugging
        }

    def parse_csv(self, file_path: str) -> Dict[str, Any]:
        """Parse a CSV financial statement"""
        logger.info(f"🔵 [PDF PARSER] parse_csv() called: {file_path}")
        try:
            df = pd.read_csv(file_path)
            transactions = self._df_to_transactions(df)
            return {
                "transactions": transactions,
                "statement_type": "csv",
                "metadata": {"columns": df.columns.tolist()},
                "summary": self._calculate_summary(transactions),
                "file_name": os.path.basename(file_path),
                "parsed_at": datetime.now().isoformat(),
                "raw_text": df.to_string()[:1000],
            }
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            raise ValueError(f"Failed to parse CSV: {e}")

    def parse_excel(self, file_path: str) -> Dict[str, Any]:
        """Parse an Excel financial statement"""
        logger.info(f"🔵 [PDF PARSER] parse_excel() called: {file_path}")
        try:
            df = pd.read_excel(file_path)
            transactions = self._df_to_transactions(df)
            return {
                "transactions": transactions,
                "statement_type": "excel",
                "metadata": {"columns": df.columns.tolist()},
                "summary": self._calculate_summary(transactions),
                "file_name": os.path.basename(file_path),
                "parsed_at": datetime.now().isoformat(),
                "raw_text": df.to_string()[:1000],
            }
        except Exception as e:
            logger.error(f"Excel parse error: {e}")
            raise ValueError(f"Failed to parse Excel: {e}")

    # ─── Text extraction ──────────────────────────────────────────────────────

    def _extract_text_from_pdf(
        self, file_content: bytes, password: Optional[str] = None
    ) -> str:
        """Extract text from PDF with better table support."""
        logger.info("🔍 [PDF PARSER] _extract_text_from_pdf() called")

        text = ""

        # ── Method 1: pdfplumber ──────────────────────────────────────────
        try:
            open_kwargs: Dict[str, Any] = {}
            if password:
                open_kwargs["password"] = password

            logger.info("   Using pdfplumber...")
            with pdfplumber.open(io.BytesIO(file_content), **open_kwargs) as pdf:
                logger.info(f"   PDF has {len(pdf.pages)} pages")

                for i, page in enumerate(pdf.pages):
                    logger.debug(f"   Processing page {i+1}...")

                    # Try to extract text
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                        logger.debug(f"   Page {i+1}: {len(page_text)} chars from extract_text()")
                    else:
                        logger.debug(f"   Page {i+1}: No text from extract_text()")

                    # Also extract tables - CRITICAL for M-PESA statements
                    tables = page.extract_tables()
                    if tables:
                        table_count = len(tables)
                        logger.debug(f"   Page {i+1}: Found {table_count} tables")

                        for table_idx, table in enumerate(tables):
                            row_count = len(table) if table else 0
                            logger.debug(f"   Table {table_idx+1}: {row_count} rows")

                            for row in table:
                                if row:
                                    # Join row cells with spaces
                                    row_text = " ".join(str(cell) for cell in row if cell and str(cell).strip())
                                    if row_text:
                                        text += row_text + "\n"
                                        logger.debug(f"   Table row: {row_text[:100]}...")

                    # If no text was extracted, try with different settings
                    if not page_text and not tables:
                        logger.warning(f"   Page {i+1}: No text or tables found - trying with tolerance...")
                        try:
                            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
                            if page_text:
                                text += page_text + "\n"
                                logger.debug(f"   Page {i+1}: {len(page_text)} chars with tolerance")
                        except Exception as e:
                            logger.debug(f"   Page {i+1} tolerance extraction failed: {e}")

            if text.strip():
                logger.info(f"✅ pdfplumber extracted {len(text)} chars")
                return text
            else:
                logger.warning("⚠️ pdfplumber extracted no text")

        except Exception as e:
            logger.warning(f"⚠️ pdfplumber failed: {e}")

        # ── Method 2: PyPDF2 (fallback) ─────────────────────────────────────
        logger.info("   Falling back to PyPDF2...")
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_content))

            if reader.is_encrypted:
                pwd = password or ""
                result = reader.decrypt(pwd)
                if result == 0:
                    if password:
                        raise ValueError("Incorrect PDF password. Please try again.")
                    else:
                        raise ValueError("PDF is password protected. Please provide the password.")
                logger.info(f"   PyPDF2 decrypted PDF (result={result})")

            logger.info(f"   PyPDF2: {len(reader.pages)} pages")
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                    logger.debug(f"   PyPDF2 Page {i+1}: {len(page_text)} chars")

            if text.strip():
                logger.info(f"✅ PyPDF2 extracted {len(text)} chars")
                return text
            else:
                logger.warning("⚠️ PyPDF2 extracted no text")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ PyPDF2 failed: {e}")

        logger.error("❌ No text extracted from PDF by any method")
        return text

    # ─── Validation ───────────────────────────────────────────────────────────

    def _validate_financial_statement(
        self,
        file_content: bytes,
        file_path: str,
        password: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validate the file is a financial statement"""
        logger.info("🔍 [PDF PARSER] _validate_financial_statement() called")

        try:
            ext = os.path.splitext(file_path)[1].lower()
            valid_extensions = [".pdf", ".csv", ".xls", ".xlsx"]

            if ext not in valid_extensions:
                return False, f"Unsupported format: {ext}"

            if len(file_content) > 50 * 1024 * 1024:
                return False, "File size exceeds 50 MB."

            # Magic bytes check
            try:
                file_type = magic.from_buffer(file_content[:1024], mime=True)
                if ext == ".pdf" and "pdf" not in file_type.lower():
                    return False, "File does not appear to be a valid PDF."
            except Exception as e:
                logger.warning(f"magic check failed: {e}")

            # Text extraction + keyword check
            try:
                text = self._extract_text_from_pdf(file_content, password)
            except ValueError as e:
                return False, str(e)

            if not text or len(text.strip()) < 50:
                logger.warning("Could not extract text — skipping keyword check")
                return True, "File passes basic validation (no text extracted)"

            text_lower = text.lower()
            keyword_count = sum(1 for kw in self.financial_keywords if kw in text_lower)

            logger.info(f"🔍 Found {keyword_count} financial keywords")

            if keyword_count < 3:
                return (
                    False,
                    "The file does not appear to be a financial statement. "
                    "Please upload a bank or M-PESA statement.",
                )

            return True, "Valid financial statement"

        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            return False, f"Validation failed: {e}"

    # ─── Transaction extraction ───────────────────────────────────────────────

    def _extract_transactions(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract transactions from M-PESA statement text.

        The actual format from the PDF:
        Receipt No.    Completion Time    Details    Transaction Status    Paid In    Withdrawn    Balance
        UF3PZ6NAAG     2026-06-03 19:25:51 OD Loan Repayment...           Completed  -200.00     0.00

        This handles multi-line Details fields.
        """
        logger.info("=" * 80)
        logger.info("🔍 [PDF PARSER] _extract_transactions() called")
        logger.info(f"   Text length: {len(text)} characters")

        # ─── CRITICAL: Log the raw text for debugging ──────────────────────────
        logger.info("📄 RAW TEXT PREVIEW (first 2000 chars):")
        logger.info("-" * 60)
        logger.info(text[:2000])
        logger.info("-" * 60)

        # ─── Also log lines that might contain transactions ────────────────────
        lines = text.split('\n')
        logger.info(f"📄 Total lines: {len(lines)}")
        logger.info("📄 First 30 lines:")
        for i, line in enumerate(lines[:30]):
            if line.strip():
                logger.info(f"   Line {i+1}: {repr(line[:150])}")
        logger.info("=" * 80)

        transactions: List[Dict[str, Any]] = []
        seen: set = set()

        if not text:
            logger.error("❌ No text provided to _extract_transactions()")
            return transactions

        # ─── Check if text contains M-PESA keywords ──────────────────────────
        has_mpesa = "M-PESA" in text or "MPESA" in text
        has_receipt = bool(re.search(r'[A-Z0-9]{10}', text))
        has_completed = "Completed" in text

        logger.info(f"🔍 Text analysis:")
        logger.info(f"   M-PESA detected: {has_mpesa}")
        logger.info(f"   Receipt pattern found: {has_receipt}")
        logger.info(f"   'Completed' found: {has_completed}")

        if not has_mpesa and not has_receipt and not has_completed:
            logger.warning("⚠️ Text doesn't appear to contain M-PESA data!")
            logger.info("   Showing first 20 lines for debugging:")
            for i, line in enumerate(lines[:20]):
                if line.strip():
                    logger.info(f"   Line {i+1}: {line[:100]}")
            return transactions

        # ─── Try multiple patterns ──────────────────────────────────────────────
        patterns_to_try = [
            # Pattern 1: Standard format with all fields
            re.compile(
                r'([A-Z0-9]{10})\s+'
                r'(\d{4}-\d{2}-\d{2})\s+'
                r'(\d{2}:\d{2}:\d{2})\s+'
                r'(.+?)\s+'
                r'(Completed|Failed|Pending)\s+'
                r'(-?[\d,]+\.\d{2})\s+'
                r'(-?[\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})'
            ),
            # Pattern 2: With DOTALL flag for multi-line details
            re.compile(
                r'([A-Z0-9]{10})\s+'
                r'(\d{4}-\d{2}-\d{2})\s+'
                r'(\d{2}:\d{2}:\d{2})\s+'
                r'(.+?)\s+'
                r'(Completed|Failed|Pending)\s+'
                r'([\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})',
                re.DOTALL
            ),
            # Pattern 3: Without status field
            re.compile(
                r'([A-Z0-9]{10})\s+'
                r'(\d{4}-\d{2}-\d{2})\s+'
                r'(\d{2}:\d{2}:\d{2})\s+'
                r'(.+?)\s+'
                r'([\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})'
            ),
            # Pattern 4: Simple - just receipt + date + amount
            re.compile(
                r'([A-Z0-9]{10})\s+'
                r'(\d{4}-\d{2}-\d{2})\s+'
                r'(.+?)\s+'
                r'([\d,]+\.\d{2})'
            ),
            # Pattern 5: Very lenient - receipt, date, details, amounts
            re.compile(
                r'([A-Z0-9]{10})\s+'
                r'(\d{4}-\d{2}-\d{2})\s+'
                r'(\d{2}:\d{2}:\d{2})\s+'
                r'([^0-9]+?)\s+'
                r'([\d,]+\.\d{2})\s+'
                r'([\d,]+\.\d{2})',
                re.DOTALL
            ),
        ]

        all_matches = []
        pattern_used = None
        for idx, pattern in enumerate(patterns_to_try):
            matches = pattern.findall(text)
            logger.info(f"   Pattern {idx+1}: Found {len(matches)} matches")
            if matches:
                all_matches = matches
                pattern_used = idx + 1
                logger.info(f"   Using Pattern {idx+1}")
                break

        if not all_matches:
            # Try finding receipt numbers and extract manually
            logger.info("🔍 No pattern matches, trying receipt-based extraction...")
            receipt_pattern = re.compile(r'([A-Z0-9]{10})')
            receipt_matches = receipt_pattern.findall(text)
            logger.info(f"   Found {len(receipt_matches)} receipt numbers")

            # Show first 10 receipts with context
            for idx, receipt in enumerate(receipt_matches[:10]):
                logger.info(f"   Receipt {idx+1}: {receipt}")
                # Find context around receipt
                pos = text.find(receipt)
                if pos != -1:
                    context = text[pos:pos+250]
                    logger.info(f"   Context: {repr(context)}")

            logger.warning("⚠️ No matches found with any pattern!")
            return transactions

        # Process matches
        for match_idx, match in enumerate(all_matches):
            try:
                logger.debug(f"   Processing match {match_idx+1}: {match}")

                if len(match) == 8:
                    receipt, date_str, time_str, details, status, paid_in_str, withdrawn_str, balance_str = match
                elif len(match) == 7:
                    receipt, date_str, time_str, details, paid_in_str, withdrawn_str, balance_str = match
                    status = "Completed"
                elif len(match) == 4:
                    # Simple pattern: receipt, date, details, amount
                    receipt, date_str, details, amount_str = match
                    time_str = "00:00:00"
                    status = "Completed"
                    amount = float(amount_str.replace(',', ''))
                    if amount > 0:
                        paid_in_str = amount_str
                        withdrawn_str = "0.00"
                        tx_type = "income"
                    else:
                        paid_in_str = "0.00"
                        withdrawn_str = amount_str
                        tx_type = "expense"
                        amount = abs(amount)
                    balance_str = "0.00"
                elif len(match) == 6:
                    # Pattern 5: receipt, date, time, details, amount1, amount2
                    receipt, date_str, time_str, details, amt1, amt2 = match
                    status = "Completed"
                    paid_in_str = amt1
                    withdrawn_str = amt2
                    balance_str = "0.00"
                else:
                    logger.debug(f"   Match {match_idx+1}: Unexpected length {len(match)}, skipping")
                    continue

                # Clean amounts
                paid_in = float(paid_in_str.replace(',', '')) if paid_in_str else 0.0
                withdrawn = float(withdrawn_str.replace(',', '')) if withdrawn_str else 0.0
                balance = float(balance_str.replace(',', '')) if balance_str else 0.0

                # Determine transaction type
                if paid_in > 0:
                    amount = paid_in
                    tx_type = "income"
                elif withdrawn > 0:
                    amount = withdrawn
                    tx_type = "expense"
                else:
                    amount = 0
                    tx_type = "unknown"

                # Clean details
                details = re.sub(r'\s+', ' ', details).strip()

                tx = {
                    "receipt": receipt,
                    "date": date_str,
                    "time": time_str,
                    "description": details,
                    "status": status,
                    "paid_in": paid_in,
                    "withdrawn": withdrawn,
                    "balance": balance,
                    "amount": amount,
                    "type": tx_type,
                }

                # ── Category detection ──────────────────────────────────────
                desc_lower = details.lower()

                if "fuliza" in desc_lower or "overdraft" in desc_lower:
                    tx["fuliza"] = True
                    tx["category"] = "Fuliza"
                elif "salary" in desc_lower:
                    tx["salary"] = True
                    tx["category"] = "Salary"
                elif "received" in desc_lower:
                    tx["received"] = True
                    tx["category"] = "Received Money"
                elif "pay bill" in desc_lower:
                    tx["paybill"] = True
                    tx["category"] = "PayBill"
                elif "merchant" in desc_lower:
                    tx["merchant"] = True
                    tx["category"] = "Merchant Payment"
                elif "agent" in desc_lower:
                    if "deposit" in desc_lower:
                        tx["agent_deposit"] = True
                        tx["category"] = "Agent Deposit"
                    elif "withdrawal" in desc_lower:
                        tx["agent_withdrawal"] = True
                        tx["category"] = "Agent Withdrawal"
                elif "transfer" in desc_lower:
                    tx["customer_transfer"] = True
                    tx["category"] = "Customer Transfer"
                elif "loan" in desc_lower and "repayment" in desc_lower:
                    tx["loan_repayment"] = True
                    tx["category"] = "Loan Repayment"

                # Extract phone number
                phone_match = re.search(r'2547\d{8}|07\d{8}', details)
                if phone_match:
                    tx["phone"] = phone_match.group()

                # Create unique ID
                tx_id = f"{receipt}_{date_str}_{amount}"
                if tx_id not in seen:
                    seen.add(tx_id)
                    transactions.append(tx)
                    logger.info(f"✅ Extracted transaction {len(transactions)}: {receipt} {date_str} {amount} {tx_type}")

            except Exception as e:
                logger.error(f"   ❌ Parse error for match {match_idx+1}: {e}")
                logger.error(f"   Match data: {match}")
                continue

        # Sort transactions
        transactions.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

        logger.info("=" * 80)
        logger.info(f"📊 EXTRACTION RESULTS:")
        logger.info(f"   Pattern used: {pattern_used if pattern_used else 'None'}")
        logger.info(f"   Total matches found: {len(all_matches)}")
        logger.info(f"   Unique transactions extracted: {len(transactions)}")
        logger.info("=" * 80)

        if transactions:
            logger.info(f"📊 First transaction: {transactions[0]}")
            logger.info(f"📊 Last transaction: {transactions[-1]}")
            logger.info(f"📊 Sample descriptions:")
            for i, tx in enumerate(transactions[:5]):
                logger.info(f"   {i+1}. {tx.get('description', '')[:80]}")
        else:
            logger.warning("⚠️ No transactions extracted!")

            # Show sample lines that might contain transaction data
            logger.info("🔍 Sample lines from text that might contain transactions:")
            count = 0
            for line in lines:
                if count >= 15:
                    break
                line_stripped = line.strip()
                if line_stripped and (
                    any(k in line_stripped for k in ["UF3", "Receipt", "Completed", "2026-", "funds", "payment"])
                ):
                    logger.info(f"   Line {count+1}: {repr(line_stripped[:150])}")
                    count += 1

            # Also check if the text contains any amount patterns
            amount_pattern = re.compile(r'[\d,]+\.\d{2}')
            amount_matches = amount_pattern.findall(text)
            logger.info(f"🔍 Found {len(amount_matches)} potential amount strings")
            if amount_matches:
                logger.info(f"   First 10 amounts: {amount_matches[:10]}")

        return transactions

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _df_to_transactions(
        self, df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Convert a DataFrame to the standard transaction list format"""
        logger.info(f"🔍 [PDF PARSER] _df_to_transactions() called with {len(df)} rows")

        date_col = desc_col = amount_col = None

        for col in df.columns:
            cl = col.lower()
            if "date" in cl and date_col is None:
                date_col = col
            if (
                any(k in cl for k in ["description", "desc", "narration", "details"])
                and desc_col is None
            ):
                desc_col = col
            if (
                any(k in cl for k in ["amount", "value", "credit", "debit"])
                and amount_col is None
            ):
                amount_col = col

        transactions: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            tx: Dict[str, Any] = {}
            if date_col:
                tx["date"] = str(row[date_col])
            if desc_col:
                tx["description"] = str(row[desc_col])
            if amount_col:
                try:
                    tx["amount"] = float(row[amount_col])
                except (ValueError, TypeError):
                    tx["amount"] = 0.0
            if "date" in tx and "description" in tx:
                tx["type"] = self._determine_transaction_type(tx.get("description", ""))
                transactions.append(tx)

        logger.info(f"📊 Extracted {len(transactions)} transactions from DataFrame")
        return transactions

    def _detect_statement_type(self, text: str) -> str:
        """Detect the type of statement from the text"""
        text_lower = text.lower()
        if "m-pesa" in text_lower or "mpesa" in text_lower:
            return "mpesa"
        for bank in self.bank_keywords:
            if bank in text_lower:
                return "bank"
        for indicator in ["bank statement", "account statement", "transaction history"]:
            if indicator in text_lower:
                return "bank"
        return "unknown"

    def _determine_transaction_type(self, description: str) -> str:
        """Determine if a transaction is income or expense based on description"""
        desc_lower = description.lower()
        income_kw = [
            "received", "sent to you", "credit", "deposit", "salary",
            "payment from", "income", "wages", "commission", "dividend",
            "refund", "reimbursement", "stipend", "grant", "bonus",
            "received from", "funds received", "paid in",
        ]
        expense_kw = [
            "sent", "paid", "debit", "withdraw", "transfer to",
            "payment to", "purchase", "buy", "subscription", "bill",
            "rent", "utility", "grocery", "food", "transport", "fuel",
            "airtime", "bet", "gamble", "loan", "repayment",
            "sent to", "pay bill", "buy goods", "withdrawn",
            "withdrawal", "charge", "fee",
        ]
        for kw in income_kw:
            if kw in desc_lower:
                return "income"
        for kw in expense_kw:
            if kw in desc_lower:
                return "expense"
        return "unknown"

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata from the statement text"""
        metadata: Dict[str, Any] = {
            "account_number": None,
            "customer_name": None,
            "start_date": None,
            "end_date": None,
            "bank_name": None,
            "statement_type": None,
            "opening_balance": None,
            "closing_balance": None,
            "phone_number": None,
            "statement_code": None,
        }

        for key, pattern in [
            ("account_number", self.patterns["account_number"]),
            ("customer_name", self.patterns["customer_name"]),
            ("bank_name", self.patterns["bank_name"]),
        ]:
            m = pattern.search(text)
            if m:
                metadata[key] = m.group(1).strip()

        date_m = self.patterns["date_range"].search(text)
        if date_m:
            metadata["start_date"] = date_m.group(1)
            metadata["end_date"] = date_m.group(2)

        if self.patterns["mpesa"].search(text):
            metadata["statement_type"] = "mpesa"
            phone_m = self.patterns["phone"].search(text)
            if phone_m:
                metadata["phone_number"] = phone_m.group()

        # Extract statement verification code
        code_match = re.search(r'GGXTGREW', text)
        if code_match:
            metadata["statement_code"] = code_match.group()

        opening_m = re.search(
            r"Opening\s+Balance[:\s]*([\d,]+\.\d{2})", text, re.IGNORECASE
        )
        if opening_m:
            metadata["opening_balance"] = float(
                opening_m.group(1).replace(",", "")
            )

        closing_m = re.search(
            r"Closing\s+Balance[:\s]*([\d,]+\.\d{2})", text, re.IGNORECASE
        )
        if closing_m:
            metadata["closing_balance"] = float(
                closing_m.group(1).replace(",", "")
            )

        return metadata

    def _calculate_summary(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate summary statistics from transactions"""
        if not transactions:
            return {
                "total_transactions": 0,
                "total_income": 0.0,
                "total_expenses": 0.0,
                "net_cash_flow": 0.0,
                "average_transaction": 0.0,
                "highest_transaction": 0.0,
                "lowest_transaction": 0.0,
                "unique_categories": [],
                "fuliza_count": 0,
                "betting_count": 0,
                "airtime_count": 0,
            }

        total_income = 0.0
        total_expenses = 0.0
        fuliza_count = betting_count = airtime_count = 0
        categories: set = set()
        amounts: List[float] = []

        for tx in transactions:
            amount = float(tx.get("amount", 0))
            if amount > 0:
                amounts.append(amount)
                if tx.get("type") == "income":
                    total_income += amount
                elif tx.get("type") == "expense":
                    total_expenses += amount
            if tx.get("fuliza"):
                fuliza_count += 1
            if tx.get("betting"):
                betting_count += 1
            if tx.get("airtime"):
                airtime_count += 1
            if tx.get("category"):
                categories.add(tx["category"])

        return {
            "total_transactions": len(transactions),
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_cash_flow": round(total_income - total_expenses, 2),
            "average_transaction": round(sum(amounts) / len(amounts), 2) if amounts else 0.0,
            "highest_transaction": max(amounts) if amounts else 0.0,
            "lowest_transaction": min(amounts) if amounts else 0.0,
            "unique_categories": list(categories),
            "fuliza_count": fuliza_count,
            "betting_count": betting_count,
            "airtime_count": airtime_count,
        }

    def _estimate_pages(self, text: str) -> int:
        """Estimate number of pages based on text length"""
        return max(1, len(text) // 3000)