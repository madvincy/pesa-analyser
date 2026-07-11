from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import os
import logging
from dotenv import load_dotenv

from app.core.cache import redis_client
from app.core.database import engine, Base
from app.core.logging_config import setup_logging

# ─── Setup logging FIRST before anything else ──────────────────────────────
# This must come BEFORE the logging.disable() calls
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))

# ─── Import model modules so their classes register on Base.metadata ──────
# before create_all() runs. If you add new models later, import them here too.
from app.models import user as _user_models  # noqa: F401
from app.models import analysis as _analysis_models  # noqa: F401

load_dotenv()

# ─── REMOVE these lines ──────────────────────────────────────────────────────
# ❌ REMOVE: logging.disable(logging.CRITICAL)
# ❌ REMOVE: logging.disable(logging.CRITICAL)  (duplicate)

# ─── Import routers after logging is configured ────────────────────────────
from app.routers import (
    user_router,
    admin_router,
    upload_router,
    analysis_router,
    reports_router,
    payment_router,
    results_router,
    converter_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Pesa Analyser API...")
    Base.metadata.create_all(bind=engine)
    redis_client.connect()
    logger.info("✅ Database and Redis connected")
    yield
    logger.info("🛑 Shutting down Pesa Analyser API...")
    redis_client.disconnect()


app: FastAPI = FastAPI(
    title="Pesa Analyser API",
    version="1.0.0",
    description="AI-powered financial statement analysis",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix="/api/v1", tags=["User"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"])
app.include_router(results_router, prefix="/api/v1/results", tags=["Results"])
app.include_router(reports_router, prefix="/api/v1", tags=["Reports"])
app.include_router(payment_router, prefix="/api/v1", tags=["Payment"])
app.include_router(converter_router, prefix="/api/v1", tags=["Converter"])


@app.get("/")
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.getenv("ENV", "development"),
        "api_prefix": "/api/v1",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
