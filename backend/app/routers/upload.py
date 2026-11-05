"""
Upload router for financial statement processing.
Uses the modular PDF parser for extracting transactions from various file formats.
"""

from fastapi import (
    APIRouter,
    Form,
    UploadFile,
    File,
    HTTPException,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List, Callable, Awaitable
import asyncio
import os
import io
import re
import uuid
import logging
import json
import aiofiles
import pdfplumber
import PyPDF2
from datetime import datetime

# Import the modular PDF parser
from app.services.pdf_parser import PDFParser
from app.services.ai_analyzer import AIAnalyzer
from app.core.cache import redis_client
from app.core.database import get_db, SessionLocal
from app.core.upload_security import encrypt_upload_password, decrypt_upload_password
from app.models.analysis import Analysis
from app.models.analysis_stages import (
    AnalysisBasicSummary,
    AnalysisCategoryBreakdown,
    AnalysisBehaviorMetrics,
    AnalysisInsights,
)
from app.models.user import User
from app.tasks.analysis import process_analysis_task

# Import from correct location
from app.middleware.auth import (
    get_current_user,
    _resolve_user_from_token,
    _get_or_create_mock_user,
    IS_DEVELOPMENT,
)

# WebSocket connection registry
from app.core.websocket_manager import manager

# Elasticsearch service (optional)
try:
    from app.services.elasticsearch_service import ElasticsearchService

    ELASTICSEARCH_ENABLED = True
except ImportError:
    ELASTICSEARCH_ENABLED = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Elasticsearch service not available")

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services with the modular parser
pdf_parser = PDFParser(debug=os.getenv("DEBUG", "false").lower() == "true")
ai_analyzer = AIAnalyzer()

# Initialize Elasticsearch service (if available)
elasticsearch_service = None
if ELASTICSEARCH_ENABLED:
    try:
        elasticsearch_service = ElasticsearchService()
        # We'll connect lazily when needed
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize Elasticsearch: {e}")
        elasticsearch_service = None


# ─── WebSocket auth helper ─────────────────────────────────────────────────
async def resolve_ws_user(token: str, db: Session) -> User:
    """Resolve the user for a WS query-param token, mirroring get_current_user()."""
    user = await _resolve_user_from_token(token, db)

    if user:
        if not user.is_active:
            raise ValueError("User account is inactive.")
        return user

    if IS_DEVELOPMENT:
        return _get_or_create_mock_user(db)

    raise ValueError("Invalid or expired token.")


# ─── Elasticsearch Indexing Helper ─────────────────────────────────────────
async def index_analysis_to_elasticsearch(
    file_id: str,
    user_id: str,
    file_name: str,
    transactions: List[Dict[str, Any]],
    analysis_result: Dict[str, Any],
) -> None:
    """
    Index analysis results to Elasticsearch for search.
    This is non-blocking - failures are logged but don't affect the response.
    """
    if not ELASTICSEARCH_ENABLED or elasticsearch_service is None:
        logger.debug("Elasticsearch not available, skipping indexing")
        return

    try:
        # Connect if not already connected
        if (
            not hasattr(elasticsearch_service, "_connected")
            or not elasticsearch_service._connected
        ):
            logger.info("🔌 Connecting to Elasticsearch for indexing...")
            await elasticsearch_service.connect()
            if elasticsearch_service.is_connected():
                logger.info("✅ Connected to Elasticsearch successfully")
            else:
                logger.warning("⚠️ Failed to connect to Elasticsearch for indexing")
                return

        if not elasticsearch_service.is_connected():
            logger.warning("⚠️ Cannot index: Elasticsearch not connected")
            return

        # Prepare document for indexing
        document = {
            "document_id": file_id,
            "user_id": str(user_id),
            "file_name": file_name,
            "file_type": "pdf",
            "upload_date": datetime.now().isoformat(),
            "statement_type": analysis_result.get("statement_type", "unknown"),
            "transaction_count": len(transactions),
            "total_income": float(analysis_result.get("total_income", 0)),
            "total_expenses": float(analysis_result.get("total_expenses", 0)),
            "net_cash_flow": float(analysis_result.get("net_cash_flow", 0)),
            "health_score": int(analysis_result.get("health_score", 0)),
            "transactions": transactions[:1000],  # Limit for ES
            "categories": [
                c.get("name")
                for c in analysis_result.get("category_data", [])
                if c.get("name")
            ],
            "merchants": list(
                set(
                    t.get("merchant_name") or t.get("till_number") or t.get("paybill")
                    for t in transactions
                    if t.get("merchant_name")
                    or t.get("till_number")
                    or t.get("paybill")
                )
            )[:50],
            "insights": analysis_result.get("insights", []),
            "warnings": analysis_result.get("warnings", []),
            "recommendations": analysis_result.get("recommendations", []),
            "monthly_data": analysis_result.get("monthly_data", []),
            "processed_at": datetime.now().isoformat(),
        }

        # Index to Elasticsearch
        await elasticsearch_service.index_document(
            document_id=file_id,
            user_id=str(user_id),
            file_name=file_name,
            content=json.dumps(document),
            file_type="pdf",
            file_size=0,
            metadata={
                "statement_type": analysis_result.get("statement_type", "unknown")
            },
            transactions=transactions[:500],  # Limit for ES
        )

        logger.info(f"✅ Indexed analysis {file_id} to Elasticsearch")

        # Verify count
        try:
            count = await elasticsearch_service.client.count(
                index=elasticsearch_service.index_name
            )
            logger.info(f"📊 Total documents in Elasticsearch: {count['count']}")
        except Exception as e:
            logger.debug(f"Could not get count: {e}")

    except ImportError as e:
        logger.debug(f"Elasticsearch import error: {e}")
    except Exception as e:
        # Non-blocking - just log the error
        logger.error(f"❌ Failed to index to Elasticsearch: {e}", exc_info=True)


# ─── Staged analysis persistence ────────────────────────────────────────────
_STAGE_TABLES = {
    "basic_summary": AnalysisBasicSummary,
    "category_breakdown": AnalysisCategoryBreakdown,
    "behavior_metrics": AnalysisBehaviorMetrics,
    "insights": AnalysisInsights,
}


def _make_stage_persister(
    db: Session, file_id: str
) -> Callable[[str, Dict[str, Any]], Awaitable[None]]:
    """
    Returns an async callback for AIAnalyzer.analyze_transactions_staged's
    `on_stage` param. Persists each stage to its table and pushes WS updates.
    """

    async def persist_stage(stage: str, stage_data: Dict[str, Any]) -> None:
        model = _STAGE_TABLES.get(stage)
        if model is None:
            logger.warning(
                f"⚠️  Unknown analysis stage '{stage}', skipping persistence"
            )
        else:
            try:
                row = db.query(model).filter_by(analysis_id=file_id).first()
                if not row:
                    row = model(analysis_id=file_id)
                    db.add(row)

                for key, value in stage_data.items():
                    if hasattr(row, key):
                        setattr(row, key, value)

                analysis = db.query(Analysis).filter(Analysis.id == file_id).first()
                if analysis:
                    stage_progress = {
                        "basic_summary": 55,
                        "category_breakdown": 70,
                        "behavior_metrics": 85,
                        "insights": 95,
                    }
                    analysis.progress = max(
                        analysis.progress or 0, stage_progress.get(stage, 45)
                    )

                if stage == "insights":
                    row.ai_enriched = (
                        "enriched"
                        if "top_income_source" in stage_data
                        else row.ai_enriched or "deterministic_only"
                    )

                db.commit()
                logger.info(f"💾 Stage '{stage}' persisted for {file_id}")
            except Exception as e:
                logger.error(
                    f"❌ Failed to persist stage '{stage}' for {file_id}: {e}",
                    exc_info=True,
                )
                db.rollback()

        # ✅ FIX: WebSocket notification is optional - never fail the request
        try:
            await manager.send_status(
                file_id,
                {
                    "status": "stage_complete",
                    "stage": stage,
                    "data": stage_data,
                },
            )
        except Exception as e:
            # WebSocket failure is not critical - log debug only
            logger.debug(f"WS notify (stage {stage}) failed: {e}")

    return persist_stage


# ─── ETA estimation ──────────────────────────────────────────────────────────
# ─── PDF encryption helper ────────────────────────────────────────────────────
def check_pdf_encryption(
    source: Any,
    password: Optional[str] = None,
) -> str:
    """Check if PDF is encrypted and handle password."""
    try:
        reader_source = io.BytesIO(source) if isinstance(source, bytes) else source
        reader = PyPDF2.PdfReader(reader_source)
    except Exception as e:
        logger.error(f"PyPDF2 could not open PDF: {e}")
        return "ok"

    if not reader.is_encrypted:
        return "ok"

    if not password:
        result: int = reader.decrypt("")
        if result != 0:
            return "ok"
        return "encrypted_no_password"

    result = reader.decrypt(password)
    if result != 0:
        return "ok"

    logger.warning("🔴 Wrong PDF password")
    return "wrong_password"


# ─── Financial statement validation ──────────────────────────────────────────
def validate_financial_statement(
    source: Any,
    filename: str,
    password: Optional[str] = None,
) -> bool:
    """Validate whether the uploaded file is a financial statement."""
    try:
        ext: str = os.path.splitext(filename)[1].lower()
        if ext not in [".pdf", ".csv", ".xls", ".xlsx"]:
            logger.warning(f"❌ Invalid extension: {ext}")
            return False

        keywords: List[str] = [
            "amount", "balance", "credit", "debit", "transaction", "mpesa",
            "m-pesa", "bank", "account", "withdrawal", "deposit", "payment",
            "transfer", "fee", "charge", "statement", "summary", "period",
            "date", "opening", "closing", "total", "currency", "kes",
            "shillings", "receipt", "reference", "code", "service", "charges",
            "m-shwari", "fuliza", "paybill", "till", "airtime", "safaricom",
            "mobile", "money", "sender", "receiver",
        ]

        file_source = io.BytesIO(source) if isinstance(source, bytes) else source
        if ext == ".pdf":
            try:
                open_kwargs: Dict[str, Any] = {}
                if password:
                    open_kwargs["password"] = password

                matched_keywords = set()
                with pdfplumber.open(file_source, **open_kwargs) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        if page_num >= 5:
                            break
                        page_text: Optional[str] = page.extract_text()
                        if page_text:
                            page_lower = page_text.lower()
                            matched_keywords.update(
                                keyword
                                for keyword in keywords
                                if keyword in page_lower
                            )
                        else:
                            tables = page.extract_tables()
                            if tables:
                                for table in tables:
                                    for row in table:
                                        if row:
                                            row_text = " ".join(
                                                str(cell) for cell in row if cell
                                            )
                                            row_lower = row_text.lower()
                                            matched_keywords.update(
                                                keyword
                                                for keyword in keywords
                                                if keyword in row_lower
                                            )
                        if len(matched_keywords) >= 3:
                            return True
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}")

            statement_indicators = (
                "statement", "mpesa", "m-pesa", "bank", "kcb", "equity",
                "cooperative", "stanbic", "safaricom", "ncba", "absa",
            )
            return any(term in filename.lower() for term in statement_indicators)

        elif ext in [".csv", ".xls", ".xlsx"]:
            try:
                import pandas as pd

                df = (
                    pd.read_csv(file_source, nrows=10)
                    if ext == ".csv"
                    else pd.read_excel(file_source, nrows=10)
                )
                text = " ".join(df.columns.astype(str))
                sample = df.head(10).astype(str).values.flatten()
                text += " " + " ".join(sample)
            except Exception as e:
                logger.warning(f"pandas parsing failed: {e}")
                return False

        text_lower: str = text.lower()
        keyword_count: int = sum(1 for kw in keywords if kw in text_lower)

        is_financial: bool = keyword_count >= 3
        if is_financial:
            logger.info(
                f"✅ Validated as financial statement ({keyword_count} keywords)"
            )
        else:
            logger.warning(f"❌ Not enough keywords: {keyword_count}/3")

        return is_financial

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        return False


def _create_empty_analysis_result(statement_type: str) -> Dict[str, Any]:
    """Create an empty analysis result when no transactions are found."""
    return {
        "total_income": 0,
        "total_expenses": 0,
        "net_cash_flow": 0,
        "savings_rate": 0,
        "health_score": 0,
        "total_transactions": 0,
        "insights": [
            "No transactions could be extracted from this file.",
            "Please ensure the file is a valid M-PESA statement from Safaricom.",
            f"The file was detected as: {statement_type}",
        ],
        "warnings": ["⚠️ No transactions found in the uploaded file."],
        "recommendations": [
            "Upload a standard M-PESA statement from Safaricom.",
            "Ensure the file is not password protected.",
        ],
        "category_data": [],
        "monthly_data": [],
        "trend_data": [],
        "recurring_payments": [],
        "anomalies": [],
        "health_breakdown": {},
        "day_of_week_spend": [],
        "salary_day": None,
        "income_change": 0,
        "expenses_change": 0,
        "statement_type": statement_type,
        "fuliza_cycles": {"cycle_count": 0, "same_day_repayment_rate": 0},
        "income_analysis": {"loan_disbursement_warning": False},
        "average_balance": 0,
        "burn_rate_daily": 0,
        "total_fees": 0,
        "fee_pct": 0,
        "fuliza_total": 0,
        "fuliza_count": 0,
        "betting_total": 0,
        "betting_pct": 0,
        "p2p_total": 0,
        "p2p_count": 0,
        "highest_transaction": 0,
        "highest_transaction_date": "",
        "top_category": "N/A",
        "top_category_amount": 0,
        "top_category_percent": 0,
        "top_income_source": "N/A",
        "income_concentration": 0,
        "transaction_count": 0,
    }


# ─── Upload endpoint ──────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Upload and analyze a financial statement file.

    Supports: PDF (M-PESA, bank), CSV, Excel
    Uses the modular PDF parser for extraction.
    """
    filename: str = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="File has no name.")

    user_id: uuid.UUID = current_user.id
    file_ext: str = os.path.splitext(filename)[1].lower()
    allowed: List[str] = [".pdf", ".csv", ".xls", ".xlsx"]
    if file_ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format. Allowed: {', '.join(allowed)}",
        )

    file_id = str(uuid.uuid4())
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = os.path.join(upload_dir, f"{file_id}{file_ext}")
    max_file_size = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))
    file_size = 0
    queue_submitted = False

    try:
        async with aiofiles.open(temp_path, "wb") as target:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > max_file_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_file_size // (1024 * 1024)} MB.",
                    )
                await target.write(chunk)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # ─── PDF Encryption Check ────────────────────────────────────────────
        if file_ext == ".pdf":
            encryption_status: str = await asyncio.to_thread(
                check_pdf_encryption, temp_path, password
            )
            logger.info(f"   Encryption status: {encryption_status}")

            if encryption_status == "encrypted_no_password":
                raise HTTPException(
                    status_code=401,
                    detail="PDF is password protected. Please provide the password.",
                )
            if encryption_status == "wrong_password":
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect PDF password. Please try again.",
                )

        # ─── Validate Financial Statement ────────────────────────────────────
        is_financial: bool = await asyncio.to_thread(
            validate_financial_statement, temp_path, filename, password
        )
        logger.info(f"   Is financial: {is_financial}")

        if not is_financial:
            raise HTTPException(
                status_code=400,
                detail="The file does not appear to be a financial statement.",
            )

        analysis = Analysis(
            id=file_id,
            user_id=user_id,
            file_name=filename,
            file_size=file_size,
            file_type=file_ext[1:],
            status="queued",
            progress=0,
        )
        db.add(analysis)
        db.commit()
        try:
            encrypted_password = (
                encrypt_upload_password(password) if password else None
            )
            process_analysis_task.apply_async(
                args=(file_id, temp_path, encrypted_password),
                task_id=file_id,
            )
            queue_submitted = True
        except Exception as queue_error:
            db.rollback()
            failed_analysis = (
                db.query(Analysis).filter(Analysis.id == file_id).first()
            )
            if failed_analysis:
                failed_analysis.status = "failed"
                failed_analysis.error_message = "Analysis queue is unavailable."
                db.commit()
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error("Could not queue analysis %s: %s", file_id, queue_error)
            raise HTTPException(
                status_code=503,
                detail="Analysis service is temporarily unavailable. Please try again.",
            ) from queue_error

        await manager.send_status(
            file_id,
            {"status": "queued", "progress": 0, "message": "Analysis queued."},
        )
        return JSONResponse(
            {
                "file_id": file_id,
                "message": "File uploaded successfully. Analysis is queued.",
                "file_name": filename,
                "file_size": file_size,
                "status": "queued",
            },
            status_code=202,
        )

    except HTTPException:
        if os.path.exists(temp_path) and not queue_submitted:
            os.remove(temp_path)
        raise
    except Exception as e:
        logger.error(f"Unhandled upload error: {e}", exc_info=True)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail="Upload could not be processed.") from e


# ─── Background Analysis ─────────────────────────────────────────────────────
async def process_analysis(
    file_id: str,
    temp_path: str,
    encrypted_password: Optional[str] = None,
) -> None:
    """
    Process an uploaded statement in a worker-owned database session.

    Opens its OWN database session via SessionLocal() to avoid using
    the closed request-scoped session.
    """
    logger.info("=" * 80)
    logger.info(f"🔵 [PROCESS] process_analysis() called for {file_id}")
    logger.info("=" * 80)

    db: Session = SessionLocal()

    try:
        if redis_client.client is None and not redis_client.connect():
            logger.warning(
                "Redis unavailable in analysis worker; continuing without cache."
            )

        # ✅ FIX: WebSocket notification is optional
        try:
            await manager.send_status(
                file_id,
                {
                    "status": "processing",
                    "progress": 10,
                    "message": "Extracting transactions…",
                },
            )
        except Exception as e:
            logger.debug(f"WS notify (processing) failed: {e}")

        analysis: Optional[Analysis] = (
            db.query(Analysis).filter(Analysis.id == file_id).first()
        )

        if not analysis:
            logger.error(f"❌ Analysis record not found for {file_id}")
            try:
                await manager.send_status(
                    file_id,
                    {
                        "status": "failed",
                        "error": "Analysis record not found.",
                    },
                )
            except Exception as e:
                logger.debug(f"WS notify (failed) failed: {e}")
            return

        logger.info(f"   Analysis user_id: {analysis.user_id}")

        analysis.status = "processing"
        analysis.progress = 5
        db.commit()

        def update_parse_progress(page: int, total_pages: int) -> None:
            if page == 1 or page == total_pages or page % 5 == 0:
                analysis.progress = 5 + round(30 * page / max(total_pages, 1))
                db.commit()

        file_ext = os.path.splitext(temp_path)[1].lower()
        password = (
            decrypt_upload_password(encrypted_password)
            if encrypted_password
            else None
        )
        if file_ext == ".pdf":
            parsed_data = pdf_parser.parse_statement(
                temp_path, password, progress_callback=update_parse_progress
            )
        elif file_ext == ".csv":
            parsed_data = pdf_parser.parse_csv(temp_path)
        else:
            parsed_data = pdf_parser.parse_excel(temp_path)

        transactions: List[Dict[str, Any]] = parsed_data.get("transactions", [])
        statement_type: str = parsed_data.get("statement_type", "unknown")
        analysis.statement_type = statement_type
        analysis.progress = 40
        db.commit()

        logger.info(
            "Parsed %s transactions from %s (%s)",
            len(transactions),
            analysis.file_name,
            statement_type,
        )

        if not transactions:
            logger.warning("No transactions found for analysis %s", file_id)
            analysis_result = _create_empty_analysis_result(statement_type)
        else:
            analysis.progress = 45
            db.commit()
            stage_persister = _make_stage_persister(db, file_id)
            analysis_result = await ai_analyzer.analyze_transactions_staged(
                transactions,
                statement_type,
                on_stage=stage_persister,
            )
            logger.info(
                f"   AI analyzer complete. Result keys: {list(analysis_result.keys())}"
            )

        # ─── Update Analysis Record ──────────────────────────────────────────
        logger.info("💾 Updating analysis record in database...")

        analysis.status = "completed"
        analysis.total_income = analysis_result.get("total_income", 0)
        analysis.total_expenses = analysis_result.get("total_expenses", 0)
        analysis.net_cash_flow = analysis_result.get("net_cash_flow", 0)
        analysis.average_balance = analysis_result.get("average_balance", 0)
        analysis.total_fees = analysis_result.get("total_fees", 0)
        analysis.total_transactions = analysis_result.get("total_transactions", 0)
        analysis.monthly_data = analysis_result.get("monthly_data", [])
        analysis.category_data = analysis_result.get("category_data", [])
        analysis.trend_data = analysis_result.get("trend_data", [])
        analysis.insights = analysis_result.get("insights", [])
        analysis.warnings = analysis_result.get("warnings", [])
        analysis.recommendations = analysis_result.get("recommendations", [])
        analysis.health_score = analysis_result.get("health_score", 0)
        analysis.completed_at = datetime.now()
        analysis.anonymized_analysis_data = analysis_result
        analysis.progress = 100

        db.commit()
        db.refresh(analysis)

        logger.info(f"✅ Analysis record updated for {file_id}")
        logger.info(f"   user_id: {analysis.user_id}")
        logger.info(f"   status: {analysis.status}")
        logger.info(f"   total_transactions: {analysis.total_transactions}")

        # ─── Cache in Redis ────────────────────────────────────────────────────
        logger.info("💾 Caching result in Redis...")
        try:
            redis_client.set(
                f"analysis:{file_id}",
                analysis_result,
                expire=3600 * 24,
            )
            logger.info("   Redis cache set successfully")
        except Exception as e:
            logger.warning(f"Redis set failed: {e}, continuing without cache")

        # ✅ Index to Elasticsearch (non-blocking)
        try:
            logger.info(f"📤 Indexing analysis {file_id} to Elasticsearch...")
            await index_analysis_to_elasticsearch(
                file_id=file_id,
                user_id=str(analysis.user_id),
                file_name=analysis.file_name,
                transactions=transactions,
                analysis_result=analysis_result,
            )
        except Exception as e:
            logger.error(f"❌ Elasticsearch indexing error: {e}", exc_info=True)

        # ─── Notify WebSocket Clients ────────────────────────────────────────
        try:
            await manager.send_status(
                file_id,
                {
                    "status": "completed",
                    "progress": 100,
                    "analysis": analysis_result,
                },
            )
        except Exception as e:
            logger.debug(f"WS notify (completed) failed: {e}")

        logger.info("=" * 80)
        logger.info(f"✅ [PROCESS] process_analysis() complete for {file_id}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Analysis error for {file_id}: {e}", exc_info=True)
        error_message = str(e)
        try:
            analysis = db.query(Analysis).filter(Analysis.id == file_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.error_message = error_message
                db.commit()
                logger.info(f"   Database updated with error status for {file_id}")
        except Exception as db_err:
            logger.error(f"   Failed to update DB status: {db_err}")

        try:
            await manager.send_status(
                file_id,
                {
                    "status": "failed",
                    "error": error_message,
                },
            )
        except Exception as ws_err:
            logger.debug(f"WS notify (failed) failed: {ws_err}")

    finally:
        db.close()
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"🗑️ Removed temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Could not remove temp file: {e}")


# ─── Status Endpoint ──────────────────────────────────────────────────────────
@router.get("/status/{file_id}")
async def get_analysis_status(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Get the status of an analysis"""
    logger.info(f"🔵 [STATUS] Checking status for {file_id}")

    query = db.query(Analysis).filter(
        Analysis.id == file_id, Analysis.user_id == current_user.id
    )

    analysis: Optional[Analysis] = query.first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    cached_result = redis_client.get(f"analysis:{file_id}")

    if cached_result:
        try:
            result = json.loads(cached_result) if isinstance(cached_result, str) else cached_result
            logger.info("   Status: completed (from cache)")
            return JSONResponse(
                {
                    "status": "completed",
                    "progress": 100,
                    "analysis": result,
                    "file_name": analysis.file_name,
                    "created_at": analysis.created_at.isoformat(),
                    "completed_at": (
                        analysis.completed_at.isoformat()
                        if analysis.completed_at
                        else None
                    ),
                }
            )
        except Exception as e:
            logger.error(f"Error parsing cached result: {e}")

    logger.info(f"   Status: {analysis.status}")
    return JSONResponse(
        {
            "status": analysis.status,
            "progress": analysis.progress,
            "analysis": (
                analysis.anonymized_analysis_data
                if analysis.status == "completed"
                else None
            ),
            "file_name": analysis.file_name,
            "created_at": analysis.created_at.isoformat(),
            "completed_at": (
                analysis.completed_at.isoformat() if analysis.completed_at else None
            ),
            "error_message": analysis.error_message,
        }
    )


# ─── Get User's Analyses ─────────────────────────────────────────────────────
@router.get("/my-analyses")
async def get_my_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
) -> JSONResponse:
    """Get all analyses for the current user"""
    logger.info(f"🔵 [MY-ANALYSES] Getting analyses for user {current_user.id}")

    analyses: List[Analysis] = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    total: int = db.query(Analysis).filter(Analysis.user_id == current_user.id).count()

    return JSONResponse(
        {
            "total": total,
            "skip": skip,
            "limit": limit,
            "analyses": [
                {
                    "id": str(a.id),
                    "file_name": a.file_name,
                    "file_size": a.file_size,
                    "file_type": a.file_type,
                    "statement_type": a.statement_type,
                    "status": a.status,
                    "total_income": float(a.total_income or 0),
                    "total_expenses": float(a.total_expenses or 0),
                    "total_transactions": int(a.total_transactions or 0),
                    "health_score": int(a.health_score or 0),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "completed_at": (
                        a.completed_at.isoformat() if a.completed_at else None
                    ),
                    "error_message": a.error_message,
                }
                for a in analyses
            ],
        }
    )


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────
@router.websocket("/ws/analysis/{file_id}")
async def analysis_websocket(
    websocket: WebSocket,
    file_id: str,
    token: str = Query(...),
) -> None:
    """
    Live status channel for a single analysis.

    The access token is passed as a query param: `?token=...`.
    On connect, sends the current status from DB/cache.
    """
    auth_db: Session = SessionLocal()
    try:
        user = await resolve_ws_user(token, auth_db)
    except Exception as e:
        logger.warning(f"WS auth failed for {file_id}: {e}")
        await websocket.close(code=4401)
        return
    finally:
        auth_db.close()

    await manager.connect(file_id, websocket)
    db: Session = SessionLocal()

    try:
        analysis: Optional[Analysis] = (
            db.query(Analysis)
            .filter(
                Analysis.id == file_id,
                Analysis.user_id == user.id,
            )
            .first()
        )

        if not analysis:
            await websocket.send_json({"status": "not_found"})
        elif analysis.status == "completed":
            cached = redis_client.get(f"analysis:{file_id}")
            result: Optional[Dict[str, Any]] = None
            if cached:
                try:
                    result = json.loads(cached) if isinstance(cached, str) else cached
                except Exception:
                    result = None
            if result is None:
                result = analysis.anonymized_analysis_data
            await websocket.send_json(
                {"status": "completed", "progress": 100, "analysis": result}
            )
        elif analysis.status == "failed":
            await websocket.send_json(
                {
                    "status": "failed",
                    "error": analysis.error_message,
                }
            )
        else:
            await websocket.send_json(
                {
                    "status": analysis.status,
                    "progress": analysis.progress,
                    "message": "Still processing…",
                }
            )

        if not analysis or analysis.status in ("completed", "failed"):
            return

        last_status = analysis.status if analysis else None
        last_progress = analysis.progress if analysis else None
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=4)
                continue
            except asyncio.TimeoutError:
                db.expire_all()
                analysis = (
                    db.query(Analysis)
                    .filter(
                        Analysis.id == file_id,
                        Analysis.user_id == user.id,
                    )
                    .first()
                )
                if not analysis:
                    await websocket.send_json({"status": "not_found"})
                    break

                if (
                    analysis.status == last_status
                    and analysis.progress == last_progress
                ):
                    continue

                payload: Dict[str, Any] = {
                    "status": analysis.status,
                    "progress": analysis.progress,
                }
                if analysis.status == "completed":
                    cached = redis_client.get(f"analysis:{file_id}")
                    if cached:
                        payload["analysis"] = (
                            json.loads(cached) if isinstance(cached, str) else cached
                        )
                elif analysis.status == "failed":
                    payload["error"] = analysis.error_message
                else:
                    payload["message"] = "Analysis is processing."

                await websocket.send_json(payload)
                last_status = analysis.status
                last_progress = analysis.progress
                if analysis.status in ("completed", "failed"):
                    break

    except WebSocketDisconnect:
        logger.info(f"🔌 WS client disconnected: {file_id}")
    except Exception as e:
        logger.warning(f"WS error for {file_id}: {e}")
    finally:
        manager.disconnect(file_id, websocket)
        db.close()
