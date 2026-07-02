# backend/app/routers/results.py
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import logging
import json
from datetime import datetime

from app.core.cache import redis_client
from app.core.database import get_db
from app.models.analysis import Analysis
from app.middleware.auth import get_current_user, get_current_user_optional
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, analysis_id: str):
        await websocket.accept()
        if analysis_id not in self.active_connections:
            self.active_connections[analysis_id] = []
        self.active_connections[analysis_id].append(websocket)

    def disconnect(self, websocket: WebSocket, analysis_id: str):
        if analysis_id in self.active_connections:
            self.active_connections[analysis_id].remove(websocket)
            if not self.active_connections[analysis_id]:
                del self.active_connections[analysis_id]

    async def broadcast(self, analysis_id: str, message: dict):
        if analysis_id in self.active_connections:
            for connection in self.active_connections[analysis_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()


@router.websocket("/ws/{analysis_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_id: str):
    """WebSocket endpoint for real-time analysis updates"""
    await manager.connect(websocket, analysis_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, analysis_id)


@router.get("/{analysis_id}")
async def get_analysis_results(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> JSONResponse:
    """
    Get comprehensive analysis results with all data for charts and tables.
    """
    try:
        logger.info(f"🔍 Fetching analysis results for: {analysis_id}")

        # Build query with user filtering
        query = db.query(Analysis).filter(Analysis.id == analysis_id)

        if current_user:
            query = query.filter(Analysis.user_id == current_user.id)
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required to view analysis"
            )

        analysis: Optional[Analysis] = query.first()

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        if analysis.status != "completed":
            return JSONResponse({
                "status": analysis.status,
                "message": f"Analysis is {analysis.status}. Please wait.",
                "id": str(analysis.id)
            })

        # Get additional data from anonymized_analysis_data
        anonymized_data = analysis.anonymized_analysis_data or {}
        
        # Extract fields from anonymized_data
        highest_transaction = anonymized_data.get('highest_transaction', 0)
        highest_transaction_date = anonymized_data.get('highest_transaction_date', '')
        income_count = anonymized_data.get('income_count', 0)
        expense_count = anonymized_data.get('expense_count', 0)
        fuliza_total = anonymized_data.get('fuliza_total', 0)
        fuliza_count = anonymized_data.get('fuliza_count', 0)
        betting_total = anonymized_data.get('betting_total', 0)
        betting_pct = anonymized_data.get('betting_pct', 0)
        p2p_total = anonymized_data.get('p2p_total', 0)
        p2p_count = anonymized_data.get('p2p_count', 0)
        savings_rate = anonymized_data.get('savings_rate', 0)
        burn_rate_daily = anonymized_data.get('burn_rate_daily', 0)
        fee_pct = anonymized_data.get('fee_pct', 0)
        top_income_source = anonymized_data.get('top_income_source', 'N/A')
        income_concentration = anonymized_data.get('income_concentration', 0)
        health_breakdown = anonymized_data.get('health_breakdown', {})
        day_of_week_spend = anonymized_data.get('day_of_week_spend', [])
        salary_day = anonymized_data.get('salary_day', None)
        recurring_payments = anonymized_data.get('recurring_payments', [])
        anomalies = anonymized_data.get('anomalies', [])
        income_change = anonymized_data.get('income_change', 0)
        expenses_change = anonymized_data.get('expenses_change', 0)
        fuliza_cycles = anonymized_data.get('fuliza_cycles', {'cycle_count': 0, 'same_day_repayment_rate': 0})
        income_analysis = anonymized_data.get('income_analysis', {'loan_disbursement_warning': False})
        top_depositors = anonymized_data.get('top_depositors', [])
        top_creditors = anonymized_data.get('top_creditors', [])

        # Build comprehensive result with all chart data
        result = {
            "id": str(analysis.id),
            "user_id": str(analysis.user_id) if analysis.user_id else None,
            "file_name": analysis.file_name,
            "file_size": analysis.file_size,
            "file_type": analysis.file_type,
            "statement_type": analysis.statement_type,
            "status": analysis.status,
            
            # Financial Metrics
            "total_income": float(analysis.total_income or 0),
            "total_expenses": float(analysis.total_expenses or 0),
            "net_cash_flow": float(analysis.net_cash_flow or 0),
            "average_balance": float(analysis.average_balance or 0),
            "total_fees": float(analysis.total_fees or 0),
            "total_transactions": int(analysis.total_transactions or 0),
            "health_score": int(analysis.health_score or 0),
            
            # Additional metrics from anonymized_data
            "savings_rate": float(savings_rate or 0),
            "burn_rate_daily": float(burn_rate_daily or 0),
            "fee_pct": float(fee_pct or 0),
            "fuliza_total": float(fuliza_total or 0),
            "fuliza_count": int(fuliza_count or 0),
            "betting_total": float(betting_total or 0),
            "betting_pct": float(betting_pct or 0),
            "p2p_total": float(p2p_total or 0),
            "p2p_count": int(p2p_count or 0),
            "income_count": int(income_count or 0),
            "expense_count": int(expense_count or 0),
            "top_income_source": top_income_source,
            "income_concentration": float(income_concentration or 0),
            "income_change": float(income_change or 0),
            "expenses_change": float(expenses_change or 0),
            
            # Chart Data
            "monthly_data": analysis.monthly_data or [],
            "category_data": analysis.category_data or [],
            "trend_data": analysis.trend_data or [],
            
            # Insights & Recommendations
            "insights": analysis.insights or [],
            "warnings": analysis.warnings or [],
            "recommendations": analysis.recommendations or [],
            
            # Top Categories
            "top_category": None,
            "top_category_amount": 0,
            "top_category_percent": 0,
            
            # Transaction Stats
            "highest_transaction": float(highest_transaction or 0),
            "highest_transaction_date": highest_transaction_date or "",
            
            # Health breakdown
            "health_breakdown": health_breakdown or {},
            
            # Additional analysis data
            "day_of_week_spend": day_of_week_spend or [],
            "salary_day": salary_day,
            "recurring_payments": recurring_payments or [],
            "anomalies": anomalies or [],
            "fuliza_cycles": fuliza_cycles or {'cycle_count': 0, 'same_day_repayment_rate': 0},
            "income_analysis": income_analysis or {'loan_disbursement_warning': False},
            "top_depositors": top_depositors or [],
            "top_creditors": top_creditors or [],
            
            # Payment Info
            "payment_status": analysis.payment_status or "pending",
            "payment_amount": float(analysis.payment_amount or 0),
            
            # Timestamps
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None
        }

        # Calculate top category
        category_data = analysis.category_data or []
        if category_data:
            sorted_categories = sorted(category_data, key=lambda x: x.get("value", 0), reverse=True)
            if sorted_categories:
                result["top_category"] = sorted_categories[0].get("name", "N/A")
                result["top_category_amount"] = sorted_categories[0].get("value", 0)
                total = analysis.total_expenses or 1
                result["top_category_percent"] = round((result["top_category_amount"] / total) * 100, 1)

        # Cache result
        try:
            redis_client.set(
                f"analysis_results:{analysis_id}",
                json.dumps(result, default=str),
                expire=3600 * 24
            )
        except Exception as e:
            logger.warning(f"Redis cache set failed: {e}")

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get analysis results error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))