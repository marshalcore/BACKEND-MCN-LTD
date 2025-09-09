# app/models/pre_applicant.py

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import uuid

from app.database import Base

class PreApplicant(Base):
    __tablename__ = "pre_applicants"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    has_paid = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    application_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # NEW FIELDS FOR RESUME FUNCTIONALITY
    payment_reference = Column(String, nullable=True)
    password_generated = Column(Boolean, default=False)
    password_generated_at = Column(DateTime, nullable=True)
    password_expires_at = Column(DateTime, nullable=True)
    password_used = Column(Boolean, default=False)
    application_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String, default="created")  # created, payment_pending, payment_completed, password_sent, submitted