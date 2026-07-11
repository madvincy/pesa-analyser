"""
M-PESA PDF to CSV/Excel Converter Endpoint

Converts M-PESA PDF statements to CSV/Excel format with:
- Single file conversion
- Bulk upload (multiple files) with drag-and-drop zone
- Multiple sheets in same CSV/Excel (one sheet per file)
- Password removal from PDFs
- Secure download (temporary, not saved to database)
- Conversion statistics
- Elasticsearch-powered search
- Export as CSV, Excel, or PDF
- Conversion history
- Analytics dashboard
- M-PESA payment tracking
- Pesa Analyzer branding with contact info
"""

import os
import io
import re
import csv
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, cast

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Depends,
    BackgroundTasks,
    Query,
    Form,
)
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.cache import redis_client
from app.models.conversion import Conversion
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.pdf_parser import PDFParser
from app.services.elasticsearch_service import ElasticsearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/converter", tags=["converter"])

# ─── Models ──────────────────────────────────────────────────────────────────


class ConversionRequest(BaseModel):
    """Conversion request model."""

    payment_reference: Optional[str] = None
    payment_amount: float = 0.0
    include_headers: bool = True
    date_format: str = "%Y-%m-%d"
    currency: str = "KES"
    format: str = "csv"  # csv or excel


class PasswordRemoveRequest(BaseModel):
    """Password removal request."""

    password: str


class SearchRequest(BaseModel):
    """Search request model."""

    query: str = ""
    filters: Dict[str, Any] = {}
    page: int = 1
    size: int = 20
    sort_by: str = "upload_date"
    sort_order: str = "desc"


class ConversionResponse(BaseModel):
    """Conversion response model."""

    conversion_id: str
    status: str
    file_count: int
    transaction_count: int
    total_amount: float
    payment_reference: Optional[str]
    payment_amount: float
    expires_at: datetime
    download_url: Optional[str] = None
    statistics: Dict[str, Any] = Field(default_factory=dict)


class BulkConversionResponse(BaseModel):
    """Bulk conversion response model."""

    conversion_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    total_transactions: int
    total_amount: float
    payment_reference: Optional[str]
    payment_amount: float
    expires_at: datetime
    download_url: Optional[str] = None
    file_results: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Constants ──────────────────────────────────────────────────────────────

# Temporary storage for conversions (in-memory with Redis backup)
CONVERSION_STORAGE: Dict[str, Dict[str, Any]] = {}
CONVERSION_EXPIRY_HOURS = 24

# M-PESA payment for conversion (KES)
CONVERSION_PRICE_PER_FILE = 50.00  # KES
CONVERSION_PRICE_BULK = 100.00  # KES for up to 10 files
CONVERSION_PRICE_BULK_EXTRA = 10.00  # KES per additional file after 10


# ─── Helper Functions ──────────────────────────────────────────────────────


def extract_transactions_from_pdf(
    content: bytes, password: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract transactions from PDF using the modular PDF parser.
    """
    try:
        parser = PDFParser(debug=False)
        parsed_data = parser.parse_statement(content, password)
        transactions: List[Dict[str, Any]] = parsed_data.get("transactions", [])

        if not transactions:
            logger.warning("No transactions extracted with PDFParser, trying fallback")
            transactions = extract_transactions_fallback(content)

        return transactions
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}", exc_info=True)
        return extract_transactions_fallback(content)


def extract_transactions_fallback(content: bytes) -> List[Dict[str, Any]]:
    """
    Fallback extraction using PyPDF2 and regex.
    """
    import PyPDF2  # type: ignore

    transactions: List[Dict[str, Any]] = []

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        lines = text.splitlines()
        receipt_pattern = re.compile(
            r"([A-Z0-9]{10})\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.+?)(?:\s+)(Completed|Failed|Pending)?\s*([-\d,]+\.\d{2})?\s*([-\d,]+\.\d{2})?"
        )

        for line in lines:
            match = receipt_pattern.search(line)
            if match:
                receipt, date, time, description = match.groups()[:4]
                amount = 0.0
                balance = 0.0

                amount_pattern = re.compile(r"([-+]?[\d,]+\.\d{2})")
                amounts = amount_pattern.findall(line)
                if len(amounts) >= 2:
                    try:
                        amount = float(amounts[0].replace(",", ""))
                        balance = float(amounts[1].replace(",", ""))
                    except ValueError:
                        pass

                transactions.append(
                    {
                        "receipt": receipt,
                        "date": date,
                        "time": time,
                        "description": description[:200],
                        "amount": abs(amount),
                        "balance": balance,
                        "type": (
                            "expense"
                            if amount < 0
                            else "income" if amount > 0 else "unknown"
                        ),
                        "direction": (
                            "out" if amount < 0 else "in" if amount > 0 else "unknown"
                        ),
                        "status": "Completed",
                    }
                )

        logger.info(f"Fallback extraction found {len(transactions)} transactions")
    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}")

    return transactions


def convert_to_csv(transactions: List[Dict[str, Any]], sheet_name: str = "") -> str:
    """Convert transactions to CSV format."""
    output = io.StringIO()

    # Add header with metadata
    if sheet_name:
        output.write(f"# Sheet: {sheet_name}\n")
    output.write(f"# Total Transactions: {len(transactions)}\n")
    output.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"# Generated by: Pesa Analyzer\n")
    output.write(f"# Contact: support@pesa-analyzer.com\n")
    output.write(f"# Phone: +254 700 000 000\n")
    output.write(
        f"# Total Income: {sum(t.get('amount', 0) for t in transactions if t.get('type') == 'income'):.2f}\n"
    )
    output.write(
        f"# Total Expenses: {sum(t.get('amount', 0) for t in transactions if t.get('type') == 'expense'):.2f}\n"
    )
    output.write(
        f"# Net Cash Flow: {sum(t.get('amount', 0) for t in transactions if t.get('type') == 'income') - sum(t.get('amount', 0) for t in transactions if t.get('type') == 'expense'):.2f}\n"
    )
    output.write("\n")

    headers = [
        "Receipt",
        "Date",
        "Time",
        "Description",
        "Amount",
        "Balance",
        "Type",
        "Direction",
        "Category",
        "Fee",
        "Status",
    ]
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for tx in transactions:
        row = {
            "Receipt": tx.get("receipt", ""),
            "Date": tx.get("date", ""),
            "Time": tx.get("time", ""),
            "Description": tx.get("description", ""),
            "Amount": tx.get("amount", 0),
            "Balance": tx.get("balance", 0),
            "Type": tx.get("type", ""),
            "Direction": tx.get("direction", ""),
            "Category": tx.get("category", "Other"),
            "Fee": tx.get("fee", 0),
            "Status": tx.get("status", "Completed"),
        }
        writer.writerow(row)

    return output.getvalue()


def convert_to_excel(
    transactions_by_file: Dict[str, List[Dict[str, Any]]],
) -> Optional[bytes]:
    """Convert transactions to Excel format with multiple sheets."""
    try:
        import pandas as pd

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:  # type: ignore
            # Add metadata sheet
            metadata = pd.DataFrame(
                {
                    "Generated By": ["Pesa Analyzer"],
                    "Generated At": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "Contact Email": ["support@pesa-analyzer.com"],
                    "Phone": ["+254 700 000 000"],
                    "Total Files": [len(transactions_by_file)],
                    "Total Transactions": [
                        sum(len(t) for t in transactions_by_file.values())
                    ],
                }
            )
            metadata.to_excel(writer, sheet_name="Metadata", index=False)

            # Add each file as a sheet
            for sheet_name, transactions in transactions_by_file.items():
                if transactions:
                    df = pd.DataFrame(transactions)
                    df = df.rename(
                        columns={
                            "receipt": "Receipt",
                            "date": "Date",
                            "time": "Time",
                            "description": "Description",
                            "amount": "Amount",
                            "balance": "Balance",
                            "type": "Type",
                            "direction": "Direction",
                            "category": "Category",
                            "fee": "Fee",
                            "status": "Status",
                        }
                    )
                    sheet_name_clean = sheet_name[:31]  # Excel limit
                    df.to_excel(writer, sheet_name=sheet_name_clean, index=False)

        return output.getvalue()
    except Exception as e:
        logger.error(f"Excel conversion failed: {e}")
        return None


def remove_password_from_pdf(content: bytes, password: str) -> Optional[bytes]:
    """Remove password from PDF."""
    try:
        import PyPDF2  # type: ignore

        reader = PyPDF2.PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            if reader.decrypt(password) != 0:
                writer = PyPDF2.PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                output = io.BytesIO()
                writer.write(output)
                return output.getvalue()
        return content
    except Exception as e:
        logger.error(f"Password removal failed: {e}")
        return None


def calculate_stats(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics from transactions."""
    if not transactions:
        return {
            "total_transactions": 0,
            "total_income": 0,
            "total_expenses": 0,
            "net_flow": 0,
        }

    total_income = sum(
        t.get("amount", 0) for t in transactions if t.get("type") == "income"
    )
    total_expenses = sum(
        t.get("amount", 0) for t in transactions if t.get("type") == "expense"
    )

    return {
        "total_transactions": len(transactions),
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_flow": round(total_income - total_expenses, 2),
    }


def get_conversion_price(file_count: int) -> float:
    """Calculate conversion price based on number of files."""
    if file_count <= 1:
        return CONVERSION_PRICE_PER_FILE
    elif file_count <= 10:
        return CONVERSION_PRICE_BULK
    else:
        return CONVERSION_PRICE_BULK + (file_count - 10) * CONVERSION_PRICE_BULK_EXTRA


def store_conversion_data(conversion_id: str, data: Dict[str, Any]) -> None:
    """Store conversion data in memory and Redis."""
    CONVERSION_STORAGE[conversion_id] = data
    try:
        redis_client.setex(
            f"conversion:{conversion_id}",
            CONVERSION_EXPIRY_HOURS * 3600,
            json.dumps(data, default=str),
        )
    except Exception as e:
        logger.warning(f"Redis storage failed: {e}")


def get_conversion_data(conversion_id: str) -> Optional[Dict[str, Any]]:
    """Get conversion data from memory or Redis."""
    if conversion_id in CONVERSION_STORAGE:
        return CONVERSION_STORAGE[conversion_id]

    try:
        data = redis_client.get(f"conversion:{conversion_id}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis retrieval failed: {e}")

    return None


def serialize_conversion(conversion: Conversion) -> Dict[str, Any]:
    """Serialize a Conversion model to JSON-serializable dict."""
    return {
        "id": str(conversion.id),  # UUID → string
        "file_name": conversion.file_name or "Unknown",
        "file_count": conversion.file_count or 0,
        "transaction_count": conversion.transaction_count or 0,
        "total_amount": (
            float(conversion.total_amount)
            if conversion.total_amount is not None
            else 0.0
        ),
        "payment_reference": conversion.payment_reference,
        "payment_amount": (
            float(conversion.payment_amount)
            if conversion.payment_amount is not None
            else 0.0
        ),
        "status": conversion.status or "unknown",
        "expires_at": (
            conversion.expires_at.isoformat() if conversion.expires_at else None
        ),
        "created_at": (
            conversion.created_at.isoformat() if conversion.created_at else None
        ),
        "updated_at": (
            conversion.updated_at.isoformat() if conversion.updated_at else None
        ),
    }


def normalize_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a transaction to ensure it has proper amount, direction, and type.
    Handles cases where amount is missing or direction is unknown.
    """
    # Get amount from various possible fields
    amount = tx.get("amount")
    if amount is None or amount == 0:
        # Try withdrawn (negative value indicates amount)
        withdrawn = tx.get("withdrawn")
        if withdrawn is not None and withdrawn != 0:
            amount = abs(withdrawn)
        else:
            # Try paid_in
            paid_in = tx.get("paid_in")
            if paid_in is not None and paid_in != 0:
                amount = paid_in
            else:
                # Try principal
                principal = tx.get("principal")
                if principal is not None and principal != 0:
                    amount = abs(principal)
                else:
                    # Try total_amount
                    total_amount = tx.get("total_amount")
                    if total_amount is not None and total_amount != 0:
                        amount = abs(total_amount)
                    else:
                        # Try actual_amount
                        actual_amount = tx.get("actual_amount")
                        if actual_amount is not None and actual_amount != 0:
                            amount = abs(actual_amount)
                        else:
                            amount = 0.0

    # Determine direction - improved detection
    direction = tx.get("direction")

    # If direction is missing or unknown, try to detect it
    if direction is None or direction == "unknown":
        # First, check if we have explicit direction from fields
        withdrawn = tx.get("withdrawn")
        paid_in = tx.get("paid_in")
        tx_type = tx.get("transaction_type", "")
        description = tx.get("description", "").lower()
        details = tx.get("details", "").lower()
        combined_text = f"{description} {details}"

        # Check the transaction type first (most reliable)
        if tx_type:
            tx_type_lower = tx_type.lower()
            if "received" in tx_type_lower or "funds_received" in tx_type_lower:
                direction = "in"
            elif "payment" in tx_type_lower or "sent" in tx_type_lower:
                direction = "out"
            elif "withdrawal" in tx_type_lower or "withdraw" in tx_type_lower:
                direction = "out"
            elif "deposit" in tx_type_lower:
                direction = "in"
            elif "transfer" in tx_type_lower:
                # Transfer direction depends on context
                if "customer transfer" in combined_text or "send" in combined_text:
                    direction = "out"
                elif "funds received" in combined_text or "received" in combined_text:
                    direction = "in"
                else:
                    # Check amount context
                    if amount > 0:
                        direction = "out"
                    else:
                        direction = "unknown"
            elif "airtime" in tx_type_lower:
                direction = "out"
            elif "paybill" in tx_type_lower:
                direction = "out"
            elif "merchant" in tx_type_lower:
                direction = "out"

        # If still unknown, check withdrawn/paid_in fields
        if direction is None or direction == "unknown":
            if withdrawn is not None and withdrawn > 0:
                direction = "out"
            elif paid_in is not None and paid_in > 0:
                direction = "in"

        # If still unknown, check description patterns
        if direction is None or direction == "unknown":
            if "received from" in combined_text:
                direction = "in"
            elif "funds received" in combined_text:
                direction = "in"
            elif "customer transfer" in combined_text and "to -" in combined_text:
                direction = "out"
            elif "send money" in combined_text:
                direction = "out"
            elif "merchant payment" in combined_text:
                direction = "out"
            elif "pay bill" in combined_text:
                direction = "out"
            elif "business payment" in combined_text:
                direction = "out"
            elif "buy goods" in combined_text:
                direction = "out"
            elif "airtime" in combined_text:
                direction = "out"
            elif "withdrawal" in combined_text:
                direction = "out"
            elif "deposit" in combined_text:
                direction = "in"
            elif "salary" in combined_text:
                direction = "in"

        # If still unknown, use amount sign as last resort
        if direction is None or direction == "unknown":
            if amount > 0:
                # Check if it's a reversal or credit
                if "reversal" in combined_text or "refund" in combined_text:
                    direction = "in"
                else:
                    # Default: positive amount is income, negative is expense
                    direction = "in"
            elif amount < 0:
                direction = "out"
            else:
                direction = "unknown"

    # Determine transaction type from description if not set
    transaction_type = tx.get("transaction_type", "")
    description = tx.get("description", "").lower()
    details = tx.get("details", "").lower()
    combined_text = f"{description} {details}"

    # If transaction type is unknown or empty, detect from description
    if (
        transaction_type is None
        or transaction_type == ""
        or transaction_type == "unknown"
    ):
        # Order matters - check more specific patterns first
        if "fuliza" in combined_text:
            if "repayment" in combined_text:
                transaction_type = "fuliza_repayment"
            elif "merchant payment" in combined_text:
                transaction_type = "merchant_payment_fuliza"
            elif "customer transfer" in combined_text or "transfer" in combined_text:
                transaction_type = "fuliza_transfer"
            elif "send money" in combined_text:
                transaction_type = "sent_money_fuliza"
            else:
                transaction_type = "fuliza"
        elif "funds received" in combined_text:
            transaction_type = "funds_received"
        elif "received from" in combined_text:
            transaction_type = "funds_received"
        elif "customer transfer" in combined_text:
            transaction_type = "customer_transfer"
        elif "send money" in combined_text:
            transaction_type = "sent_money"
        elif "merchant payment" in combined_text:
            transaction_type = "merchant_payment"
        elif "pay bill" in combined_text:
            transaction_type = "paybill"
        elif "business payment" in combined_text:
            transaction_type = "business_payment"
        elif "buy goods" in combined_text:
            transaction_type = "buy_goods"
        elif "airtime" in combined_text:
            transaction_type = "airtime"
        elif "withdrawal" in combined_text:
            transaction_type = "withdrawal"
        elif "deposit" in combined_text:
            transaction_type = "deposit"
        elif "salary" in combined_text:
            transaction_type = "salary"
        elif "m-pesa" in combined_text:
            transaction_type = "mpesa"
        elif "reversal" in combined_text or "refund" in combined_text:
            transaction_type = "reversal"
        else:
            # Try to determine from direction
            if direction == "in":
                transaction_type = "funds_received"
            elif direction == "out":
                transaction_type = "payment_sent"
            else:
                transaction_type = "other"

    # Determine category
    category = tx.get("category", "Other")
    if category is None or category == "" or category == "Other":
        if "fuliza" in transaction_type:
            category = "Fuliza"
        elif transaction_type == "funds_received":
            category = "Received Money"
        elif transaction_type in ["sent_money", "customer_transfer", "fuliza_transfer"]:
            category = "Send Money"
        elif transaction_type == "merchant_payment_fuliza":
            category = "Buy Goods (Fuliza)"
        elif transaction_type in ["merchant_payment", "buy_goods"]:
            category = "Buy Goods"
        elif transaction_type == "paybill":
            category = "PayBill"
        elif transaction_type == "business_payment":
            category = "Business Payment"
        elif transaction_type == "airtime":
            category = "Airtime"
        elif transaction_type == "withdrawal":
            category = "Withdrawal"
        elif transaction_type == "deposit":
            category = "Deposit"
        elif transaction_type == "salary":
            category = "Salary"
        elif transaction_type == "reversal":
            category = "Reversal"
        else:
            category = "Other"

    # Clean up merchant name
    merchant_name = tx.get("merchant_name", "")
    desc = tx.get("description", "")

    if not merchant_name or merchant_name == desc or len(merchant_name) > 100:
        # Try to extract merchant from description
        # Common patterns
        if " to - " in desc:
            parts = desc.split(" to - ")
            if len(parts) > 1:
                merchant_name = parts[1].strip()
        elif "Payment to " in desc:
            merchant_name = desc.replace("Payment to ", "").strip()
        elif " - " in desc:
            parts = desc.split(" - ")
            if len(parts) > 1:
                merchant_name = parts[-1].strip()
        elif "Customer Transfer" in desc:
            # Extract the recipient name
            import re

            match = re.search(r"to - \d+\s+(.+?)(?:$|,)", desc)
            if match:
                merchant_name = match.group(1).strip()
        elif "Funds received from" in desc:
            import re

            match = re.search(r"from - \d+\s+(.+?)(?:$|,)", desc)
            if match:
                merchant_name = match.group(1).strip()
        elif "Merchant Payment" in desc:
            # Extract merchant name after "to"
            import re

            match = re.search(r"to\s+(\d+)\s*-\s*(.+?)(?:$|,)", desc)
            if match:
                merchant_name = match.group(2).strip()
        # If still empty, use description truncated
        if not merchant_name or len(merchant_name) < 3:
            merchant_name = desc[:60]

    # Limit merchant name length
    if len(merchant_name) > 80:
        merchant_name = merchant_name[:77] + "..."

    # Create normalized transaction with all fields
    normalized_tx = {
        "receipt": tx.get("receipt", ""),
        "date": tx.get("date", ""),
        "time": tx.get("time", ""),
        "description": tx.get("description", ""),
        "amount": amount,
        "balance": tx.get("balance", 0),
        "direction": direction or "unknown",
        "category": category,
        "merchant_name": merchant_name,
        "fuliza_used": tx.get("fuliza_used", False),
        "fuliza_amount": tx.get("fuliza_amount", 0),
        "customer_name": tx.get("customer_name"),
        "status": tx.get("status", "Completed"),
        "transaction_type": transaction_type,
        # Original fields for reference
        "withdrawn": tx.get("withdrawn", 0),
        "paid_in": tx.get("paid_in", 0),
        "principal": tx.get("principal", 0),
        "total_amount": tx.get("total_amount", 0),
        "actual_amount": tx.get("actual_amount", 0),
        "details": tx.get("details", ""),
        "merchant_number": tx.get("merchant_number", ""),
        "paybill_number": tx.get("paybill_number", ""),
        "till_number": tx.get("till_number", ""),
        "fee": tx.get("fee", 0),
    }

    return normalized_tx


def calculate_transaction_stats(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate transaction statistics from a list of transactions.
    """
    total_in = 0.0
    total_out = 0.0

    for tx in transactions:
        amount = tx.get("amount", 0)
        direction = tx.get("direction", "unknown")

        if direction == "in":
            total_in += amount
        elif direction == "out":
            total_out += amount
        else:
            # If direction is unknown, try to determine from amount sign
            if amount > 0:
                # Check if it's an expense (withdrawn)
                if tx.get("withdrawn", 0) > 0:
                    total_out += amount
                elif tx.get("paid_in", 0) > 0:
                    total_in += amount
                else:
                    # Default: positive amounts are income, negative are expenses
                    total_in += amount
            else:
                total_out += abs(amount)

    net_flow = total_in - total_out

    return {
        "total_transactions": len(transactions),
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "net_flow": round(net_flow, 2),
    }


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/convert")
async def convert_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),  # type: ignore
    password: Optional[str] = Form(None),
    format: str = Form("csv"),
    include_headers: bool = Form(True),
    payment_reference: Optional[str] = Form(None),
    payment_amount: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Convert multiple PDF files to CSV or Excel.
    Supports password-protected files.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 files allowed")

        conversion_id = str(uuid.uuid4())
        transactions_by_file: Dict[str, List[Dict[str, Any]]] = {}
        file_results: List[Dict[str, Any]] = []
        total_transactions = 0
        total_income = 0.0
        total_expenses = 0.0
        failed_files = 0

        for file in files:
            try:
                content = await file.read()
                if not content:
                    file_results.append(
                        {
                            "file_name": file.filename,
                            "status": "failed",
                            "error": "Empty file",
                            "transaction_count": 0,
                        }
                    )
                    failed_files += 1
                    continue

                transactions = extract_transactions_from_pdf(content, password)

                if not transactions:
                    file_results.append(
                        {
                            "file_name": file.filename,
                            "status": "failed",
                            "error": "No transactions found",
                            "transaction_count": 0,
                        }
                    )
                    failed_files += 1
                    continue

                sheet_name = file.filename or f"Statement_{len(transactions_by_file)+1}"
                transactions_by_file[sheet_name] = transactions

                total_transactions += len(transactions)
                total_income += sum(
                    t.get("amount", 0)
                    for t in transactions
                    if t.get("type") == "income"
                )
                total_expenses += sum(
                    t.get("amount", 0)
                    for t in transactions
                    if t.get("type") == "expense"
                )

                file_results.append(
                    {
                        "file_name": file.filename,
                        "status": "completed",
                        "transaction_count": len(transactions),
                        "error": None,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to process {file.filename}: {e}")
                file_results.append(
                    {
                        "file_name": file.filename,
                        "status": "failed",
                        "error": str(e),
                        "transaction_count": 0,
                    }
                )
                failed_files += 1

        if not transactions_by_file:
            raise HTTPException(
                status_code=400,
                detail="No transactions could be extracted from any of the files.",
            )

        # Convert to requested format
        if format.lower() == "excel":
            output_content = convert_to_excel(transactions_by_file)
            if output_content:
                media_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                file_extension = "xlsx"
            else:
                # Fallback to CSV if Excel fails
                csv_parts = []
                for sheet_name, transactions in transactions_by_file.items():
                    csv_parts.append(convert_to_csv(transactions, sheet_name))
                output_content = "\n\n".join(csv_parts).encode("utf-8")
                media_type = "text/csv"
                file_extension = "csv"
        else:
            csv_parts = []
            for sheet_name, transactions in transactions_by_file.items():
                csv_parts.append(convert_to_csv(transactions, sheet_name))
            output_content = "\n\n".join(csv_parts).encode("utf-8")
            media_type = "text/csv"
            file_extension = "csv"

        price = payment_amount or get_conversion_price(len(files))

        conversion_data = {
            "id": conversion_id,
            "user_id": str(current_user.id),
            "file_count": len(files),
            "total_transactions": total_transactions,
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_flow": round(total_income - total_expenses, 2),
            "file_results": file_results,
            "failed_files": failed_files,
            "format": format,
            "output_content": output_content,
            "media_type": media_type,
            "file_extension": file_extension,
            "payment_reference": payment_reference,
            "payment_amount": price,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        }

        store_conversion_data(conversion_id, conversion_data)

        conversion = Conversion(
            id=conversion_id,
            user_id=current_user.id,
            file_name=f"bulk_conversion_{len(files)}_files",
            file_count=len(files),
            transaction_count=total_transactions,
            total_amount=round(total_income - total_expenses, 2),
            payment_reference=payment_reference,
            payment_amount=price,
            status="completed",
            expires_at=datetime.now() + timedelta(hours=24),
        )
        db.add(conversion)
        db.commit()

        return JSONResponse(
            {
                "conversion_id": conversion_id,
                "status": "completed" if failed_files == 0 else "partial",
                "total_files": len(files),
                "processed_files": len(transactions_by_file),
                "failed_files": failed_files,
                "total_transactions": total_transactions,
                "total_income": round(total_income, 2),
                "total_expenses": round(total_expenses, 2),
                "net_flow": round(total_income - total_expenses, 2),
                "format": format,
                "payment_reference": payment_reference,
                "payment_amount": price,
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
                "download_url": f"/api/converter/download/{conversion_id}",
                "file_results": file_results,
                "statistics": {
                    "total_transactions": total_transactions,
                    "total_income": round(total_income, 2),
                    "total_expenses": round(total_expenses, 2),
                    "net_flow": round(total_income - total_expenses, 2),
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post("/remove-password")
async def remove_password(
    file: UploadFile = File(...),  # type: ignore
    password: str = Form(...),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Remove password from a PDF file and return the unlocked version.
    """
    try:
        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        unlocked_content = remove_password_from_pdf(content, password)

        if unlocked_content is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to remove password. Incorrect password or invalid PDF.",
            )

        filename = file.filename
        if filename and filename.lower().endswith(".pdf"):
            filename = filename[:-4] + "_unlocked.pdf"
        else:
            filename = "unlocked.pdf"

        return StreamingResponse(
            iter([unlocked_content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Unlocked": "true",
                "X-Original-File": file.filename or "unknown",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password removal failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to remove password: {str(e)}"
        )


@router.get("/download/{conversion_id}")
async def download_conversion(
    conversion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Download converted file.
    """
    data = get_conversion_data(conversion_id)

    if not data:
        conversion = (
            db.query(Conversion)
            .filter(
                Conversion.id == conversion_id, Conversion.user_id == current_user.id
            )
            .first()
        )

        if conversion:
            if (
                conversion.expires_at is not None
                and conversion.expires_at < datetime.now()
            ):
                raise HTTPException(status_code=410, detail="Conversion has expired")
            else:
                raise HTTPException(status_code=404, detail="Conversion data not found")
        else:
            raise HTTPException(status_code=404, detail="Conversion not found")

    if data.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    output_content = data.get("output_content")
    if not output_content:
        raise HTTPException(status_code=404, detail="Content not found")

    media_type = data.get("media_type", "text/csv")
    file_extension = data.get("file_extension", "csv")
    file_count = data.get("file_count", 1)

    if file_count == 1:
        filename = f"mpesa_statement_converted.{file_extension}"
    else:
        filename = f"mpesa_bulk_conversion_{file_count}_files.{file_extension}"

    return StreamingResponse(
        iter(
            [output_content]
            if isinstance(output_content, bytes)
            else [output_content.encode("utf-8")]
        ),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Conversion-ID": conversion_id,
            "X-Transaction-Count": str(data.get("total_transactions", 0)),
            "X-Total-Amount": str(
                data.get("total_income", 0) - data.get("total_expenses", 0)
            ),
            "X-Generated-By": "Pesa Analyzer",
            "X-Contact": "support@pesa-analyzer.com",
        },
    )


@router.post("/search")
async def search_transactions(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Search transactions using Elasticsearch.
    Returns table with rows and columns.
    Searches within nested transaction objects.
    """
    try:
        es = ElasticsearchService()
        await es.connect()

        # Check if connected
        if not es.is_connected():
            logger.warning("Elasticsearch is not connected, returning empty results")
            return JSONResponse(
                {
                    "error": "Search service unavailable",
                    "message": "Elasticsearch is not available",
                    "results": [],
                    "total": 0,
                    "page": request.page,
                    "size": request.size,
                    "total_pages": 0,
                    "aggregations": {
                        "total_income": 0,
                        "total_expenses": 0,
                        "net_flow": 0,
                        "by_month": [],
                        "by_category": [],
                        "by_merchant": [],
                    },
                },
                status_code=503,
            )

        # Build the query - search within nested transactions
        must_conditions: List[Dict[str, Any]] = [
            {"term": {"user_id": str(current_user.id)}}
        ]

        # If query is provided, search within nested transactions
        if request.query:
            # Build nested query to search within transactions
            nested_query = {
                "nested": {
                    "path": "transactions",
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "match": {
                                        "transactions.description": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                            "operator": "or",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "transactions.merchant_name": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "transactions.category": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "transactions.customer_name": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "transactions.receipt": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "transactions.details": {
                                            "query": request.query,
                                            "fuzziness": "AUTO",
                                        }
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    "inner_hits": {
                        "size": 100,  # Return matching transactions
                        "_source": [
                            "transactions.receipt",
                            "transactions.date",
                            "transactions.time",
                            "transactions.description",
                            "transactions.amount",
                            "transactions.balance",
                            "transactions.direction",
                            "transactions.category",
                            "transactions.merchant_name",
                            "transactions.fuliza_used",
                            "transactions.fuliza_amount",
                            "transactions.customer_name",
                            "transactions.status",
                            "transactions.transaction_type",
                            "transactions.withdrawn",
                            "transactions.paid_in",
                            "transactions.principal",
                            "transactions.total_amount",
                            "transactions.actual_amount",
                            "transactions.details",
                            "transactions.merchant_number",
                            "transactions.paybill_number",
                            "transactions.till_number",
                            "transactions.fee",
                        ],
                    },
                }
            }

            must_conditions.append(nested_query)

        # Apply filters
        filters = request.filters or {}
        if filters.get("category"):
            must_conditions.append(
                {
                    "nested": {
                        "path": "transactions",
                        "query": {
                            "term": {"transactions.category": filters["category"]}
                        },
                    }
                }
            )
        if filters.get("merchant"):
            must_conditions.append(
                {
                    "nested": {
                        "path": "transactions",
                        "query": {
                            "term": {
                                "transactions.merchant_name.keyword": filters[
                                    "merchant"
                                ]
                            }
                        },
                    }
                }
            )
        if filters.get("date_from") and filters.get("date_to"):
            must_conditions.append(
                {
                    "nested": {
                        "path": "transactions",
                        "query": {
                            "range": {
                                "transactions.date": {
                                    "gte": filters["date_from"],
                                    "lte": filters["date_to"],
                                }
                            }
                        },
                    }
                }
            )
        if filters.get("min_amount") or filters.get("max_amount"):
            amount_range: Dict[str, Any] = {}
            if filters.get("min_amount"):
                amount_range["gte"] = filters["min_amount"]
            if filters.get("max_amount"):
                amount_range["lte"] = filters["max_amount"]
            must_conditions.append(
                {
                    "nested": {
                        "path": "transactions",
                        "query": {"range": {"transactions.amount": amount_range}},
                    }
                }
            )

        # Handle sort field mapping
        sort_field = request.sort_by
        if sort_field == "upload_date":
            sort_field = "upload_date"
        elif sort_field == "transaction_count":
            sort_field = "transaction_count"
        elif sort_field == "total_income":
            sort_field = "total_income"
        elif sort_field == "total_expenses":
            sort_field = "total_expenses"
        elif sort_field == "file_name":
            sort_field = "file_name.keyword"
        else:
            sort_field = "upload_date"

        # Build the query body
        query_body: Dict[str, Any] = {
            "query": (
                {"bool": {"must": must_conditions}}
                if must_conditions
                else {"match_all": {}}
            ),
            "from": (request.page - 1) * request.size,
            "size": request.size,
            "sort": [{sort_field: {"order": request.sort_order}}],
            "aggs": {
                "total_income": {"sum": {"field": "total_income"}},
                "total_expenses": {"sum": {"field": "total_expenses"}},
                "by_month": {
                    "date_histogram": {
                        "field": "upload_date",
                        "calendar_interval": "month",
                        "format": "yyyy-MM-dd",
                    }
                },
                "by_category": {
                    "nested": {"path": "transactions"},
                    "aggs": {
                        "categories": {
                            "terms": {"field": "transactions.category", "size": 20}
                        }
                    },
                },
                "by_merchant": {
                    "nested": {"path": "transactions"},
                    "aggs": {
                        "merchants": {
                            "terms": {
                                "field": "transactions.merchant_name.keyword",
                                "size": 20,
                            }
                        }
                    },
                },
            },
        }

        logger.info(f"🔍 ES Query: {json.dumps(query_body, indent=2)}")

        response = await es.client.search(index=es.index_name, body=query_body)  # type: ignore

        hits = response.get("hits", {})
        aggs = response.get("aggregations", {})

        results: List[Dict[str, Any]] = []
        all_matching_transactions: List[Dict[str, Any]] = []

        for hit in hits.get("hits", []):
            source = hit.get("_source", {})

            # Get matching transactions from inner_hits
            matching_transactions: List[Dict[str, Any]] = []
            inner_hits = hit.get("inner_hits", {})
            if "transactions" in inner_hits:
                for inner_hit in inner_hits["transactions"]["hits"]["hits"]:
                    tx_source = inner_hit["_source"]
                    normalized_tx = normalize_transaction(tx_source)
                    matching_transactions.append(normalized_tx)
                    all_matching_transactions.append(normalized_tx)

            results.append(
                {
                    "id": hit.get("_id"),
                    "file_name": source.get("file_name", "Unknown"),
                    "file_type": source.get("file_type", "pdf"),
                    "transaction_count": (
                        len(matching_transactions)
                        if matching_transactions
                        else source.get("transaction_count", 0)
                    ),
                    "total_income": source.get("total_income", 0),
                    "total_expenses": source.get("total_expenses", 0),
                    "net_flow": source.get("total_income", 0)
                    - source.get("total_expenses", 0),
                    "upload_date": source.get("upload_date"),
                    "categories": source.get("categories", []),
                    "merchants": source.get("merchants", []),
                    "score": hit.get("_score", 0),
                    "matching_transactions": matching_transactions,  # Only matching transactions
                }
            )

        # Calculate transaction stats from all matching transactions
        transaction_stats = calculate_transaction_stats(all_matching_transactions)

        # Get aggregations from nested aggs
        categories: List[Dict[str, Any]] = []
        if "by_category" in aggs and "categories" in aggs["by_category"]:
            categories = [
                {"name": b["key"], "count": b["doc_count"]}
                for b in aggs["by_category"]["categories"]["buckets"]
            ]

        merchants: List[Dict[str, Any]] = []
        if "by_merchant" in aggs and "merchants" in aggs["by_merchant"]:
            merchants = [
                {"name": b["key"], "count": b["doc_count"]}
                for b in aggs["by_merchant"]["merchants"]["buckets"]
            ]

        total_income = aggs.get("total_income", {}).get("value", 0)
        total_expenses = aggs.get("total_expenses", {}).get("value", 0)

        # Ensure we return proper values even if aggregations are empty
        by_month: List[Dict[str, Any]] = []
        for b in aggs.get("by_month", {}).get("buckets", []):
            month_key = b.get("key_as_string") or b.get("key")
            if month_key:
                by_month.append({"month": month_key, "count": b.get("doc_count", 0)})

        total_hits = hits.get("total", {})
        if isinstance(total_hits, dict):
            total_value = total_hits.get("value", 0)
        else:
            total_value = total_hits or 0

        logger.info(f"✅ Found {total_value} results")

        return JSONResponse(
            {
                "results": results,
                "total": total_value,
                "page": request.page,
                "size": request.size,
                "total_pages": (
                    (total_value + request.size - 1) // request.size
                    if total_value > 0
                    else 0
                ),
                "aggregations": {
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "net_flow": total_income - total_expenses,
                    "by_month": by_month,
                    "by_category": categories,
                    "by_merchant": merchants,
                },
                "transaction_stats": transaction_stats,
            }
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return JSONResponse(
            {
                "error": "Search failed",
                "message": str(e),
                "results": [],
                "total": 0,
                "page": request.page,
                "size": request.size,
                "total_pages": 0,
                "aggregations": {
                    "total_income": 0,
                    "total_expenses": 0,
                    "net_flow": 0,
                    "by_month": [],
                    "by_category": [],
                    "by_merchant": [],
                },
                "transaction_stats": {
                    "total_transactions": 0,
                    "total_in": 0,
                    "total_out": 0,
                    "net_flow": 0,
                },
            },
            status_code=500,
        )


@router.get("/history")
async def get_conversion_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
) -> JSONResponse:
    """
    Get conversion history for the current user.
    """
    try:
        conversions = (
            db.query(Conversion)
            .filter(Conversion.user_id == current_user.id)
            .order_by(Conversion.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        total = (
            db.query(Conversion).filter(Conversion.user_id == current_user.id).count()
        )

        # Convert all conversions to JSON-serializable format
        conversion_list = [serialize_conversion(c) for c in conversions]

        return JSONResponse(
            {
                "total": total,
                "skip": skip,
                "limit": limit,
                "conversions": conversion_list,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching conversion history: {e}", exc_info=True)
        return JSONResponse(
            {
                "total": 0,
                "skip": skip,
                "limit": limit,
                "conversions": [],
                "error": str(e),
            },
            status_code=500,
        )


@router.get("/analytics/{conversion_id}")
async def get_conversion_analytics(
    conversion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Get analytics for a specific conversion.
    """
    try:
        conversion = (
            db.query(Conversion)
            .filter(
                Conversion.id == conversion_id, Conversion.user_id == current_user.id
            )
            .first()
        )

        if not conversion:
            raise HTTPException(status_code=404, detail="Conversion not found")

        # Get detailed data from storage
        data = get_conversion_data(conversion_id)
        transactions = data.get("transactions", []) if data else []
        transactions_by_file = data.get("transactions_by_file", {}) if data else {}

        stats = calculate_stats(transactions) if transactions else {}

        # Get all transactions from all files
        all_transactions: List[Dict[str, Any]] = []
        for sheet, txs in transactions_by_file.items():
            all_transactions.extend(txs)

        return JSONResponse(
            {
                "conversion_id": str(conversion.id),  # Convert UUID to string
                "file_name": conversion.file_name,
                "file_count": conversion.file_count,
                "transaction_count": conversion.transaction_count,
                "total_amount": (
                    float(conversion.total_amount) if conversion.total_amount else 0.0
                ),
                "payment_reference": conversion.payment_reference,
                "payment_amount": (
                    float(conversion.payment_amount)
                    if conversion.payment_amount
                    else 0.0
                ),
                "status": conversion.status,
                "created_at": (
                    conversion.created_at.isoformat() if conversion.created_at else None
                ),
                "expires_at": (
                    conversion.expires_at.isoformat() if conversion.expires_at else None
                ),
                "statistics": stats,
                "transactions": all_transactions[:1000],  # Limit for performance
                "files": list(transactions_by_file.keys()),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversion analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch analytics: {str(e)}"
        )


@router.get("/stats")
async def get_conversion_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Get conversion statistics.
    """
    from sqlalchemy import func

    try:
        total_conversions = (
            db.query(Conversion).filter(Conversion.user_id == current_user.id).count()
        )

        total_transactions_result = (
            db.query(func.sum(Conversion.transaction_count))
            .filter(Conversion.user_id == current_user.id)
            .scalar()
        )
        total_transactions = (
            int(total_transactions_result) if total_transactions_result else 0
        )

        total_amount_result = (
            db.query(func.sum(Conversion.total_amount))
            .filter(Conversion.user_id == current_user.id)
            .scalar()
        )
        total_amount = float(total_amount_result) if total_amount_result else 0.0

        this_month = datetime.now().replace(day=1)
        monthly_conversions = (
            db.query(Conversion)
            .filter(
                Conversion.user_id == current_user.id,
                Conversion.created_at >= this_month,
            )
            .count()
        )

        last_30_days = (
            db.query(Conversion)
            .filter(
                Conversion.user_id == current_user.id,
                Conversion.created_at >= (datetime.now() - timedelta(days=30)),
            )
            .count()
        )

        return JSONResponse(
            {
                "total_conversions": total_conversions,
                "total_transactions": total_transactions,
                "total_amount": total_amount,
                "monthly_conversions": monthly_conversions,
                "last_30_days": last_30_days,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching conversion stats: {e}", exc_info=True)
        return JSONResponse(
            {
                "total_conversions": 0,
                "total_transactions": 0,
                "total_amount": 0.0,
                "monthly_conversions": 0,
                "last_30_days": 0,
                "error": str(e),
            },
            status_code=500,
        )


@router.get("/pricing")
async def get_conversion_pricing(
    file_count: int = Query(1, ge=1, le=50),
) -> JSONResponse:
    """
    Get conversion pricing.
    """
    price = get_conversion_price(file_count)

    return JSONResponse(
        {
            "file_count": file_count,
            "price": price,
            "price_per_file": round(price / file_count, 2),
            "currency": "KES",
            "base_price": CONVERSION_PRICE_PER_FILE,
            "bulk_price": CONVERSION_PRICE_BULK,
            "bulk_threshold": 10,
            "bulk_extra_price": CONVERSION_PRICE_BULK_EXTRA,
        }
    )


@router.get("/check/{conversion_id}")
async def check_conversion_exists(
    conversion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Check if a conversion exists and is accessible.
    """
    try:
        conversion = (
            db.query(Conversion)
            .filter(
                Conversion.id == conversion_id, Conversion.user_id == current_user.id
            )
            .first()
        )

        if not conversion:
            return JSONResponse({"exists": False})

        return JSONResponse(
            {
                "exists": True,
                "status": conversion.status,
                "expires_at": (
                    conversion.expires_at.isoformat() if conversion.expires_at else None
                ),
            }
        )

    except Exception as e:
        logger.error(f"Error checking conversion: {e}", exc_info=True)
        return JSONResponse(
            {"exists": False, "error": str(e)},
            status_code=500,
        )
