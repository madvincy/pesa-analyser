from typing import Any, Dict

from app.core.database import SessionLocal
from app.models.analysis import Analysis
from app.services.report_generator import ReportGenerator
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.report.generate_report_task")
def generate_report_task(analysis_id: str, format: str = "pdf") -> str:
    if format not in ("pdf", "csv"):
        raise ValueError("Report format must be 'pdf' or 'csv'.")

    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis is None:
            raise ValueError(f"Analysis {analysis_id} was not found.")
        if analysis.status != "completed":
            raise ValueError(f"Analysis {analysis_id} is not complete.")

        data: Dict[str, Any] = {
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
            "monthly_data": analysis.monthly_data or [],
            "category_data": analysis.category_data or [],
            "trend_data": analysis.trend_data or [],
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            **(analysis.anonymized_analysis_data or {}),
        }
        generator = ReportGenerator()
        if format == "pdf":
            return generator.generate_pdf_report(data)
        return generator.generate_csv_export(data)
    finally:
        db.close()
