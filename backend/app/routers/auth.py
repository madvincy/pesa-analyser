from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from app.core.database import get_db
from app.models.user import User
from app.utils.security import verify_password, create_access_token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login endpoint to get JWT token.
    """
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        logger.warning(f"❌ Login failed: User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        logger.warning(f"❌ Login failed: Invalid password for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token using security utils
    access_token_data = {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
    }
    access_token = create_access_token(access_token_data)
    
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
    }