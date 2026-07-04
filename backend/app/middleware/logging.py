# app/middleware/logging.py
"""Logging Middleware"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
import json

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses"""

    async def dispatch(self, request: Request, call_next):
        """Log request and response"""

        # Start timer
        start_time = time.time()

        # Log request
        await self.log_request(request)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        await self.log_response(request, response, duration)

        return response

    async def log_request(self, request: Request):
        """Log incoming request"""
        try:
            log_data = {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "client": request.client.host if request.client else None,
            }
            # Log as INFO for easier visibility
            logger.info(f"📥 REQUEST: {request.method} {request.url.path}")
        except Exception as e:
            logger.error(f"Failed to log request: {str(e)}")

    async def log_response(self, request: Request, response, duration: float):
        """Log response"""
        try:
            log_data = {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s",
            }
            # Log with emojis for better visibility
            status_emoji = "✅" if response.status_code < 400 else "❌"
            logger.info(
                f"📤 RESPONSE: {request.method} {request.url.path} → {status_emoji} {response.status_code} ({duration:.3f}s)"
            )
        except Exception as e:
            logger.error(f"Failed to log response: {str(e)}")
