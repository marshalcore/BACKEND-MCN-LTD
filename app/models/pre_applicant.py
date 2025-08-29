# app/models/pre_applicant.py

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.database import Base

class PreApplicant(Base):
    __tablename__ = "pre_applicants"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    has_paid = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)  # Optional for tracking login
    application_password = Column(String, nullable=True)  # ✅ Add this line
    created_at = Column(DateTime, default=datetime.utcnow)
