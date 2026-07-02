"""Authentication Middleware and Dependencies

Handles both:
1. Backend-issued JWTs (signed with JWT_SECRET, containing `user_id`)
2. NextAuth-issued JWTs from the frontend (signed with NEXTAUTH_SECRET,
   containing `email` / `sub` / `name` — no `user_id` claim)

Falls back to a mock user in development if no valid token is found,
so local testing / Postman calls without auth still work.
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os
import uuid
import secrets
import string
import jwt

from app.core.database import get_db
from app.models.user import User
from app.utils.security import hash_password

security_scheme = HTTPBearer(auto_error=False)

JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-key")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
NEXTAUTH_SECRET: str = os.getenv("NEXTAUTH_SECRET", "")
IS_DEVELOPMENT: bool = os.getenv("ENV", "development") == "development"

MOCK_USER: Dict[str, Any] = {
    "id": "user_123",
    "email": "test@example.com",
    "name": "Test User",
    "role": "user",
    "isActive": True,
}


async def get_or_create_user(db: Session, email: str, name: str = "User") -> User:
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in token",
        )

    user: Optional[User] = db.query(User).filter(User.email == email).first()

    if user:
        user.last_login = datetime.now()
        if name and user.full_name != name:
            user.full_name = name
        db.commit()
        db.refresh(user)
        return user

    random_password: str = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=name or email.split("@")[0],
        password_hash=hash_password(random_password),
        is_active=True,
        is_verified=True,
        role="user",
        last_login=datetime.now(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def _get_or_create_mock_user(db: Session) -> User:
    mock_user: Optional[User] = db.query(User).filter(User.email == MOCK_USER["email"]).first()
    if mock_user:
        return mock_user

    random_password: str = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )
    mock_user = User(
        id=uuid.uuid4(),
        email=MOCK_USER["email"],
        full_name=MOCK_USER["name"],
        password_hash=hash_password(random_password),
        is_active=True,
        is_verified=True,
        role=MOCK_USER["role"],
        last_login=datetime.now(),
    )
    db.add(mock_user)
    try:
        db.commit()
    except IntegrityError:
        # ✅ Another concurrent request already created it between our SELECT
        # and this INSERT (classic get-or-create race). Roll back this failed
        # insert and just fetch the row the other request created instead of
        # crashing with an uncaught 500.
        db.rollback()
        mock_user = db.query(User).filter(User.email == MOCK_USER["email"]).first()
        if mock_user is None:
            # Extremely unlikely (would mean it was deleted in between), but
            # don't silently return None -- surface a clear error instead.
            raise RuntimeError("Failed to get or create mock user after IntegrityError.")
        return mock_user

    db.refresh(mock_user)
    return mock_user

def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass

    if NEXTAUTH_SECRET:
        try:
            payload = jwt.decode(token, NEXTAUTH_SECRET, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            pass
        except jwt.InvalidTokenError:
            pass

    if IS_DEVELOPMENT and len(token.split(".")) == 3:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception:
            pass

    return None


async def _resolve_user_from_token(token: str, db: Session) -> Optional[User]:
    try:
        user_id = uuid.UUID(token)
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user
    except ValueError:
        pass

    payload = _decode_token(token)
    if not payload:
        return None

    user_id_claim = payload.get("user_id")
    if user_id_claim:
        try:
            user = db.query(User).filter(User.id == user_id_claim).first()
            if user:
                return user
        except Exception:
            pass

    email = payload.get("email") or payload.get("sub")
    name = payload.get("name")

    if not email and name:
        email = f"{name.lower().replace(' ', '.')}@example.com"

    if email:
        user = await get_or_create_user(db, email, name or "User")
        if user:
            return user

    return None


def _get_request_identity(request: Request) -> tuple[Optional[str], Optional[str], Optional[str]]:
    user_id = request.headers.get("x-user-id") or request.headers.get("X-User-ID")
    email = request.headers.get("x-user-email") or request.headers.get("X-User-Email")
    name = request.headers.get("x-user-name") or request.headers.get("X-User-Name")
    return user_id, email, name


def _coerce_uuid(value: Optional[Any]) -> Optional[uuid.UUID]:
    if value is None:
        return None
    try:
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    request_user_id, request_email, request_name = _get_request_identity(request)

    if hasattr(request.state, "user_id") and request.state.user_id:
        parsed_user_id = _coerce_uuid(request.state.user_id)
        if parsed_user_id:
            user = db.query(User).filter(User.id == parsed_user_id).first()
            if user and user.is_active:
                return user

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
        if IS_DEVELOPMENT:
            return _get_or_create_mock_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await _resolve_user_from_token(credentials.credentials, db)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    if IS_DEVELOPMENT:
        return _get_or_create_mock_user(db)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    request_user_id, request_email, _ = _get_request_identity(request)

    if hasattr(request.state, "user_id") and request.state.user_id:
        parsed_user_id = _coerce_uuid(request.state.user_id)
        if parsed_user_id:
            user = db.query(User).filter(User.id == parsed_user_id).first()
            if user and user.is_active:
                return user

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

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "", 1)
    try:
        user = await _resolve_user_from_token(token, db)
    except HTTPException:
        return None
    except Exception:
        return None

    if user and user.is_active:
        return user

    return None


def get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[str]:
    request_user_id, _, _ = _get_request_identity(request)

    if hasattr(request.state, "user_id") and request.state.user_id:
        parsed_user_id = _coerce_uuid(request.state.user_id)
        if parsed_user_id:
            return str(parsed_user_id)

    if request_user_id:
        parsed_user_id = _coerce_uuid(request_user_id)
        if parsed_user_id:
            return str(parsed_user_id)

    if not credentials:
        return None

    payload = _decode_token(credentials.credentials)
    if not payload:
        return None

    return payload.get("user_id")


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/upload",
            "/api/v1/debug-pdf",
            "/api/v1/payment/callback",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/verify",
            "/api/v1/auth/reset-password",
        ]

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = _decode_token(token)
            if payload and payload.get("user_id"):
                request.state.user_id = payload.get("user_id")
                request.state.user_email = payload.get("email")
                request.state.user = payload
        return await call_next(request)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode: Dict[str, Any] = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=int(os.getenv("JWT_EXPIRE_MINUTES", 1440))
        )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    return _decode_token(token)
