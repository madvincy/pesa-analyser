"""
Conversion model for tracking PDF to CSV conversions.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ConversionStatus(str, enum.Enum):
    """Conversion status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    PARTIAL = "partial"


class Conversion(Base):
    """Conversion record model."""

    __tablename__ = "conversions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_count = Column(Integer, default=1)
    transaction_count = Column(Integer, default=0)
    total_amount = Column(Float, default=0.0)
    payment_reference = Column(String(100), nullable=True)
    payment_amount = Column(Float, default=0.0)
    status = Column(Enum(ConversionStatus), default=ConversionStatus.PENDING)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    user = relationship("User", back_populates="conversions")
