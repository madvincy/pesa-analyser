from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET", "your-secret-key-change-me")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token from NextAuth"""
        try:
            # Decode the token
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_signature": True}
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
    
    async def authenticate(self, request: Request):
        """Authenticate request using Bearer token"""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No token provided")
        
        token = auth_header.split(" ")[1]
        payload = self.verify_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Add user info to request state
        request.state.user_id = payload.get("id")
        request.state.user_email = payload.get("email")
        
        return payload

# Singleton instance
security_middleware = SecurityMiddleware()
