from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Union
import os
import logging
from datetime import datetime

from app.services.report_generator import ReportGenerator
from app.services.email_service import EmailService
from app.core.database import get_db
from app.models.analysis import Analysis

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
report_generator = ReportGenerator()

# Initialize email service with proper error handling
try:
    email_service = EmailService(
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", 587)),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", "")
    )
except Exception as e:
    logger.warning(f"⚠️ Email service initialization failed: {e}")
    email_service = None


@router.get("/report/{analysis_id}", response_model=None)
async def generate_report(
    analysis_id: str,
    format: str = "pdf",
    db: Session = Depends(get_db)
) -> Union[FileResponse, JSONResponse]:
    """
    Generate report for analysis.
    Supports PDF, CSV, and JSON formats.
    """
    try:
        # Get analysis data
        analysis: Optional[Analysis] = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Check payment status
        if analysis.payment_status != "paid":
            raise HTTPException(status_code=402, detail="Payment required")
        
        # Build report data
        report_data: Dict[str, Any] = {
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "statement_type": analysis.statement_type,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "average_balance": analysis.average_balance or 0,
            "total_fees": analysis.total_fees or 0,
            "total_transactions": analysis.total_transactions or 0,
            "monthly_data": analysis.monthly_data or [],
            "category_data": analysis.category_data or [],
            "trend_data": analysis.trend_data or [],
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            "generated_at": datetime.now().isoformat()
        }
        
        format_lower: str = format.lower()
        
        if format_lower == "pdf":
            # Generate PDF report
            pdf_path: str = report_generator.generate_pdf_report(report_data)
            
            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=f"financial_report_{analysis_id}.pdf"
            )
        elif format_lower == "csv":
            # Generate CSV export
            csv_path: str = report_generator.generate_csv_export(report_data)
            
            return FileResponse(
                csv_path,
                media_type="text/csv",
                filename=f"financial_data_{analysis_id}.csv"
            )
        else:
            # Return JSON
            return JSONResponse(report_data)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/email", response_model=None)
async def email_report(
    email: str,
    analysis_id: str,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Email report to user.
    Requires email service to be configured.
    """
    try:
        # Check if email service is available
        if not email_service:
            raise HTTPException(
                status_code=503,
                detail="Email service is not configured. Please check SMTP settings."
            )
        
        # Get analysis data
        analysis: Optional[Analysis] = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Check payment status
        if analysis.payment_status != "paid":
            raise HTTPException(status_code=402, detail="Payment required")
        
        # Build report data
        report_data: Dict[str, Any] = {
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "average_balance": analysis.average_balance or 0,
            "insights": analysis.insights or [],
            "recommendations": analysis.recommendations or [],
            "generated_at": datetime.now().isoformat()
        }
        
        # Generate report PDF first
        try:
            pdf_path: str = report_generator.generate_pdf_report(report_data)
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            pdf_path = None
        
        # Send email with report
        success: bool = email_service.send_report_email(
            to_email=email,
            report_data=report_data,
            report_path=pdf_path
        )
        
        if success:
            # Clean up temporary PDF if it exists
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary PDF: {e}")
            
            return JSONResponse({
                "message": "Report sent successfully",
                "email": email,
                "analysis_id": analysis_id
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email report error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/preview/{analysis_id}", response_model=None)
async def preview_report(
    analysis_id: str,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Preview report data without generating a file.
    Useful for checking data before generating PDF/CSV.
    """
    try:
        # Get analysis data
        analysis: Optional[Analysis] = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Return preview data
        return JSONResponse({
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "total_income": analysis.total_income or 0,
            "total_expenses": analysis.total_expenses or 0,
            "net_cash_flow": analysis.net_cash_flow or 0,
            "total_transactions": analysis.total_transactions or 0,
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            "preview": True,
            "generated_at": datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report preview error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))