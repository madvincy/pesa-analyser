from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import logging
import json
from datetime import datetime

from app.core.cache import redis_client
from app.core.database import get_db
from app.models.analysis import Analysis
from app.middleware.auth import get_current_user_optional
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Health score labeling, shared logic for the gauge + note copy ───────────
def _health_label(score: int) -> Dict[str, str]:
    if score >= 80:
        return {"label": "Excellent", "tone": "success", "note": "Your finances are in great shape."}
    if score >= 65:
        return {"label": "Good", "tone": "success", "note": "Solid footing, with room to optimize."}
    if score >= 50:
        return {"label": "Fair", "tone": "warning", "note": "A few habits are holding you back."}
    return {"label": "Needs Attention", "tone": "danger", "note": "Several patterns need addressing soon."}


@router.get("/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> JSONResponse:
    """
    Returns the analysis pre-shaped into report SECTIONS the frontend can
    render directly — chart-ready arrays, note-card content, and table rows —
    instead of making the client reshape raw columns on every render.

    Sections returned:
      - meta            : id, file name, statement type, generated_at
      - summary_cards   : the 4 headline KPI cards (income/expenses/flow/balance)
      - health          : score + label + tone, ready for a radial gauge
      - charts.category_pie   : [{name, value}] for a pie/donut chart
      - charts.monthly_bars   : [{month, income, expenses}] for a grouped bar chart
      - charts.trend_line     : [{date, amount}] for an area/line chart
      - notes.insights        : sticky-note style cards
      - notes.warnings        : sticky-note style cards (danger tone)
      - notes.recommendations : sticky-note style cards (actionable tone)
      - tables.top_categories : ranked table rows with % of total spend
    """
    query = db.query(Analysis).filter(Analysis.id == analysis_id)

    if current_user:
        query = query.filter(Analysis.user_id == current_user.id)
    else:
        raise HTTPException(status_code=401, detail="Authentication required to view this report")

    analysis: Optional[Analysis] = query.first()

    if not analysis:
        exists = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if exists:
            raise HTTPException(status_code=403, detail="Access denied. This analysis does not belong to you.")
        raise HTTPException(status_code=404, detail="Analysis not found")

    if analysis.status != "completed":
        return JSONResponse({
            "status": analysis.status,
            "message": "Report isn't ready yet — analysis is still " + analysis.status,
            "id": str(analysis.id),
        })

    cache_key = f"analysis:{analysis_id}:report"
    cached = redis_client.get(cache_key)
    if cached:
        try:
            return JSONResponse(json.loads(cached) if isinstance(cached, str) else cached)
        except Exception as e:
            logger.warning(f"Report cache parse failed: {e}")

    category_data: List[Dict[str, Any]] = analysis.category_data or []
    monthly_data: List[Dict[str, Any]] = analysis.monthly_data or []
    trend_data: List[Dict[str, Any]] = analysis.trend_data or []
    total_expenses = float(analysis.total_expenses or 0)

    # ── Top categories table with % of spend, sorted descending ─────────────
    sorted_categories = sorted(category_data, key=lambda x: x.get("value", 0), reverse=True)
    top_categories_table = [
        {
            "rank": i + 1,
            "name": c.get("name", "Unknown"),
            "amount": c.get("value", 0),
            "percent_of_spend": round((c.get("value", 0) / total_expenses) * 100, 1) if total_expenses > 0 else 0,
        }
        for i, c in enumerate(sorted_categories[:10])
    ]

    health_score = int(analysis.health_score or 0)
    health_meta = _health_label(health_score)

    report = {
        "status": "completed",
        "meta": {
            "id": str(analysis.id),
            "file_name": analysis.file_name,
            "statement_type": analysis.statement_type,
            "generated_at": datetime.now().isoformat(),
            "period_covered": f"{monthly_data[0]['month']} – {monthly_data[-1]['month']}" if monthly_data else None,
        },
        "summary_cards": [
            {"key": "total_income", "label": "Total Income", "value": float(analysis.total_income or 0), "icon": "trending-up", "tone": "success"},
            {"key": "total_expenses", "label": "Total Expenses", "value": float(analysis.total_expenses or 0), "icon": "trending-down", "tone": "danger"},
            {"key": "net_cash_flow", "label": "Net Cash Flow", "value": float(analysis.net_cash_flow or 0), "icon": "wallet", "tone": "success" if (analysis.net_cash_flow or 0) >= 0 else "danger"},
            {"key": "average_balance", "label": "Average Balance", "value": float(analysis.average_balance or 0), "icon": "activity", "tone": "info"},
        ],
        "health": {
            "score": health_score,
            "max": 100,
            "label": health_meta["label"],
            "tone": health_meta["tone"],
            "note": health_meta["note"],
        },
        "charts": {
            "category_pie": [{"name": c.get("name", "Unknown"), "value": c.get("value", 0)} for c in category_data],
            "monthly_bars": [
                {"month": m.get("month"), "income": m.get("income", 0), "expenses": m.get("expenses", 0)}
                for m in monthly_data
            ],
            "trend_line": [{"date": t.get("date"), "amount": t.get("amount", 0)} for t in trend_data],
        },
        "notes": {
            "insights": [{"id": i, "text": text, "tone": "info"} for i, text in enumerate(analysis.insights or [])],
            "warnings": [{"id": i, "text": text, "tone": "danger"} for i, text in enumerate(analysis.warnings or [])],
            "recommendations": [{"id": i, "text": text, "tone": "success"} for i, text in enumerate(analysis.recommendations or [])],
        },
        "tables": {
            "top_categories": top_categories_table,
        },
    }

    try:
        redis_client.set(cache_key, json.dumps(report, default=str), expire=3600 * 24)
    except Exception as e:
        logger.warning(f"Report cache set failed: {e}")

    return JSONResponse(report)