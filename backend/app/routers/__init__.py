"""API Routers Module"""

from app.routers.user import router as user_router
from app.routers.admin import router as admin_router
from app.routers.converter import router as converter_router
from app.routers.upload import router as upload_router
from app.routers.analysis import router as analysis_router
from app.routers.reports import router as reports_router
from app.routers.payment import router as payment_router
from app.routers.results import router as results_router

__all__ = [
    "user_router",
    "admin_router",
    "converter_router",
    "upload_router",
    "analysis_router",
    "results_router",
    "reports_router",
    "payment_router",
]
