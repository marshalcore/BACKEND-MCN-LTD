# This model represents a pre-applicant for the event. It captures essential information about the applicant, their payment status, tier selection, and other relevant details before they become a full applicant.
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from zoneinfo import ZoneInfo
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
    created_at = Column(DateTime, default=lambda: datetime.now(ZoneInfo("UTC")))
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    # Payment Fields
    payment_reference = Column(String, nullable=True)
    
    # Password Fields
    password_generated = Column(Boolean, default=False)
    password_generated_at = Column(DateTime, nullable=True)
    password_expires_at = Column(DateTime, nullable=True)
    password_used = Column(Boolean, default=False)
    
    # Application Fields
    application_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    
    # Tier Selection Fields
    selected_tier = Column(String(20), nullable=True)  # 'regular' or 'vip'
    tier_selected_at = Column(DateTime, nullable=True)
    
    # Privacy Fields
    privacy_accepted = Column(Boolean, default=False)
    privacy_accepted_at = Column(DateTime, nullable=True)
    
    # Status Tracking
    status = Column(String, default="created")  # created, tier_selected, payment_completed, password_sent, privacy_accepted, submitted