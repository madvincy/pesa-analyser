"""
M-PESA PDF to CSV Converter Endpoint

Converts M-PESA PDF statements to CSV format with:
- Single file conversion
- Bulk upload (multiple files)
- Multiple sheets in same CSV (one sheet per file)
- Secure download (temporary, not saved to database)
- Conversion statistics
- M-PESA payment tracking
"""

import os
import io
import re
import csv
import uuid
import logging
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

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
from app.models.conversion import Conversion, ConversionStatus
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.pdf_parser import PDFParser

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
        parser = PDFParser(debug=True)

        # Parse the PDF
        parsed_data = parser.parse_statement(content, password)

        # Get transactions
        transactions = parsed_data.get("transactions", [])

        # If no transactions found, try alternative extraction
        if not transactions:
            logger.warning("No transactions extracted with PDFParser, trying fallback")
            transactions = extract_transactions_fallback(content)

        return transactions
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}", exc_info=True)
        # Try fallback
        return extract_transactions_fallback(content)


def extract_transactions_fallback(content: bytes) -> List[Dict[str, Any]]:
    """
    Fallback extraction using PyPDF2 and regex.
    """
    import PyPDF2
    import io

    transactions = []

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        # Parse text for M-PESA transactions
        lines = text.splitlines()

        # M-PESA receipt pattern: [A-Z0-9]{10} YYYY-MM-DD HH:MM:SS Description
        receipt_pattern = re.compile(
            r"([A-Z0-9]{10})\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.+?)(?:\s+)(Completed|Failed|Pending)?\s*([-\d,]+\.\d{2})?\s*([-\d,]+\.\d{2})?"
        )

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            match = receipt_pattern.search(line)
            if match:
                receipt, date, time, description = match.groups()[:4]

                # Look for amount in the same line or next lines
                amount = 0.0
                balance = 0.0

                # Try to find amount and balance
                amount_pattern = re.compile(r"([-+]?[\d,]+\.\d{2})")
                amounts = amount_pattern.findall(line)
                if len(amounts) >= 2:
                    try:
                        amount = float(amounts[0].replace(",", ""))
                        balance = float(amounts[1].replace(",", ""))
                    except ValueError:
                        pass

                # Determine type
                tx_type = (
                    "expense" if amount < 0 else "income" if amount > 0 else "unknown"
                )
                direction = "out" if amount < 0 else "in" if amount > 0 else "unknown"

                transactions.append(
                    {
                        "receipt": receipt,
                        "date": date,
                        "time": time,
                        "description": description[:200],
                        "amount": abs(amount),
                        "balance": balance,
                        "type": tx_type,
                        "direction": direction,
                        "status": "Completed",
                    }
                )

                i += 1
                continue

            i += 1

        logger.info(f"Fallback extraction found {len(transactions)} transactions")

    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}", exc_info=True)

    return transactions


def convert_transactions_to_csv(
    transactions: List[Dict[str, Any]], sheet_name: str = "Sheet1"
) -> str:
    """
    Convert transactions to CSV format with sheet name as comment.
    """
    if not transactions:
        return f"# {sheet_name}\nNo transactions found\n"

    output = io.StringIO()

    # Add sheet name as comment
    output.write(f"# Sheet: {sheet_name}\n")
    output.write(f"# Total Transactions: {len(transactions)}\n")

    # Determine headers
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
        # Ensure all fields exist
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


def convert_bulk_to_csv(transactions_by_file: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Convert multiple files to CSV with sheets separated.
    """
    output = io.StringIO()

    for sheet_name, transactions in transactions_by_file.items():
        # Add sheet header
        output.write(f"\n\n# === Sheet: {sheet_name} ===\n")
        output.write(f"# Transactions: {len(transactions)}\n")

        if transactions:
            # Write headers
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
        else:
            output.write("No transactions found\n")

    return output.getvalue()


def calculate_stats(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics from transactions."""
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
        "date_range": (
            {
                "start": min((t.get("date", "") for t in transactions), default=""),
                "end": max((t.get("date", "") for t in transactions), default=""),
            }
            if transactions
            else {}
        ),
    }


def store_conversion_data(conversion_id: str, data: Dict[str, Any]) -> None:
    """Store conversion data in memory and Redis."""
    # Store in memory
    CONVERSION_STORAGE[conversion_id] = data

    # Store in Redis for persistence across restarts
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
    # Check memory first
    if conversion_id in CONVERSION_STORAGE:
        return CONVERSION_STORAGE[conversion_id]

    # Check Redis
    try:
        data = redis_client.get(f"conversion:{conversion_id}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis retrieval failed: {e}")

    return None


def get_conversion_price(file_count: int) -> float:
    """Calculate conversion price based on number of files."""
    if file_count <= 1:
        return CONVERSION_PRICE_PER_FILE
    elif file_count <= 10:
        return CONVERSION_PRICE_BULK
    else:
        return CONVERSION_PRICE_BULK + (file_count - 10) * CONVERSION_PRICE_BULK_EXTRA


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/convert", response_model=ConversionResponse)
async def convert_pdf_to_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    include_headers: bool = Form(True),
    date_format: str = Form("%Y-%m-%d"),
    payment_reference: Optional[str] = Form(None),
    payment_amount: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Convert a single M-PESA PDF to CSV.

    - **file**: PDF file to convert
    - **password**: Optional password for encrypted PDF
    - **include_headers**: Include column headers in CSV
    - **date_format**: Date format for output
    - **payment_reference**: M-PESA payment reference
    - **payment_amount**: Amount paid for conversion
    """
    try:
        # Read file
        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")

        # Extract transactions
        transactions = extract_transactions_from_pdf(content, password)

        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions could be extracted from the PDF. Please ensure it's a valid M-PESA statement.",
            )

        # Generate conversion ID
        conversion_id = str(uuid.uuid4())

        # Convert to CSV
        csv_content = convert_transactions_to_csv(
            transactions, sheet_name=file.filename or "Statement"
        )

        # Calculate stats
        stats = calculate_stats(transactions)

        # Store conversion data
        data = {
            "id": conversion_id,
            "user_id": str(current_user.id),
            "file_name": file.filename,
            "csv_content": csv_content,
            "transactions": transactions,
            "stats": stats,
            "payment_reference": payment_reference,
            "payment_amount": payment_amount,
            "created_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS)
            ).isoformat(),
            "single_file": True,
            "file_count": 1,
        }
        store_conversion_data(conversion_id, data)

        # Create conversion record in DB
        conversion = Conversion(
            id=conversion_id,
            user_id=current_user.id,
            file_name=file.filename,
            file_count=1,
            transaction_count=len(transactions),
            total_amount=stats.get("net_flow", 0),
            payment_reference=payment_reference,
            payment_amount=payment_amount or get_conversion_price(1),
            status="completed",
            expires_at=datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS),
            created_at=datetime.now(),
        )
        db.add(conversion)
        db.commit()

        # Return response
        return JSONResponse(
            {
                "conversion_id": conversion_id,
                "status": "completed",
                "file_count": 1,
                "transaction_count": len(transactions),
                "total_amount": stats.get("net_flow", 0),
                "payment_reference": payment_reference,
                "payment_amount": payment_amount or get_conversion_price(1),
                "expires_at": (
                    datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS)
                ).isoformat(),
                "download_url": f"/api/converter/download/{conversion_id}",
                "statistics": stats,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post("/convert/bulk", response_model=BulkConversionResponse)
async def convert_bulk_pdf_to_csv(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    password: Optional[str] = Form(None),
    include_headers: bool = Form(True),
    date_format: str = Form("%Y-%m-%d"),
    payment_reference: Optional[str] = Form(None),
    payment_amount: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Convert multiple M-PESA PDFs to a single CSV with multiple sheets.

    - **files**: List of PDF files to convert
    - **password**: Optional password for encrypted PDFs (same for all)
    - **include_headers**: Include column headers in CSV
    - **date_format**: Date format for output
    - **payment_reference**: M-PESA payment reference
    - **payment_amount**: Amount paid for conversion
    """
    try:
        if not files or len(files) == 0:
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

        # Process each file
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

                # Extract transactions
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

                # Store transactions by file
                sheet_name = file.filename or f"Statement_{len(transactions_by_file)+1}"
                transactions_by_file[sheet_name] = transactions

                # Calculate totals
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

        # Convert to CSV
        csv_content = convert_bulk_to_csv(transactions_by_file)

        # Calculate price
        price = payment_amount or get_conversion_price(len(files))

        # Store conversion data
        data = {
            "id": conversion_id,
            "user_id": str(current_user.id),
            "csv_content": csv_content,
            "transactions_by_file": transactions_by_file,
            "stats": {
                "total_transactions": total_transactions,
                "total_income": round(total_income, 2),
                "total_expenses": round(total_expenses, 2),
                "net_flow": round(total_income - total_expenses, 2),
                "file_count": len(files),
                "failed_files": failed_files,
            },
            "payment_reference": payment_reference,
            "payment_amount": price,
            "created_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS)
            ).isoformat(),
            "bulk": True,
            "file_count": len(files),
            "file_results": file_results,
        }
        store_conversion_data(conversion_id, data)

        # Create conversion record in DB
        conversion = Conversion(
            id=conversion_id,
            user_id=current_user.id,
            file_name="bulk_conversion",
            file_count=len(files),
            transaction_count=total_transactions,
            total_amount=round(total_income - total_expenses, 2),
            payment_reference=payment_reference,
            payment_amount=price,
            status="completed",
            expires_at=datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS),
            created_at=datetime.now(),
        )
        db.add(conversion)
        db.commit()

        # Build response
        return JSONResponse(
            {
                "conversion_id": conversion_id,
                "status": "completed" if failed_files == 0 else "partial",
                "total_files": len(files),
                "processed_files": len(transactions_by_file),
                "failed_files": failed_files,
                "total_transactions": total_transactions,
                "total_amount": round(total_income - total_expenses, 2),
                "payment_reference": payment_reference,
                "payment_amount": price,
                "expires_at": (
                    datetime.now() + timedelta(hours=CONVERSION_EXPIRY_HOURS)
                ).isoformat(),
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
        raise HTTPException(status_code=500, detail=f"Bulk conversion failed: {str(e)}")


@router.get("/download/{conversion_id}")
async def download_conversion(
    conversion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Download a converted CSV file.

    - **conversion_id**: ID of the conversion to download
    """
    # Get conversion data
    data = get_conversion_data(conversion_id)

    if not data:
        # Check if conversion exists in DB but expired
        conversion = (
            db.query(Conversion)
            .filter(
                Conversion.id == conversion_id, Conversion.user_id == current_user.id
            )
            .first()
        )

        if conversion:
            if conversion.expires_at < datetime.now():
                raise HTTPException(status_code=410, detail="Conversion has expired")
            else:
                # Data should be available but isn't - try to recover from Redis
                raise HTTPException(status_code=404, detail="Conversion data not found")
        else:
            raise HTTPException(status_code=404, detail="Conversion not found")

    # Verify user owns this conversion
    if data.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Get CSV content
    csv_content = data.get("csv_content")
    if not csv_content:
        raise HTTPException(status_code=404, detail="CSV content not found")

    # Determine filename
    is_bulk = data.get("bulk", False)
    if is_bulk:
        filename = f"mpesa_bulk_statement_{datetime.now().strftime('%Y%m%d')}.csv"
    else:
        file_name = data.get("file_name", "statement")
        name_without_ext = os.path.splitext(file_name)[0]
        filename = f"{name_without_ext}_converted.csv"

    # Create response
    response = StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Conversion-ID": conversion_id,
            "X-Transaction-Count": str(
                data.get("stats", {}).get("total_transactions", 0)
            ),
            "X-Total-Amount": str(data.get("stats", {}).get("total_amount", 0)),
        },
    )

    return response


@router.get("/status/{conversion_id}")
async def get_conversion_status(
    conversion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Get the status of a conversion.
    """
    # Check memory/Redis first
    data = get_conversion_data(conversion_id)

    if data:
        return JSONResponse(
            {
                "conversion_id": conversion_id,
                "status": "completed",
                "file_count": data.get("file_count", 0),
                "transaction_count": data.get("stats", {}).get("total_transactions", 0),
                "expires_at": data.get("expires_at"),
                "download_url": f"/api/converter/download/{conversion_id}",
            }
        )

    # Check DB
    conversion = (
        db.query(Conversion)
        .filter(Conversion.id == conversion_id, Conversion.user_id == current_user.id)
        .first()
    )

    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")

    return JSONResponse(
        {
            "conversion_id": conversion_id,
            "status": conversion.status,
            "file_count": conversion.file_count,
            "transaction_count": conversion.transaction_count,
            "total_amount": conversion.total_amount,
            "payment_reference": conversion.payment_reference,
            "payment_amount": conversion.payment_amount,
            "expires_at": (
                conversion.expires_at.isoformat() if conversion.expires_at else None
            ),
            "created_at": (
                conversion.created_at.isoformat() if conversion.created_at else None
            ),
            "download_url": (
                f"/api/converter/download/{conversion_id}"
                if conversion.status == "completed"
                else None
            ),
        }
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
    conversions = (
        db.query(Conversion)
        .filter(Conversion.user_id == current_user.id)
        .order_by(Conversion.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    total = db.query(Conversion).filter(Conversion.user_id == current_user.id).count()

    return JSONResponse(
        {
            "total": total,
            "skip": skip,
            "limit": limit,
            "conversions": [
                {
                    "id": c.id,
                    "file_name": c.file_name,
                    "file_count": c.file_count,
                    "transaction_count": c.transaction_count,
                    "total_amount": c.total_amount,
                    "payment_reference": c.payment_reference,
                    "payment_amount": c.payment_amount,
                    "status": c.status,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in conversions
            ],
        }
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
