from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from app.core.database import Base
import uuid

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="KES")
    payment_type = Column(String(50), nullable=False)
    
    # M-PESA specific
    phone_number = Column(String(20), nullable=True)
    checkout_request_id = Column(String(100), nullable=True)
    merchant_request_id = Column(String(100), nullable=True)
    mpesa_receipt_number = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)
    
    # Metadata - renamed to payment_metadata to avoid reserved keyword
    payment_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)

class PaymentConfig(Base):
    __tablename__ = "payment_configs"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
