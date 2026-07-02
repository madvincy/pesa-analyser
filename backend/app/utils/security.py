import hashlib
import secrets
from typing import Optional, Dict, Any
import base64
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import jwt
import os
import re
import logging

logger = logging.getLogger(__name__)


class SecurityUtils:
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key: str = secret_key or os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "default-secret-key-change-me"))
        self.algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        
        # Ensure key is 32 bytes for Fernet
        key_bytes: bytes = self.secret_key.encode()[:32].ljust(32)
        self.fernet: Fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
    
    # ─── Encryption ──────────────────────────────────────────────────────────
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            raise ValueError(f"Encryption failed: {str(e)}")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    # ─── JWT Token Methods ──────────────────────────────────────────────────
    
    def create_access_token(self, data: Dict[str, Any], expires_in: Optional[int] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token (should contain user_id and email)
            expires_in: Expiration time in minutes (default: 1440 minutes = 24 hours)
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_in:
            expire = datetime.utcnow() + timedelta(minutes=expires_in)
        else:
            # Default to 7 days (10080 minutes)
            expire = datetime.utcnow() + timedelta(minutes=10080)
        
        to_encode.update({
            'exp': expire,
            'iat': datetime.utcnow()
        })
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"JWT creation failed: {e}")
            raise ValueError(f"Token creation failed: {str(e)}")
    
    def generate_token(self, user_id: str, expires_in: int = 1440) -> str:
        """
        Generate JWT token (legacy method - kept for compatibility).
        
        Args:
            user_id: User ID to encode
            expires_in: Expiration time in minutes
            
        Returns:
            Encoded JWT token
        """
        return self.create_access_token({'user_id': user_id}, expires_in)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return payload.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Dict payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT token invalid: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT decode error: {e}")
            return None
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode JWT token without verification (for debugging).
        
        Args:
            token: JWT token to decode
            
        Returns:
            Dict payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm], 
                options={"verify_signature": False}
            )
            return payload
        except Exception as e:
            logger.error(f"JWT decode error: {e}")
            return None
    
    # ─── Password Methods ──────────────────────────────────────────────────
    
    def hash_password(self, password: str) -> str:
        """Hash password for storage"""
        salt: str = secrets.token_hex(16)
        hash_obj = hashlib.sha256((password + salt).encode())
        return f"{salt}:{hash_obj.hexdigest()}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_value = hashed.split(':')
            hash_obj = hashlib.sha256((password + salt).encode())
            return hash_obj.hexdigest() == hash_value
        except Exception:
            return False
    
    # ─── API Key Methods ──────────────────────────────────────────────────
    
    def generate_api_key(self) -> str:
        """Generate API key"""
        return f"pa_{secrets.token_urlsafe(32)}"
    
    # ─── Data Masking ──────────────────────────────────────────────────────
    
    def mask_sensitive_data(self, data: str, keep_chars: int = 4) -> str:
        """Mask sensitive data like phone numbers, emails"""
        if not data:
            return data
        
        if len(data) <= keep_chars * 2:
            return "*" * len(data)
        
        return data[:keep_chars] + "*" * (len(data) - keep_chars * 2) + data[-keep_chars:]
    
    def sanitize_input(self, text: str) -> str:
        """Sanitize user input to prevent injection"""
        # Remove potentially dangerous characters
        text = re.sub(r'[<>]', '', text)
        text = re.sub(r'[\'"]', '', text)
        return text.strip()


# ─── Singleton instance ──────────────────────────────────────────────────────
security: SecurityUtils = SecurityUtils()


# ─── Convenience functions for direct import ─────────────────────────────────

def create_access_token(data: Dict[str, Any], expires_in: Optional[int] = None) -> str:
    """Create a JWT access token"""
    return security.create_access_token(data, expires_in)


def generate_token(user_id: str, expires_in: int = 1440) -> str:
    """Generate JWT token"""
    return security.generate_token(user_id, expires_in)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token"""
    return security.verify_token(token)


def hash_password(password: str) -> str:
    """Hash a password for storage"""
    return security.hash_password(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return security.verify_password(password, hashed)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    return security.encrypt_data(data)


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    return security.decrypt_data(encrypted_data)


def generate_api_key() -> str:
    """Generate API key"""
    return security.generate_api_key()


def mask_sensitive_data(data: str, keep_chars: int = 4) -> str:
    """Mask sensitive data"""
    return security.mask_sensitive_data(data, keep_chars)


def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    return security.sanitize_input(text)