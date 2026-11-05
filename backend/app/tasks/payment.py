from datetime import datetime

from app.core.database import SessionLocal
from app.models.analysis import Analysis
from app.models.payment import Payment
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.payment.poll_payment_status_task",
    max_retries=30,
)
def poll_payment_status_task(
    self, payment_id: str, checkout_request_id: str
) -> None:
    from app.routers.payment import get_mpesa_service

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if payment is None or payment.status != "processing":
            return

        result = get_mpesa_service().query_status(checkout_request_id)
        result_code = result.get("ResultCode")
        if result_code is None or (
            str(result_code) == "-1" and result.get("error")
        ):
            if self.request.retries >= self.max_retries:
                payment.status = "failed"
                payment.error_message = "Payment status could not be confirmed."
                db.commit()
                return
            raise self.retry(countdown=10)

        if str(result_code) == "0":
            payment.status = "completed"
            payment.mpesa_receipt_number = result.get("ReceiptNumber")
            payment.completed_at = datetime.now()

            analysis = (
                db.query(Analysis)
                .filter(Analysis.id == payment.analysis_id)
                .first()
            )
            if analysis:
                analysis.payment_status = "paid"
                analysis.payment_amount = payment.amount
                analysis.payment_reference = result.get("ReceiptNumber")
        else:
            payment.status = "failed"
            payment.error_message = result.get("ResultDesc", "Payment failed")

        db.commit()
    finally:
        db.close()
