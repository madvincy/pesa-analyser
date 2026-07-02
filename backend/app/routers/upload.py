from fastapi import (
    APIRouter, Form, UploadFile, File, HTTPException, Depends,
    BackgroundTasks, Request, WebSocket, WebSocketDisconnect, Query,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List, Callable, Awaitable
import os
import io
import re
import uuid
import logging
import json
import pdfplumber
import PyPDF2
from datetime import datetime

from app.services.pdf_parser import PDFParser
from app.services.ai_analyzer import AIAnalyzer
from app.core.cache import redis_client
from app.core.database import get_db, SessionLocal
from app.models.analysis import Analysis
from app.models.analysis_stages import (
    AnalysisBasicSummary,
    AnalysisCategoryBreakdown,
    AnalysisBehaviorMetrics,
    AnalysisInsights,
)
from app.models.user import User

# ✅ Import from correct location
from app.middleware.auth import (
    get_current_user,
    _resolve_user_from_token,
    _get_or_create_mock_user,
    IS_DEVELOPMENT,
)

# ✅ WebSocket connection registry (see app/core/websocket_manager.py)
from app.core.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
pdf_parser = PDFParser()
ai_analyzer = AIAnalyzer()

# ─── WebSocket auth helper ─────────────────────────────────────────────────
# Depends() dependency injection (used by get_current_user for normal HTTP
# routes) doesn't run the same way over a WebSocket handshake, so this wraps
# the SAME resolution logic get_current_user() uses internally — including
# backend JWTs, NextAuth JWTs, and the dev mock-user fallback — instead of
# reimplementing JWT verification separately here.
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


# ─── Staged analysis persistence ────────────────────────────────────────────
# Maps each stage name (from AIAnalyzer.analyze_transactions_staged) to its
# table + which of its own columns to set from the stage_data dict.
_STAGE_TABLES = {
    "basic_summary": AnalysisBasicSummary,
    "category_breakdown": AnalysisCategoryBreakdown,
    "behavior_metrics": AnalysisBehaviorMetrics,
    "insights": AnalysisInsights,
}


def _make_stage_persister(db: Session, file_id: str) -> Callable[[str, Dict[str, Any]], Awaitable[None]]:
    """
    Returns an async callback suitable for AIAnalyzer.analyze_transactions_staged's
    `on_stage` param. Get-or-creates the relevant stage row, updates only the
    columns present in stage_data, commits, and pushes a WS update — so the
    frontend can render each section the moment it's ready instead of waiting
    for the whole analysis (including the slow AI call) to finish.
    """

    async def persist_stage(stage: str, stage_data: Dict[str, Any]) -> None:
        model = _STAGE_TABLES.get(stage)
        if model is None:
            logger.warning(f"⚠️  Unknown analysis stage '{stage}', skipping persistence")
        else:
            try:
                row = db.query(model).filter_by(analysis_id=file_id).first()
                if not row:
                    row = model(analysis_id=file_id)
                    db.add(row)

                for key, value in stage_data.items():
                    if hasattr(row, key):
                        setattr(row, key, value)

                if stage == "insights":
                    # Second call for this stage (after AI enrichment) flips this flag.
                    row.ai_enriched = "enriched" if "top_income_source" in stage_data else row.ai_enriched or "deterministic_only"

                db.commit()
                logger.info(f"💾 Stage '{stage}' persisted for {file_id}")
            except Exception as e:
                logger.error(f"❌ Failed to persist stage '{stage}' for {file_id}: {e}", exc_info=True)
                db.rollback()

        try:
            await manager.send_status(file_id, {
                "status": "stage_complete",
                "stage": stage,
                "data": stage_data,
            })
        except Exception as e:
            logger.warning(f"WS notify (stage {stage}) failed: {e}")

    return persist_stage


# ─── Tunable: rough per-transaction processing time used to estimate ETA ─────
# Adjust this constant against real timings once you have production data.
SECONDS_PER_TRANSACTION: float = 0.05
MIN_ESTIMATED_SECONDS: int = 5


def estimate_processing_seconds(tx_count: int) -> int:
    """Rough ETA shown to the frontend while analysis runs in the background."""
    return max(MIN_ESTIMATED_SECONDS, round(tx_count * SECONDS_PER_TRANSACTION))


# ─── PDF encryption helper ────────────────────────────────────────────────────
def check_pdf_encryption(
    content: bytes,
    password: Optional[str] = None,
) -> str:
    """Check if PDF is encrypted and handle password."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
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
    content: bytes,
    filename: str,
    password: Optional[str] = None,
) -> bool:
    """Validate whether the uploaded file is a financial statement."""
    try:
        ext: str = os.path.splitext(filename)[1].lower()
        if ext not in [".pdf", ".csv", ".xls", ".xlsx"]:
            logger.warning(f"❌ Invalid extension: {ext}")
            return False

        text: str = ""

        if ext == ".pdf":
            try:
                open_kwargs: Dict[str, Any] = {}
                if password:
                    open_kwargs["password"] = password

                with pdfplumber.open(io.BytesIO(content), **open_kwargs) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        page_text: Optional[str] = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                            logger.debug(f"   Page {page_num+1}: {len(page_text)} chars")
                        else:
                            tables = page.extract_tables()
                            if tables:
                                logger.debug(f"   Page {page_num+1}: Found {len(tables)} tables")
                                for table in tables:
                                    for row in table:
                                        if row:
                                            text += " ".join(str(c) for c in row if c) + "\n"
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}")

            if len(text.strip()) < 50:
                try:
                    reader = PyPDF2.PdfReader(io.BytesIO(content))
                    if reader.is_encrypted:
                        pwd: str = password or ""
                        decrypt_result: int = reader.decrypt(pwd)
                        if decrypt_result == 0:
                            logger.warning("PyPDF2 decrypt failed")
                        else:
                            logger.info(f"PyPDF2 decrypted (result={decrypt_result})")

                    for page_num, page in enumerate(reader.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                            logger.debug(f"   PyPDF2 Page {page_num+1}: {len(page_text)} chars")
                except Exception as e:
                    logger.warning(f"PyPDF2 failed: {e}")

            if len(text.strip()) < 50:
                statement_indicators: List[str] = [
                    "statement", "mpesa", "m-pesa", "bank",
                    "kcb", "equity", "cooperative", "stanbic",
                    "safaricom", "ncba", "absa",
                ]
                if any(s in filename.lower() for s in statement_indicators):
                    return True
                return False

        elif ext in [".csv", ".xls", ".xlsx"]:
            try:
                import pandas as pd
                df = (
                    pd.read_csv(io.BytesIO(content))
                    if ext == ".csv"
                    else pd.read_excel(io.BytesIO(content))
                )
                text = " ".join(df.columns.astype(str))
                sample = df.head(10).astype(str).values.flatten()
                text += " " + " ".join(sample)
            except Exception as e:
                logger.warning(f"pandas parsing failed: {e}")
                return False

        financial_keywords: List[str] = [
            "amount", "balance", "credit", "debit", "transaction",
            "mpesa", "m-pesa", "bank", "account", "withdrawal",
            "deposit", "payment", "transfer", "fee", "charge",
            "statement", "summary", "period", "date", "opening",
            "closing", "total", "currency", "kes", "shillings",
            "receipt", "reference", "code", "service", "charges",
            "m-shwari", "fuliza", "paybill", "till", "airtime",
            "safaricom", "mobile", "money", "sender", "receiver",
        ]

        text_lower: str = text.lower()
        keyword_count: int = sum(1 for kw in financial_keywords if kw in text_lower)

        is_financial: bool = keyword_count >= 3
        if is_financial:
            logger.info(f"✅ Validated as financial statement ({keyword_count} keywords)")
        else:
            logger.warning(f"❌ Not enough keywords: {keyword_count}/3")

        return is_financial

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        return False


# ─── Shared transaction-matching regexes ─────────────────────────────────────
_TX_PATTERN_STRICT: re.Pattern = re.compile(
    r'([A-Z0-9]{10})\s+'                         # Receipt No
    r'(\d{4}-\d{2}-\d{2})\s+'                    # Date
    r'(\d{2}:\d{2}:\d{2})\s+'                    # Time
    r'(.+?)\s+'                                  # Details
    r'(Completed|Failed|Pending)\s+'             # Status
    r'(-?[\d,]+\.\d{2})\s+'                      # Paid In
    r'(-?[\d,]+\.\d{2})\s+'                      # Withdrawn
    r'([\d,]+\.\d{2})'                           # Balance
)

_TX_PATTERN_LENIENT: re.Pattern = re.compile(
    r'([A-Z0-9]{10})\s+'
    r'(\d{4}-\d{2}-\d{2})\s+'
    r'(\d{2}:\d{2}:\d{2})\s+'
    r'(.+?)\s+'
    r'(Completed|Failed|Pending)\s+'
    r'([\d,]+\.\d{2})\s+'
    r'([\d,]+\.\d{2})\s+'
    r'([\d,]+\.\d{2})',
    re.DOTALL
)


# ─── Upload endpoint ──────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_statement(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:

    filename: str = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="File has no name.")

    # ─── Debug: Log headers ──────────────────────────────────────────────────
    logger.info("📋 Request Headers:")
    for key, value in request.headers.items():
        if key.lower() == "authorization":
            logger.info(f"   Authorization: {value[:30]}...")
        else:
            logger.info(f"   {key}: {value}")

    logger.info(f"   Filename: {filename}")
    logger.info(f"   File size: {file.size}")
    logger.info(f"   Content type: {file.content_type}")
    logger.info(f"   Password provided: {bool(password)}")

    # ─── ✅ User is always authenticated now ──────────────────────────────────
    logger.info(f"   ✅ User authenticated: {current_user.id}")
    user_id: uuid.UUID = current_user.id  # Always a UUID now

    try:
        content: bytes = await file.read()
        logger.info(f"   Bytes read: {len(content)}")

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 50 MB.")

        file_ext: str = os.path.splitext(filename)[1].lower()
        allowed: List[str] = [".pdf", ".csv", ".xls", ".xlsx"]
        if file_ext not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format. Allowed: {', '.join(allowed)}",
            )

        if file_ext == ".pdf":
            encryption_status: str = check_pdf_encryption(content, password)
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

        is_financial: bool = validate_financial_statement(content, filename, password)
        logger.info(f"   Is financial: {is_financial}")

        if not is_financial:
            raise HTTPException(
                status_code=400,
                detail="The file does not appear to be a financial statement.",
            )

        file_id: str = str(uuid.uuid4())
        temp_dir: str = os.getenv("TEMP_DIR", "./temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path: str = os.path.join(temp_dir, f"{file_id}{file_ext}")

        with open(temp_path, "wb") as f:
            f.write(content)
        logger.info(f"   Temp file saved: {temp_path}")

        logger.info("🔍 Parsing file...")
        try:
            parsed_data: Dict[str, Any]
            if file_ext == ".pdf":
                parsed_data = pdf_parser.parse_statement(temp_path, password)
            elif file_ext == ".csv":
                parsed_data = pdf_parser.parse_csv(temp_path)
            else:
                parsed_data = pdf_parser.parse_excel(temp_path)

            logger.info("=" * 80)
            logger.info("📊 PARSED DATA SUMMARY")
            logger.info("=" * 80)

            transactions: List[Dict[str, Any]] = parsed_data.get("transactions", [])
            logger.info(f"   Transactions: {len(transactions)}")

            raw_text: str = parsed_data.get("raw_text", "")
            logger.info(f"   Raw text length: {len(raw_text)}")

            statement_type: str = parsed_data.get("statement_type", "unknown")
            logger.info(f"   Statement type: {statement_type}")

            metadata: Dict[str, Any] = parsed_data.get("metadata", {})
            logger.info(f"   Metadata: {metadata}")

            summary: Dict[str, Any] = parsed_data.get("summary", {})
            logger.info(f"   Summary: {summary}")

            if transactions:
                logger.info(f"   First transaction sample: {transactions[0]}")
                logger.info(f"   Last transaction sample: {transactions[-1]}")
            else:
                logger.warning("⚠️ No transactions found in parsed data!")
                if raw_text:
                    logger.info(f"   Raw text preview (first 1500 chars):\n{raw_text[:1500]}")
                else:
                    logger.error("❌ No raw text available!")

            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

        # ─── Create analysis record ──────────────────────────────────────────
        logger.info("💾 Saving analysis record to database...")
        logger.info(f"   user_id: {user_id}")

        analysis = Analysis(
            id=file_id,
            user_id=user_id,
            file_name=filename,
            file_size=len(content),
            file_type=file_ext[1:],
            statement_type=statement_type,
            status="processing",
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        logger.info(f"   ✅ Analysis record created:")
        logger.info(f"      - ID: {file_id}")
        logger.info(f"      - User ID: {user_id}")
        logger.info(f"      - Status: processing")

        tx_count: int = len(transactions)
        estimated_seconds: int = estimate_processing_seconds(tx_count)

        # ─── ✅ Run analysis synchronously for small files ────────────────────
        # If there are no transactions or very few, process immediately
        if tx_count <= 200:
            logger.info(f"🔍 Processing {tx_count} transactions synchronously...")
            try:
                if not transactions:
                    # No transactions - create empty result
                    analysis_result = {
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
                else:
                    # ✅ Run AI analyzer with staged persistence — each group
                    # of fields (basic totals → categories → behavior → AI
                    # insights) is written to its own table and pushed over
                    # WebSocket the moment it's ready, instead of blocking
                    # this whole request on the slowest step (AI enrichment).
                    stage_persister = _make_stage_persister(db, file_id)
                    analysis_result = await ai_analyzer.analyze_transactions_staged(
                        transactions,
                        statement_type,
                        on_stage=stage_persister,
                    )

                # Update analysis record
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

                db.commit()
                db.refresh(analysis)

                # Cache result
                try:
                    redis_client.set(
                        f"analysis:{file_id}",
                        json.dumps(analysis_result, default=str),
                        expire=3600 * 24,
                    )
                except Exception as e:
                    logger.warning(f"Redis set failed: {e}")

                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

                # ─── ✅ Notify any listening WebSocket clients ──────────────────
                # Safe even if nobody has connected yet — send_status() is a no-op
                # when there are no active connections for this file_id.
                try:
                    await manager.send_status(file_id, {
                        "status": "completed",
                        "analysis": analysis_result,
                    })
                except Exception as e:
                    logger.warning(f"WS notify (sync path) failed: {e}")

                # Return complete result
                return JSONResponse({
                    "file_id": file_id,
                    "message": "File uploaded and analyzed successfully.",
                    "file_name": filename,
                    "file_size": len(content),
                    "transaction_count": tx_count,
                    "status": "completed",
                    "analysis": analysis_result,
                })

            except Exception as e:
                logger.error(f"Synchronous analysis failed: {e}", exc_info=True)
                # Fall back to background processing

        # ─── For large files or on error, use background processing ──────────
        logger.info(f"📤 Queuing background task for {tx_count} transactions...")

        # ✅ Let any connected client know we're queued, with an ETA, before
        # the background task even starts (it may take a moment to be scheduled).
        try:
            await manager.send_status(file_id, {
                "status": "queued",
                "message": "Analysis queued, starting shortly…",
                "estimated_seconds": estimated_seconds,
            })
        except Exception as e:
            logger.warning(f"WS notify (queued) failed: {e}")

        # ✅ NOTE: we deliberately do NOT pass `db` here. The request-scoped
        # session from Depends(get_db) is closed as soon as this response is
        # sent — BackgroundTasks run *after* that. Passing a closed session
        # into process_analysis silently breaks commits there, which is very
        # likely the root cause of "Analysis service is unavailable" errors
        # bubbling up from a failed background write. process_analysis now
        # opens its own fresh session instead.
        background_tasks.add_task(
            process_analysis, file_id, parsed_data, temp_path
        )

        response: Dict[str, Any] = {
            "file_id": file_id,
            "message": "File uploaded successfully. Analysis is running in the background.",
            "file_name": filename,
            "file_size": len(content),
            "transaction_count": tx_count,
            "status": "processing",
            "estimated_seconds": estimated_seconds,
        }

        logger.info(f"✅ Upload complete. Response: {response}")
        logger.info("=" * 80)

        return JSONResponse(response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Background analysis (async) ─────────────────────────────────────────────
async def process_analysis(
    file_id: str,
    parsed_data: Dict[str, Any],
    temp_path: str,
) -> None:
    """
    Background task to process analysis for large files.

    ✅ Opens its OWN database session via SessionLocal(). Do not pass in the
    request-scoped `db` from Depends(get_db) — FastAPI closes that session
    right after the HTTP response is sent, which happens before this task
    runs. Writing to a closed session fails silently in ways that look like
    a generic "service unavailable" error further up the stack.
    """
    logger.info("=" * 80)
    logger.info(f"🔵 [PROCESS] process_analysis() called for {file_id}")
    logger.info("=" * 80)

    db: Session = SessionLocal()

    try:
        await manager.send_status(file_id, {
            "status": "processing",
            "progress": 10,
            "message": "Extracting transactions…",
        })

        transactions: List[Dict[str, Any]] = parsed_data.get("transactions", [])
        statement_type: str = parsed_data.get("statement_type", "unknown")
        logger.info(f"   Parsed_data keys: {list(parsed_data.keys())}")
        logger.info(f"   Transactions: {len(transactions)}")
        logger.info(f"   Statement type: {statement_type}")

        # ✅ Get the analysis record to update
        analysis: Optional[Analysis] = db.query(Analysis).filter(Analysis.id == file_id).first()

        if not analysis:
            logger.error(f"❌ Analysis record not found for {file_id}")
            await manager.send_status(file_id, {
                "status": "failed",
                "error": "Analysis record not found.",
            })
            return

        logger.info(f"   Analysis user_id: {analysis.user_id}")

        if not transactions:
            logger.warning("⚠️ No transactions found in parsed data!")

            raw_text: str = parsed_data.get("raw_text", "")
            logger.info(f"   Raw text length: {len(raw_text)}")
            if raw_text:
                logger.info(f"   Raw text preview: {raw_text[:1000]}")

            analysis_result: Dict[str, Any] = {
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
                    "Check the debug endpoint to see what was extracted.",
                ],
                "warnings": ["⚠️ No transactions found in the uploaded file."],
                "recommendations": [
                    "Upload a standard M-PESA statement from Safaricom.",
                    "Ensure the file is not password protected.",
                    "Try using the debug endpoint to test extraction.",
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
        else:
            logger.info(f"✅ Found {len(transactions)} transactions, running AI analyzer...")

            # ✅ Staged persistence: each group of fields lands in its own
            # table and gets pushed over WS as soon as it's ready, cheapest
            # first, AI-enriched insights last. Uses this task's own `db`
            # session (opened via SessionLocal() above) — not the closed
            # request-scoped one.
            stage_persister = _make_stage_persister(db, file_id)
            analysis_result = await ai_analyzer.analyze_transactions_staged(
                transactions,
                statement_type,
                on_stage=stage_persister,
            )
            logger.info(f"   AI analyzer complete. Result keys: {list(analysis_result.keys())}")

        # ─── Update the analysis record ──────────────────────────────────────
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

        db.commit()
        db.refresh(analysis)

        logger.info(f"✅ Analysis record updated for {file_id}")
        logger.info(f"   user_id: {analysis.user_id}")
        logger.info(f"   status: {analysis.status}")
        logger.info(f"   total_transactions: {analysis.total_transactions}")

        # Store in Redis cache
        logger.info("💾 Caching result in Redis...")
        try:
            redis_client.set(
                f"analysis:{file_id}",
                json.dumps(analysis_result, default=str),
                expire=3600 * 24,
            )
            logger.info("   Redis cache set successfully")
        except Exception as e:
            logger.warning(f"Redis set failed: {e}, continuing without cache")

        # ─── ✅ Notify WebSocket clients the analysis is done ──────────────────
        await manager.send_status(file_id, {
            "status": "completed",
            "analysis": analysis_result,
        })

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

        # ─── ✅ Notify WebSocket clients of failure ─────────────────────────────
        try:
            await manager.send_status(file_id, {
                "status": "failed",
                "error": error_message,
            })
        except Exception as ws_err:
            logger.warning(f"WS notify (failed) failed: {ws_err}")

    finally:
        db.close()  # ✅ always release the session this task opened
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"🗑️ Removed temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Could not remove temp file: {e}")


# ─── Status endpoint ──────────────────────────────────────────────────────────
@router.get("/status/{file_id}")
async def get_analysis_status(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Get the status of an analysis"""
    logger.info(f"🔵 [STATUS] Checking status for {file_id}")

    query = db.query(Analysis).filter(
        Analysis.id == file_id,
        Analysis.user_id == current_user.id
    )

    analysis: Optional[Analysis] = query.first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    cached_result = redis_client.get(f"analysis:{file_id}")

    if cached_result:
        try:
            result = json.loads(cached_result) if isinstance(cached_result, str) else cached_result
            logger.info("   Status: completed (from cache)")
            return JSONResponse({
                "status": "completed",
                "analysis": result,
                "file_name": analysis.file_name,
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            })
        except Exception as e:
            logger.error(f"Error parsing cached result: {e}")

    logger.info(f"   Status: {analysis.status}")
    return JSONResponse({
        "status": analysis.status,
        "file_name": analysis.file_name,
        "created_at": analysis.created_at.isoformat(),
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "error_message": analysis.error_message,
    })


# ─── Get user's analyses endpoint ──────────────────────────────────────────
@router.get("/my-analyses")
async def get_my_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
) -> JSONResponse:
    """Get all analyses for the current user"""
    logger.info(f"🔵 [MY-ANALYSES] Getting analyses for user {current_user.id}")

    analyses: List[Analysis] = db.query(Analysis).filter(
        Analysis.user_id == current_user.id
    ).order_by(
        Analysis.created_at.desc()
    ).offset(skip).limit(limit).all()

    total: int = db.query(Analysis).filter(
        Analysis.user_id == current_user.id
    ).count()

    return JSONResponse({
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
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "error_message": a.error_message,
            }
            for a in analyses
        ]
    })


# ─── WebSocket endpoint ────────────────────────────────────────────────────────
@router.websocket("/ws/analysis/{file_id}")
async def analysis_websocket(
    websocket: WebSocket,
    file_id: str,
    token: str = Query(...),
) -> None:
    """
    Live status channel for a single analysis.

    Browsers cannot set an Authorization header on the WS handshake, so the
    access token is passed as a query param instead: `?token=...`.

    On connect, immediately sends the CURRENT status from the DB/cache —
    this covers the case where the analysis already finished before the
    frontend opened the socket (e.g. page refresh, slow client load).
    Afterwards it just waits, and process_analysis() pushes further updates
    through the shared `manager`.
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
        analysis: Optional[Analysis] = db.query(Analysis).filter(
            Analysis.id == file_id,
            Analysis.user_id == user.id,
        ).first()

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
            await websocket.send_json({"status": "completed", "analysis": result})
        elif analysis.status == "failed":
            await websocket.send_json({
                "status": "failed",
                "error": analysis.error_message,
            })
        else:
            await websocket.send_json({
                "status": analysis.status,
                "message": "Still processing…",
            })

        # Keep the connection open; client sends occasional pings/keep-alives.
        # No further action needed here — server-side pushes come from
        # manager.send_status() calls inside process_analysis().
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"🔌 WS client disconnected: {file_id}")
    except Exception as e:
        logger.warning(f"WS error for {file_id}: {e}")
    finally:
        manager.disconnect(file_id, websocket)
        db.close()