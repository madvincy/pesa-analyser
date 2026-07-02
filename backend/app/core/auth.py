from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, Union
import logging
import os
import jwt
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Mock user for development
MOCK_USER: Dict[str, Any] = {
    "id": "user_123",
    "email": "test@example.com",
    "name": "Test User",
    "role": "user",
    "isActive": True
}

# NextAuth secret (same as frontend NEXTAUTH_SECRET)
NEXTAUTH_SECRET: str = os.getenv("NEXTAUTH_SECRET", "")


async def get_or_create_user(db: Session, email: str, name: str = "User") -> User:
    """Get or create a user by email"""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found"
        )
    
    # Try to find existing user
    user: Optional[User] = db.query(User).filter(User.email == email).first()
    
    if user:
        # Update last login and name if changed
        user.last_login = datetime.now()
        if name and user.full_name != name:
            user.full_name = name
        db.commit()
        db.refresh(user)
        return user
    
    # Create new user for OAuth/First time login
    import secrets
    import string
    random_password: str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    hashed_password: str = hash_password(random_password)
    
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=name or email.split('@')[0],
        password_hash=hashed_password,
        is_active=True,
        is_verified=True,  # OAuth users are verified by provider
        role="user",
        last_login=datetime.now()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


def _get_request_identity(request: Request) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Read user identity from request headers when the frontend passes it explicitly."""
    user_id = request.headers.get("x-user-id") or request.headers.get("X-User-ID")
    email = request.headers.get("x-user-email") or request.headers.get("X-User-Email")
    name = request.headers.get("x-user-name") or request.headers.get("X-User-Name")
    return user_id, email, name


def _coerce_uuid(value: Optional[Any]) -> Optional[uuid.UUID]:
    """Convert a value to a UUID when possible; otherwise return None."""
    if value is None:
        return None
    try:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _get_mock_user(db: Session) -> User:
    """Get or create the mock user for development."""
    mock_user: Optional[User] = db.query(User).filter(User.email == MOCK_USER["email"]).first()
    if mock_user:
        return mock_user
    
    import secrets
    import string
    random_password: str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    hashed_password: str = hash_password(random_password)
    
    mock_user = User(
        id=uuid.uuid4(),
        email=MOCK_USER["email"],
        full_name=MOCK_USER["name"],
        password_hash=hashed_password,
        is_active=True,
        is_verified=True,
        role=MOCK_USER["role"],
        last_login=datetime.now()
    )
    db.add(mock_user)
    db.commit()
    db.refresh(mock_user)
    return mock_user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user, auto-create if doesn't exist.
    Supports both JWT_SECRET and NEXTAUTH_SECRET tokens.
    """
    request_user_id, request_email, request_name = _get_request_identity(request)

    # Check request headers first
    if request_user_id:
        parsed_user_id = _coerce_uuid(request_user_id)
        if parsed_user_id:
            user = db.query(User).filter(User.id == parsed_user_id).first()
            if user and user.is_active:
                return user

    if request_email:
        user = db.query(User).filter(User.email == request_email).first()
        if user and user.is_active:
            return user
        if request_email:
            user = await get_or_create_user(db, request_email, request_name or "User")
            if user and user.is_active:
                return user

    token: str = credentials.credentials
    is_development: bool = os.getenv("ENV", "development") == "development"
    
    # Check if token is a UUID (user ID from frontend fallback)
    try:
        user_id = uuid.UUID(token)
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
        else:
            logger.warning(f"⚠️ No user found with UUID: {user_id}")
    except ValueError:
        pass  # Not a UUID, continue with JWT decoding
    
    # ============================================================
    # 🔍 JWT DECODING
    # ============================================================
    
    try:
        secret_key: str = os.getenv("JWT_SECRET", "dev-secret-key")
        nextauth_secret: str = os.getenv("NEXTAUTH_SECRET", "")
        
        payload: Optional[Dict[str, Any]] = None
        email: Optional[str] = None
        name: Optional[str] = None
        
        # Try 1: Decode with JWT_SECRET
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            logger.info("✅ Token decoded with JWT_SECRET")
        except jwt.InvalidTokenError as e:
            logger.debug(f"JWT_SECRET decode failed: {str(e)}")
        
        # Try 2: Decode with NEXTAUTH_SECRET (for NextAuth tokens)
        if not payload and nextauth_secret:
            try:
                payload = jwt.decode(token, nextauth_secret, algorithms=["HS256"])
                logger.info("✅ Token decoded with NEXTAUTH_SECRET")
            except jwt.InvalidTokenError as e:
                logger.debug(f"NEXTAUTH_SECRET decode failed: {str(e)}")
        
        # Try 3: Decode without verification (development only)
        if not payload and is_development and len(token.split('.')) == 3:
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                logger.warning("⚠️ Token decoded without signature verification (development mode)")
            except Exception as e:
                logger.debug(f"No-verification decode failed: {str(e)}")
        
        # Try 4: Extract from base64 payload (last resort)
        if not payload and len(token.split('.')) == 3:
            try:
                import base64
                import json
                parts = token.split('.')
                if len(parts) >= 2:
                    # Add padding if needed
                    payload_json = parts[1]
                    payload_json += '=' * (4 - len(payload_json) % 4)
                    payload_bytes = base64.urlsafe_b64decode(payload_json)
                    payload = json.loads(payload_bytes)
                    logger.info("✅ Token decoded from base64 payload")
            except Exception as e:
                logger.debug(f"Base64 decode failed: {str(e)}")
        
        # If we have a payload, extract email
        if payload:
            email = payload.get("email")
            name = payload.get("name") or "User"
            
            # If no email, try to get it from sub or other fields
            if not email:
                email = payload.get("sub")
                # If we have a name but no email, create a placeholder email
                if not email and payload.get("name"):
                    display_name = str(payload.get("name") or "user")
                    email = f"{display_name.lower().replace(' ', '.')}@example.com"
            
            if email:
                user: User = await get_or_create_user(db, str(email), str(name))
                if user:
                    return user
                else:
                    logger.error(f"❌ User creation failed for email: {email}")
            else:
                logger.error(f"❌ No email found in payload: {payload}")
        
        # If in development, use mock user
        if is_development:
            logger.warning("⚠️ No valid token found, using mock user in development")
            return _get_mock_user(db)
        
        # No valid token - raise exception
        logger.error("❌ No valid token found - raising 401")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
        
    except jwt.ExpiredSignatureError:
        logger.error("❌ Token has expired")
        if is_development:
            return _get_mock_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ Invalid token: {str(e)}")
        if is_development:
            return _get_mock_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Auth error: {str(e)}")
        if is_development:
            return _get_mock_user(db)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, else None"""
    request_user_id, request_email, request_name = _get_request_identity(request)
    if request_user_id:
        parsed_user_id = _coerce_uuid(request_user_id)
        if parsed_user_id:
            user = db.query(User).filter(User.id == parsed_user_id).first()
            if user and user.is_active:
                return user

    if request_email:
        user = db.query(User).filter(User.email == request_email).first()
        if user and user.is_active:
            return user

    if not credentials:
        return None
    
    try:
        return await get_current_user(request=request, credentials=credentials, db=db)
    except Exception as e:
        logger.warning(f"Optional auth failed: {str(e)}")
        return None


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user, ensuring they are an admin"""
    if current_user.role != "admin" and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode: Dict[str, Any] = data.copy()
    if expires_delta:
        expire: datetime = datetime.utcnow() + expires_delta
    else:
        expire: datetime = datetime.utcnow() + timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", 1440)))
    
    to_encode.update({"exp": expire})
    secret_key: str = os.getenv("JWT_SECRET", "dev-secret-key")
    encoded_jwt: str = jwt.encode(to_encode, secret_key, algorithm=os.getenv("JWT_ALGORITHM", "HS256"))
    return encoded_jwt