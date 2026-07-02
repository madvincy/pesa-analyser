from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import uuid

from app.core.auth import get_current_user, get_current_admin_user
from app.core.database import get_db
from app.models.user import User
from app.models.analysis import Analysis
from app.models.payment import Payment

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Helper Functions ──────────────────────────────────────────────────────────
def generate_mock_id() -> str:
    """Generate a mock UUID string"""
    return str(uuid.uuid4())


def get_mock_timestamp() -> str:
    """Get current timestamp as ISO string"""
    return datetime.now().isoformat()


# ─── Type Definitions ──────────────────────────────────────────────────────────
UserDict = Dict[str, Any]
AnalysisDict = Dict[str, Any]
PaymentDict = Dict[str, Any]
ContactDict = Dict[str, Any]


@router.get("/admin/analytics")
async def get_admin_analytics(
    current_user: User = Depends(get_current_admin_user)
) -> JSONResponse:
    """
    Get admin analytics dashboard data.
    Requires admin privileges.
    """
    try:
        # Mock data for analytics
        return JSONResponse({
            "users": {
                "total": 156,
                "active": 89,
                "newToday": 12,
                "recent": [
                    {"id": generate_mock_id(), "name": "John Doe", "email": "john@example.com", "createdAt": get_mock_timestamp()},
                    {"id": generate_mock_id(), "name": "Jane Smith", "email": "jane@example.com", "createdAt": get_mock_timestamp()},
                    {"id": generate_mock_id(), "name": "Bob Wilson", "email": "bob@example.com", "createdAt": get_mock_timestamp()}
                ]
            },
            "analyses": {
                "total": 345,
                "completed": 278,
                "failed": 23,
                "recent": [
                    {
                        "id": generate_mock_id(),
                        "fileName": "M-PESA Statement.pdf",
                        "user": {"name": "John Doe", "email": "john@example.com"},
                        "status": "completed",
                        "createdAt": get_mock_timestamp()
                    },
                    {
                        "id": generate_mock_id(),
                        "fileName": "Bank Statement.pdf",
                        "user": {"name": "Jane Smith", "email": "jane@example.com"},
                        "status": "pending",
                        "createdAt": get_mock_timestamp()
                    }
                ]
            },
            "payments": {
                "total": 234,
                "successful": 198,
                "failed": 36,
                "revenue": 23450.00
            },
            "tokenUsage": {
                "totalTokens": 456789,
                "totalPrompts": 1234,
                "totalFailed": 45
            },
            "pendingMessages": 8,
            "timestamp": get_mock_timestamp()
        })
        
    except Exception as e:
        logger.error(f"Admin analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users")
async def get_admin_users(
    page: Optional[int] = Query(1, ge=1, description="Page number"),
    limit: Optional[int] = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get all users with pagination.
    Requires admin privileges.
    """
    try:
        # In production, this would query the database with filters
        # For now, using mock data
        mock_users: List[UserDict] = [
            {
                "id": generate_mock_id(),
                "name": "John Doe",
                "email": "john@example.com",
                "role": "user",
                "isActive": True,
                "_count": {"analyses": 5, "payments": 3},
                "createdAt": get_mock_timestamp()
            },
            {
                "id": generate_mock_id(),
                "name": "Jane Smith",
                "email": "jane@example.com",
                "role": "admin",
                "isActive": True,
                "_count": {"analyses": 12, "payments": 8},
                "createdAt": get_mock_timestamp()
            },
            {
                "id": generate_mock_id(),
                "name": "Bob Wilson",
                "email": "bob@example.com",
                "role": "user",
                "isActive": False,
                "_count": {"analyses": 2, "payments": 1},
                "createdAt": get_mock_timestamp()
            }
        ]
        
        # Apply filters
        if search:
            search_lower = search.lower()
            mock_users = [
                u for u in mock_users 
                if search_lower in u["name"].lower() or search_lower in u["email"].lower()
            ]
        
        if role:
            mock_users = [u for u in mock_users if u["role"] == role]
        
        # Apply pagination
        total: int = len(mock_users)
        start: int = (page - 1) * limit
        end: int = start + limit
        paginated_users: List[UserDict] = mock_users[start:end]
        
        return JSONResponse({
            "users": paginated_users,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 1
            }
        })
        
    except Exception as e:
        logger.error(f"Admin users error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users/{user_id}")
async def get_admin_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get a specific user by ID.
    Requires admin privileges.
    """
    try:
        # In production, this would query the database
        # For now, returning mock data
        mock_user: UserDict = {
            "id": user_id,
            "name": "John Doe",
            "email": "john@example.com",
            "role": "user",
            "isActive": True,
            "isVerified": True,
            "phone_number": "+254700123456",
            "createdAt": get_mock_timestamp(),
            "lastLogin": get_mock_timestamp(),
            "_count": {"analyses": 5, "payments": 3}
        }
        
        return JSONResponse({"user": mock_user})
        
    except Exception as e:
        logger.error(f"Get admin user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}")
async def update_admin_user(
    user_id: str,
    user_data: Dict[str, Any],
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Update a user by ID.
    Requires admin privileges.
    """
    try:
        # In production, this would update the database
        return JSONResponse({
            "message": "User updated successfully",
            "user_id": user_id,
            "updated_at": get_mock_timestamp()
        })
        
    except Exception as e:
        logger.error(f"Update admin user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/users/{user_id}")
async def delete_admin_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Delete a user by ID.
    Requires admin privileges.
    """
    try:
        # In production, this would delete from the database
        return JSONResponse({
            "message": "User deleted successfully",
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Delete admin user error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/payments/logs")
async def get_payment_logs(
    page: Optional[int] = Query(1, ge=1, description="Page number"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get payment logs with pagination.
    Requires admin privileges.
    """
    try:
        mock_logs: List[PaymentDict] = [
            {
                "id": generate_mock_id(),
                "user": {"name": "John Doe", "email": "john@example.com"},
                "status": "completed",
                "amount": 150,
                "currency": "KES",
                "payment_type": "mpesa",
                "createdAt": get_mock_timestamp()
            },
            {
                "id": generate_mock_id(),
                "user": {"name": "Jane Smith", "email": "jane@example.com"},
                "status": "failed",
                "amount": 50,
                "currency": "KES",
                "payment_type": "mpesa",
                "errorMessage": "Transaction declined",
                "createdAt": get_mock_timestamp()
            }
        ]
        
        # Apply status filter
        if status:
            mock_logs = [log for log in mock_logs if log["status"] == status]
        
        # Apply pagination
        total: int = len(mock_logs)
        start: int = (page - 1) * limit
        end: int = start + limit
        paginated_logs: List[PaymentDict] = mock_logs[start:end]
        
        return JSONResponse({
            "logs": paginated_logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 1
            }
        })
        
    except Exception as e:
        logger.error(f"Payment logs error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/contact")
async def get_contact_messages(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Get contact messages.
    Requires admin privileges.
    """
    try:
        mock_messages: List[ContactDict] = [
            {
                "id": generate_mock_id(),
                "name": "John Doe",
                "email": "john@example.com",
                "subject": "Billing Issue",
                "message": "I was charged twice for my analysis.",
                "status": "pending",
                "createdAt": get_mock_timestamp()
            },
            {
                "id": generate_mock_id(),
                "name": "Jane Smith",
                "email": "jane@example.com",
                "subject": "Feature Request",
                "message": "Can you add support for more banks?",
                "status": "read",
                "createdAt": get_mock_timestamp()
            }
        ]
        
        # Apply status filter
        if status:
            mock_messages = [msg for msg in mock_messages if msg["status"] == status]
        
        return JSONResponse({
            "messages": mock_messages,
            "total": len(mock_messages)
        })
        
    except Exception as e:
        logger.error(f"Contact messages error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/contact/{message_id}")
async def update_contact_message(
    message_id: str,
    status: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Update a contact message status.
    Requires admin privileges.
    """
    try:
        # In production, this would update the database
        return JSONResponse({
            "message": "Contact message updated successfully",
            "message_id": message_id,
            "status": status,
            "updated_at": get_mock_timestamp()
        })
        
    except Exception as e:
        logger.error(f"Update contact message error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))