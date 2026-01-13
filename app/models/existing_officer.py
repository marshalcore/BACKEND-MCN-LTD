# app/models/existing_officer.py
from sqlalchemy import Column, String, Boolean, DateTime, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class ExistingOfficer(Base):
    __tablename__ = "existing_officers"
    __table_args__ = {'comment': 'Table for officers who registered in the past without payment'}

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment='Unique identifier for the existing officer'
    )
    
    # Credential Fields
    officer_id = Column(String(50), unique=True, nullable=False, comment='Original officer ID from legacy system')
    email = Column(String(255), unique=True, nullable=False, comment='Officer email')
    phone = Column(String(20), nullable=False, comment='Officer phone number')
    password_hash = Column(String(255), nullable=False, comment='Hashed password')
    
    # Verification Fields
    is_verified = Column(Boolean, default=False, comment='Whether officer credentials are verified')
    verification_date = Column(DateTime(timezone=True), nullable=True, comment='Date when officer was verified')
    verified_by = Column(String(100), nullable=True, comment='Admin who verified the officer')
    
    # Status Fields
    status = Column(
        String(20),
        default='pending',
        nullable=False,
        comment='Status: pending, verified, approved, rejected'
    )
    is_active = Column(Boolean, default=True, comment='Whether officer account is active')
    last_login = Column(DateTime(timezone=True), nullable=True, comment='Last login timestamp')
    
    # Personal Information (23 fields as specified)
    full_name = Column(String(100), nullable=False, comment='Full name')
    nin_number = Column(String(20), nullable=False, unique=True, comment='National Identification Number')
    gender = Column(String(10), nullable=False, comment='Gender')
    date_of_birth = Column(Date, nullable=False, comment='Date of birth')
    place_of_birth = Column(String(100), nullable=False, comment='Place of birth')
    nationality = Column(String(50), nullable=False, comment='Nationality')
    marital_status = Column(String(20), nullable=False, comment='Marital status')
    
    # Contact Information
    residential_address = Column(Text, nullable=False, comment='Residential address')
    state_of_residence = Column(String(50), nullable=False, comment='State of residence')
    local_government_residence = Column(String(50), nullable=False, comment='LGA of residence')
    country_of_residence = Column(String(50), nullable=False, comment='Country of residence')
    
    # Origin Information
    state_of_origin = Column(String(50), nullable=False, comment='State of origin')
    local_government_origin = Column(String(50), nullable=False, comment='LGA of origin')
    
    # Professional Information
    rank = Column(String(50), nullable=False, comment='Officer rank')
    position = Column(String(100), nullable=False, comment='Position/title')
    years_of_service = Column(String(20), nullable=True, comment='Years of service')
    service_number = Column(String(50), nullable=True, unique=True, comment='Service number')
    
    # Additional Information
    religion = Column(String(30), nullable=True, comment='Religion')
    additional_skills = Column(Text, nullable=True, comment='Additional skills')
    
    # Financial Information
    bank_name = Column(String(100), nullable=True, comment='Bank name')
    account_number = Column(String(20), nullable=True, comment='Bank account number')
    
    # PDF Tracking Fields
    terms_pdf_path = Column(String(500), nullable=True, comment='Path to Terms & Conditions PDF')
    application_pdf_path = Column(String(500), nullable=True, comment='Path to Application Form PDF')
    terms_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    application_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')
    
    # Document Paths (10+ file types)
    passport_photo = Column(String(255), nullable=True, comment='Passport photo path')
    nin_slip = Column(String(255), nullable=True, comment='NIN slip path')
    ssce_certificate = Column(String(255), nullable=True, comment='SSCE certificate path')
    birth_certificate = Column(String(255), nullable=True, comment='Birth certificate path')
    letter_of_first_appointment = Column(String(255), nullable=True, comment='First appointment letter')
    promotion_letters = Column(String(255), nullable=True, comment='Promotion letters')
    service_certificate = Column(String(255), nullable=True, comment='Service certificate')
    medical_certificate = Column(String(255), nullable=True, comment='Medical certificate')
    guarantor_form = Column(String(255), nullable=True, comment='Guarantor form')
    other_documents = Column(Text, nullable=True, comment='Other documents JSON array')
    
    # Audit Fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True, comment='Who created this record')
    updated_by = Column(String(100), nullable=True, comment='Who last updated this record')
    
    # Comments/Notes
    admin_notes = Column(Text, nullable=True, comment='Administrator notes')
    rejection_reason = Column(Text, nullable=True, comment='Reason for rejection if applicable')