# app/models/applicant.py - COMPLETE FIXED VERSION
from sqlalchemy import Column, String, Boolean, Date, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Applicant(Base):
    __tablename__ = "applicants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    unique_id = Column(String(50), unique=True, nullable=True)

    # SECTION A: Basic Information
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone_number = Column(String(20), nullable=False)
    nin_number = Column(String(20), nullable=False, unique=True, index=True)
    date_of_birth = Column(Date, nullable=False)
    state_of_residence = Column(String(50), nullable=False)
    lga = Column(String(50), nullable=False)  # Local Government Area
    address = Column(Text, nullable=False)

    # SECTION B: Documents
    passport_photo = Column(String(255), nullable=False)
    nin_slip = Column(String(255), nullable=False)

    # SECTION C: Application Details
    application_tier = Column(String(20), nullable=False, default="regular")  # 'regular' or 'vip'
    selected_reasons = Column(JSONB, nullable=False)  # Array of selected reason codes
    additional_details = Column(Text, nullable=True)
    
    # SECTION D: Auto-generated fields
    segmentation_tags = Column(JSONB, nullable=True)  # Auto-generated tags based on reasons
    assigned_programs = Column(JSONB, nullable=True)  # Auto-assigned programs

    # SECTION E: Payment Information
    payment_type = Column(String(20), nullable=True)  # 'regular' or 'vip'
    payment_status = Column(String(20), default="pending")  # 'pending', 'paid', 'failed'
    amount_paid = Column(Float, nullable=True)
    payment_reference = Column(String(100), nullable=True, index=True)

    # SECTION F: Verification Status
    application_password = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    has_paid = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # SECTION G: PDF Tracking Fields
    terms_pdf_path = Column(String(500), nullable=True, comment='Path to Terms & Conditions PDF')
    application_pdf_path = Column(String(500), nullable=True, comment='Path to Application Form PDF')
    terms_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    application_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')

    # Relationship - FIXED: Added back_populates
    officer = relationship("Officer", back_populates="applicant", cascade="all, delete", uselist=False)