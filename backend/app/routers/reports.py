# backend/app/routers/reports.py
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import os
import logging
from datetime import datetime

from app.services.report_generator import ReportGenerator
from app.services.email_service import EmailService
from app.core.database import get_db
from app.models.analysis import Analysis
from app.models.user import User
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)

# Initialize services
report_generator = ReportGenerator()

# Initialize email service with proper error handling
try:
    email_service = EmailService(
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", 587)),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
    )
except Exception as e:
    logger.warning(f"⚠️ Email service initialization failed: {e}")
    email_service = None


def extract_from_anonymized(analysis: Analysis, field: str, default=0):
    """Helper to extract fields from anonymized_analysis_data with fallback."""
    if not analysis.anonymized_analysis_data:
        return default
    return analysis.anonymized_analysis_data.get(field, default)


@router.get("/{analysis_id}", response_model=None)
async def generate_report(
    analysis_id: str,
    format: str = Query("pdf", regex="^(pdf|csv|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate report for analysis.
    Supports PDF, CSV, and JSON formats.

    - **analysis_id**: UUID of the analysis
    - **format**: Output format (pdf, csv, json)
    """
    try:
        # Get analysis data with user ownership check
        analysis: Optional[Analysis] = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
            .first()
        )

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        # Check payment status
        # if analysis.payment_status != "paid":
        #     raise HTTPException(
        #         status_code=402,
        #         detail="Payment required. Please complete payment to access this report."
        #     )

        # Check if analysis is completed
        if analysis.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Analysis is not completed. Current status: {analysis.status}",
            )

        # Get anonymized data
        anonymized = analysis.anonymized_analysis_data or {}

        # Build report data from both model fields and anonymized data
        report_data: Dict[str, Any] = {
            # Core fields from model
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "statement_type": analysis.statement_type,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "average_balance": analysis.average_balance or 0,
            "total_fees": analysis.total_fees or 0,
            "total_transactions": analysis.total_transactions or 0,
            "health_score": analysis.health_score or 0,
            # JSON data from model
            "monthly_data": analysis.monthly_data or [],
            "category_data": analysis.category_data or [],
            "trend_data": analysis.trend_data or [],
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            # Fields from anonymized_analysis_data
            "savings_rate": anonymized.get("savings_rate", 0),
            "burn_rate_daily": anonymized.get("burn_rate_daily", 0),
            "income_count": anonymized.get("income_count", 0),
            "expense_count": anonymized.get("expense_count", 0),
            "highest_transaction": anonymized.get("highest_transaction", 0),
            "top_category": anonymized.get("top_category", "N/A"),
            "top_income_source": anonymized.get("top_income_source", "N/A"),
            "income_concentration": anonymized.get("income_concentration", 0),
            "fuliza_count": anonymized.get("fuliza_count", 0),
            "fuliza_total": anonymized.get("fuliza_total", 0),
            "betting_pct": anonymized.get("betting_pct", 0),
            "p2p_count": anonymized.get("p2p_count", 0),
            "health_breakdown": anonymized.get("health_breakdown", {}),
            "income_change": anonymized.get("income_change", 0),
            "expenses_change": anonymized.get("expenses_change", 0),
            "highest_transaction_date": anonymized.get("highest_transaction_date", ""),
            "fee_pct": anonymized.get("fee_pct", 0),
            "betting_total": anonymized.get("betting_total", 0),
            "p2p_total": anonymized.get("p2p_total", 0),
            "day_of_week_spend": anonymized.get("day_of_week_spend", []),
            "salary_day": anonymized.get("salary_day", None),
            "recurring_payments": anonymized.get("recurring_payments", []),
            "anomalies": anonymized.get("anomalies", []),
            "fuliza_cycles": anonymized.get("fuliza_cycles", {}),
            "income_analysis": anonymized.get("income_analysis", {}),
            "top_depositors": anonymized.get("top_depositors", []),
            "top_creditors": anonymized.get("top_creditors", []),
            "generated_at": datetime.now().isoformat(),
        }

        # Calculate top category if not in anonymized
        if not report_data["top_category"] or report_data["top_category"] == "N/A":
            category_data = analysis.category_data or []
            if category_data:
                sorted_categories = sorted(
                    category_data, key=lambda x: x.get("value", 0), reverse=True
                )
                if sorted_categories:
                    report_data["top_category"] = sorted_categories[0].get(
                        "name", "N/A"
                    )
                    report_data["top_category_percent"] = round(
                        (
                            sorted_categories[0].get("value", 0)
                            / max(analysis.total_expenses or 1, 1)
                        )
                        * 100,
                        1,
                    )

        format_lower: str = format.lower()

        if format_lower == "pdf":
            # Generate PDF report
            pdf_path: str = report_generator.generate_pdf_report(report_data)

            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=f"financial_report_{analysis_id}.pdf",
                background=None,
            )
        elif format_lower == "csv":
            # Generate CSV export
            csv_path: str = report_generator.generate_csv_export(report_data)

            return FileResponse(
                csv_path,
                media_type="text/csv",
                filename=f"financial_data_{analysis_id}.csv",
                background=None,
            )
        else:
            # Return JSON
            return JSONResponse(report_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email", response_model=None)
async def email_report(
    email: str = Query(..., description="Email address to send the report to"),
    analysis_id: str = Query(..., description="Analysis ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Email report to user.
    Requires email service to be configured.

    - **email**: Recipient email address
    - **analysis_id**: UUID of the analysis
    """
    try:
        # Check if email service is available
        if not email_service:
            raise HTTPException(
                status_code=503,
                detail="Email service is not configured. Please check SMTP settings.",
            )

        # Get analysis data with user ownership check
        analysis: Optional[Analysis] = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
            .first()
        )

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        # Check payment status
        if analysis.payment_status != "paid":
            raise HTTPException(
                status_code=402,
                detail="Payment required. Please complete payment to access this report.",
            )

        # Check if analysis is completed
        if analysis.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Analysis is not completed. Current status: {analysis.status}",
            )

        # Get anonymized data
        anonymized = analysis.anonymized_analysis_data or {}

        # Build report data
        report_data: Dict[str, Any] = {
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "average_balance": analysis.average_balance or 0,
            "health_score": analysis.health_score or 0,
            "total_transactions": analysis.total_transactions or 0,
            "savings_rate": anonymized.get("savings_rate", 0),
            "insights": analysis.insights or [],
            "recommendations": analysis.recommendations or [],
            "generated_at": datetime.now().isoformat(),
        }

        # Generate report PDF
        pdf_path: Optional[str] = None
        try:
            pdf_path = report_generator.generate_pdf_report(report_data)
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            # Continue without PDF attachment (send only summary)

        # Send email with report
        success: bool = email_service.send_report_email(
            to_email=email, report_data=report_data, report_path=pdf_path
        )

        # Clean up temporary PDF if it exists
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info(f"Cleaned up temporary PDF: {pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary PDF: {e}")

        if success:
            return JSONResponse(
                {
                    "message": "Report sent successfully",
                    "email": email,
                    "analysis_id": analysis_id,
                    "sent_at": datetime.now().isoformat(),
                }
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to send email. Please try again later."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email report error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/{analysis_id}", response_model=None)
async def preview_report(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview report data without generating a file.
    Useful for checking data before generating PDF/CSV.

    - **analysis_id**: UUID of the analysis
    """
    try:
        # Get analysis data with user ownership check
        analysis: Optional[Analysis] = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
            .first()
        )

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        # Check payment status
        if analysis.payment_status != "paid":
            raise HTTPException(
                status_code=402,
                detail="Payment required. Please complete payment to access this report.",
            )

        # Get anonymized data
        anonymized = analysis.anonymized_analysis_data or {}

        # Build preview data
        preview_data = {
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "statement_type": analysis.statement_type,
            "status": analysis.status,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "average_balance": analysis.average_balance or 0,
            "total_fees": analysis.total_fees or 0,
            "total_transactions": analysis.total_transactions or 0,
            "health_score": analysis.health_score or 0,
            "savings_rate": anonymized.get("savings_rate", 0),
            "burn_rate_daily": anonymized.get("burn_rate_daily", 0),
            "income_count": anonymized.get("income_count", 0),
            "expense_count": anonymized.get("expense_count", 0),
            "highest_transaction": anonymized.get("highest_transaction", 0),
            "highest_transaction_date": anonymized.get("highest_transaction_date", ""),
            "top_category": anonymized.get("top_category", "N/A"),
            "top_income_source": anonymized.get("top_income_source", "N/A"),
            "income_concentration": anonymized.get("income_concentration", 0),
            "fuliza_count": anonymized.get("fuliza_count", 0),
            "fuliza_total": anonymized.get("fuliza_total", 0),
            "betting_pct": anonymized.get("betting_pct", 0),
            "p2p_count": anonymized.get("p2p_count", 0),
            "income_change": anonymized.get("income_change", 0),
            "expenses_change": anonymized.get("expenses_change", 0),
            "health_breakdown": anonymized.get("health_breakdown", {}),
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            "monthly_data": analysis.monthly_data or [],
            "category_data": analysis.category_data or [],
            "trend_data": analysis.trend_data or [],
            "payment_status": analysis.payment_status,
            "created_at": (
                analysis.created_at.isoformat() if analysis.created_at else None
            ),
            "completed_at": (
                analysis.completed_at.isoformat() if analysis.completed_at else None
            ),
            "preview": True,
            "generated_at": datetime.now().isoformat(),
        }

        # Calculate top category percent
        if preview_data["top_category"] and preview_data["top_category"] != "N/A":
            category_data = analysis.category_data or []
            for cat in category_data:
                if cat.get("name") == preview_data["top_category"]:
                    total = analysis.total_expenses or 1
                    preview_data["top_category_percent"] = round(
                        (cat.get("value", 0) / total) * 100, 1
                    )
                    break

        return JSONResponse(preview_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report preview error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=None)
async def health_check():
    """
    Health check for report service.
    """
    return JSONResponse(
        {
            "status": "healthy",
            "email_configured": email_service is not None,
            "report_dir": report_generator.report_dir,
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.delete("/{analysis_id}", response_model=None)
async def delete_report(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an analysis/report.
    """
    try:
        # Get analysis with user ownership check
        analysis: Optional[Analysis] = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
            .first()
        )

        if not analysis:
            raise HTTPException(status_code=404, detail="Report not found")

        # Delete associated files
        report_dir = os.getenv("REPORTS_DIR", "./reports")
        files_deleted = []

        # Pattern matching for files
        import glob

        patterns = [
            f"*_{analysis_id}.pdf",
            f"*_{analysis_id}.csv",
            f"*_{analysis_id}.json",
            f"financial_report_{analysis_id}.*",
            f"financial_data_{analysis_id}.*",
        ]

        for pattern in patterns:
            for file_path in glob.glob(os.path.join(report_dir, pattern)):
                try:
                    os.remove(file_path)
                    files_deleted.append(os.path.basename(file_path))
                    logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")

        # Delete from database
        db.delete(analysis)
        db.commit()

        return JSONResponse(
            {
                "message": "Report deleted successfully",
                "analysis_id": analysis_id,
                "files_deleted": files_deleted,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete report error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
