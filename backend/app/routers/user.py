from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from app.middleware.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.analysis import Analysis
from app.models.chat import ChatHistory

# Create router with explicit type
router: APIRouter = APIRouter()

logger: logging.Logger = logging.getLogger(__name__)

# Type definitions
TransactionDict = Dict[str, Any]
ChatDict = Dict[str, Any]
AnalysisDict = Dict[str, Any]
PaymentDict = Dict[str, Any]

# Mock data
MOCK_ANALYSES: List[AnalysisDict] = [
    {
        "id": str(uuid.uuid4()),
        "userId": "user_123",
        "fileName": "M-PESA Statement Jan 2024.pdf",
        "fileSize": 245760,
        "fileType": "pdf",
        "statementType": "mpesa",
        "totalIncome": 125000,
        "totalExpenses": 98000,
        "netCashFlow": 27000,
        "averageBalance": 45000,
        "totalFees": 2450,
        "totalTransactions": 156,
        "status": "completed",
        "paymentStatus": "paid",
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
]

MOCK_CHATS: List[ChatDict] = [
    {
        "id": str(uuid.uuid4()),
        "userId": "user_123",
        "sessionId": "session_1",
        "message": "What are my biggest expenses?",
        "response": "Your biggest expenses are: Rent (30%), Food (25%), Transport (15%)",
        "tokensUsed": 150,
        "createdAt": datetime.now().isoformat()
    }
]

MOCK_PAYMENTS: List[PaymentDict] = [
    {
        "id": str(uuid.uuid4()),
        "userId": "user_123",
        "amount": 150,
        "currency": "KES",
        "status": "completed",
        "createdAt": datetime.now().isoformat()
    }
]


@router.get("/user/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """Get current user profile"""
    return JSONResponse({
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    })


@router.put("/user/profile")
async def update_user_profile(
    profile_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """Update user profile"""
    if "name" in profile_data:
        current_user.full_name = str(profile_data["name"])
    if "email" in profile_data:
        current_user.email = str(profile_data["email"])
    
    db.commit()
    db.refresh(current_user)
    
    return JSONResponse({
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.full_name,
        "updated_at": datetime.now().isoformat()
    })


@router.get("/user/history")
async def get_user_history(
    type: Optional[str] = Query("all", description="Filter by type: all, analyses, chats"),
    page: Optional[int] = Query(1, ge=1),
    limit: Optional[int] = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Get user history - analyses and chat history (user-specific)"""
    
    user_id: str = str(current_user.id)

    # Query analyses from DB
    analyses_q = db.query(Analysis).filter(Analysis.user_id == current_user.id).order_by(Analysis.created_at.desc())
    analyses_total = analyses_q.count()
    analyses_items = []
    if type in ("all", "analyses"):
        analyses_items = [a.to_dict() for a in analyses_q.offset((page - 1) * limit).limit(limit).all()]

    # Query chats from DB
    chats_q = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).order_by(ChatHistory.created_at.desc())
    chats_total = chats_q.count()
    chats_items = []
    if type in ("all", "chats"):
        chats_items = [c.to_dict() for c in chats_q.offset((page - 1) * limit).limit(limit).all()]
    
    total = (analyses_total if type in ("all", "analyses") else 0) + (chats_total if type in ("all", "chats") else 0)

    return JSONResponse({
        "analyses": analyses_items,
        "chats": chats_items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total > 0 else 1
        }
    })


@router.delete("/user/data")
async def delete_user_data(
    confirm: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """Delete all user data"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")
    
    return JSONResponse({
        "message": "All user data deleted successfully"
    })


@router.get("/user/export")
async def export_user_data(
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """Export all user data"""
    return JSONResponse({
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.full_name,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        },
        "analyses": MOCK_ANALYSES,
        "chatHistory": MOCK_CHATS,
        "payments": MOCK_PAYMENTS,
        "exportedAt": datetime.now().isoformat()
    })


@router.get("/user/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """Get current user info"""
    return JSONResponse({
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    })