from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True)
    
    # ─── Relationships ──────────────────────────────────────────────────────
    # If you want a relationship to analyses, you need a foreign key in analyses
    # Option 1: Add a foreign key to analyses table
    # analyses = relationship("Analysis", back_populates="api_key")
    
    # Option 2: Remove the relationship if not needed
    # analyses = relationship("Analysis")  # This will fail without foreign key
    
    # User relationship
    user = relationship("User", back_populates="api_keys")