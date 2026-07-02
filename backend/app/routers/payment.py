from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import uuid
import os
import asyncio

from app.services.mpesa_service import MpesaService
from app.core.database import get_db, SessionLocal
from app.models.payment import Payment
from app.models.analysis import Analysis

router = APIRouter()
logger = logging.getLogger(__name__)

# ── M-PESA service ────────────────────────────────────────────────────────────
# Initialised lazily so missing env vars don't crash startup
def get_mpesa_service() -> MpesaService:
    """Get M-PESA service instance"""
    return MpesaService(
        consumer_key=os.getenv("MPESA_CONSUMER_KEY", ""),
        consumer_secret=os.getenv("MPESA_CONSUMER_SECRET", ""),
        passkey=os.getenv("MPESA_PASSKEY", ""),
        shortcode=os.getenv("MPESA_SHORTCODE", ""),
    )


class PaymentRequest(BaseModel):
    """Payment request model"""
    analysis_id: str
    phone_number: str
    amount: float
    payment_type: str = "mpesa"


@router.post("/payment/initiate")
async def initiate_payment(
    request: PaymentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Initiate a payment for an analysis"""
    try:
        # Check if analysis exists
        analysis = db.query(Analysis).filter(Analysis.id == request.analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        if analysis.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Already paid")

        # Create payment record
        payment = Payment(
            id=uuid.uuid4(),
            analysis_id=request.analysis_id,
            amount=request.amount,
            currency="KES",
            payment_type=request.payment_type,
            phone_number=request.phone_number,
            status="pending",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Process M-PESA payment
        if request.payment_type == "mpesa":
            mpesa_service = get_mpesa_service()
            result = mpesa_service.stk_push(
                phone=request.phone_number,
                amount=request.amount,
                account_reference=str(payment.id),
                transaction_desc=f"Pesa Analyser - {analysis.file_name[:20]}",
            )

            if result.get("ResponseCode") == "0":
                payment.checkout_request_id = result.get("CheckoutRequestID")
                payment.merchant_request_id = result.get("MerchantRequestID")
                payment.status = "processing"
                db.commit()

                # Start background polling
                background_tasks.add_task(
                    poll_payment_status,
                    str(payment.id),
                    result.get("CheckoutRequestID"),
                )

                return JSONResponse({
                    "payment_id": str(payment.id),
                    "status": "processing",
                    "message": "STK Push sent. Please check your phone.",
                    "checkout_request_id": result.get("CheckoutRequestID"),
                })
            else:
                payment.status = "failed"
                payment.error_message = result.get("ResponseDescription", "Payment failed")
                db.commit()
                raise HTTPException(
                    status_code=400,
                    detail=result.get("ResponseDescription", "Payment initiation failed"),
                )

        return JSONResponse({
            "payment_id": str(payment.id),
            "status": "pending",
            "message": "Payment initiated",
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment initiation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment/status/{payment_id}")
async def get_payment_status(
    payment_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Check payment status"""
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Query M-PESA if still processing
        if payment.status == "processing" and payment.checkout_request_id:
            mpesa_service = get_mpesa_service()
            result = mpesa_service.query_status(payment.checkout_request_id)

            if result.get("ResultCode") == "0":
                payment.status = "completed"
                payment.mpesa_receipt_number = result.get("ReceiptNumber")
                payment.completed_at = datetime.now()

                analysis = db.query(Analysis).filter(
                    Analysis.id == payment.analysis_id
                ).first()
                if analysis:
                    analysis.payment_status = "paid"
                    analysis.payment_amount = payment.amount
                    analysis.payment_reference = result.get("ReceiptNumber")

                db.commit()

            elif result.get("ResultCode"):
                payment.status = "failed"
                payment.error_message = result.get("ResultDesc", "Payment failed")
                db.commit()

        return JSONResponse({
            "payment_id": str(payment.id),
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "mpesa_receipt": payment.mpesa_receipt_number,
            "error": payment.error_message,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Background polling ────────────────────────────────────────────────────────
async def poll_payment_status(payment_id: str, checkout_request_id: str) -> None:
    """
    Background task to poll M-PESA payment status.
    This runs as a background task and uses its own database session.
    """
    mpesa_service = get_mpesa_service()
    db: Optional[Session] = None

    try:
        for attempt in range(30):
            await asyncio.sleep(10)

            result = mpesa_service.query_status(checkout_request_id)

            # Only act on a terminal result code
            result_code = result.get("ResultCode")
            if result_code is None:
                continue

            # ── Open a fresh DB session for the background task ───────────
            db = SessionLocal()
            try:
                payment = db.query(Payment).filter(Payment.id == payment_id).first()
                if not payment or payment.status != "processing":
                    break

                if result_code == "0":
                    payment.status = "completed"
                    payment.mpesa_receipt_number = result.get("ReceiptNumber")
                    payment.completed_at = datetime.now()

                    analysis = db.query(Analysis).filter(
                        Analysis.id == payment.analysis_id
                    ).first()
                    if analysis:
                        analysis.payment_status = "paid"
                        analysis.payment_amount = payment.amount
                        analysis.payment_reference = result.get("ReceiptNumber")

                else:
                    payment.status = "failed"
                    payment.error_message = result.get("ResultDesc", "Payment failed")
                    logger.warning(f"❌ Payment {payment_id} failed: {payment.error_message}")

                db.commit()
                break  # terminal result received — stop polling

            except Exception as e:
                logger.error(f"Database error in poll attempt {attempt + 1}: {e}")
                if db:
                    db.rollback()
            finally:
                if db:
                    db.close()  # always close background sessions
                    db = None

    except Exception as e:
        logger.error(f"Poll payment status error: {e}", exc_info=True)
    finally:
        if db:
            db.close()