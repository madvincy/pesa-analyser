from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.types import JSON as SQLJSON


class Analysis(Base):
    __tablename__ = "analyses"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # ✅ FIX: Make sure user_id has ForeignKey
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    statement_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Analysis results
    total_income: Mapped[float] = mapped_column(Float, default=0)
    total_expenses: Mapped[float] = mapped_column(Float, default=0)
    net_cash_flow: Mapped[float] = mapped_column(Float, default=0)
    average_balance: Mapped[float] = mapped_column(Float, default=0)
    total_fees: Mapped[float] = mapped_column(Float, default=0)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    health_score: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON data
    monthly_data: Mapped[List[Dict[str, Any]]] = mapped_column(SQLJSON, default=list)
    category_data: Mapped[List[Dict[str, Any]]] = mapped_column(SQLJSON, default=list)
    trend_data: Mapped[List[Dict[str, Any]]] = mapped_column(SQLJSON, default=list)
    insights: Mapped[List[str]] = mapped_column(SQLJSON, default=list)
    warnings: Mapped[List[str]] = mapped_column(SQLJSON, default=list)
    recommendations: Mapped[List[str]] = mapped_column(SQLJSON, default=list)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Payment
    payment_status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_amount: Mapped[float] = mapped_column(Float, default=0)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Anonymized data
    anonymized_analysis_data: Mapped[Dict[str, Any]] = mapped_column(SQLJSON, default=dict)
    
    # ─── Relationships ──────────────────────────────────────────────────────
    user = relationship("User", back_populates="analyses")
    
    def __repr__(self) -> str:
        return f"<Analysis {self.id} - {self.file_name}>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "statement_type": self.statement_type,
            "total_income": self.total_income,
            "total_expenses": self.total_expenses,
            "net_cash_flow": self.net_cash_flow,
            "total_transactions": self.total_transactions,
            "health_score": self.health_score,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }