"""Rate Limiting Middleware"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.clients: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0))
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting"""
        
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not self.is_allowed(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
        
        return await call_next(request)
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is allowed to make request"""
        current_time = time.time()
        count, window_start = self.clients[client_ip]
        
        # Reset if window expired
        if current_time - window_start > 60:
            self.clients[client_ip] = (1, current_time)
            return True
        
        # Check if under limit
        if count < self.requests_per_minute:
            self.clients[client_ip] = (count + 1, window_start)
            return True
        
        return False
