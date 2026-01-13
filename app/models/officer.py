# app/models/officer.py
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base

class Officer(Base):
    __tablename__ = "officers"
    __table_args__ = {'comment': 'Table storing officer information'}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment='Unique identifier for the officer'
    )
    applicant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applicants.id", ondelete="CASCADE", name='fk_officer_applicant'),
        nullable=False,
        unique=True,
        comment='Reference to the applicant record this officer is associated with'
    )
    unique_id = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True, server_default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    role = Column(String(50), default='officer', nullable=False)
    passport = Column(String(255), nullable=True)
    
    # Personal Information
    full_name = Column(String(100), nullable=True)
    nin_number = Column(String(20), nullable=True)
    gender = Column(String(10), nullable=True)
    rank = Column(String(50), nullable=True)
    position = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    residential_address = Column(Text, nullable=True)
    state_of_residence = Column(String(50), nullable=True)
    local_government_residence = Column(String(50), nullable=True)
    additional_skills = Column(Text, nullable=True)
    
    # Additional Fields
    nationality = Column(String(50), nullable=True)
    country_of_residence = Column(String(50), nullable=True)
    state_of_origin = Column(String(50), nullable=True)
    local_government_origin = Column(String(50), nullable=True)
    religion = Column(String(50), nullable=True)
    place_of_birth = Column(String(100), nullable=True)
    marital_status = Column(String(20), nullable=True)
    bank_name = Column(String(100), nullable=True)
    account_number = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    other_name = Column(String(100), nullable=True)
    do_you_smoke = Column(Boolean, nullable=True)

    # PDF Tracking Fields
    terms_pdf_path = Column(String(500), nullable=True, comment='Path to Terms & Conditions PDF')
    application_pdf_path = Column(String(500), nullable=True, comment='Path to Application Form PDF')
    terms_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    application_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')

    applicant = relationship(
        "Applicant",
        back_populates="officer",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True
    )