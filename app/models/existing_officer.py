from sqlalchemy import Column, String, Boolean, DateTime, Text, Date, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class ExistingOfficer(Base):
    __tablename__ = "existing_officers"
    __table_args__ = {'comment': 'Table for existing officers - UPDATED for 2-upload system'}

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment='Unique identifier for the existing officer'
    )
    
    # Credential Fields
    officer_id = Column(String(50), unique=True, nullable=False, comment='Officer ID in NEW format: PREFIX/ALPHANUMERIC/INTAKE')
    email = Column(String(255), unique=True, nullable=False, comment='Officer email')
    phone = Column(String(20), nullable=False, comment='Officer phone number')
    password_hash = Column(String(255), nullable=False, comment='Hashed password')
    
    # NEW FIELDS: Service Dates (from master prompt)
    date_of_enlistment = Column(Date, nullable=False, comment='Date officer enlisted - REQUIRED')
    date_of_promotion = Column(Date, nullable=True, comment='Date of last promotion - OPTIONAL')
    
    # Category Field - MCN, MBT, MBC (extracted from officer_id)
    category = Column(
        String(50), 
        nullable=True, 
        comment='Officer category: MCN (Marshal Core of Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board of Committee)'
    )
    
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
    
    # Personal Information
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
    registration_pdf_path = Column(String(500), nullable=True, comment='Path to Existing Officer Registration Form PDF')
    terms_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    registration_generated_at = Column(DateTime(timezone=True), nullable=True, comment='When Registration PDF was generated')
    
    # NEW: Simplified Document Upload Fields (ONLY 2 UPLOADS)
    passport_uploaded = Column(Boolean, default=False, comment='Passport photo uploaded status')
    passport_path = Column(String(255), nullable=True, comment='Passport photo path - JPG/PNG, 2MB max')
    consolidated_pdf_uploaded = Column(Boolean, default=False, comment='Consolidated PDF uploaded status')
    consolidated_pdf_path = Column(String(255), nullable=True, comment='Consolidated PDF path - All 10 documents in one PDF, 10MB max')
    
    # REMOVED: Old document fields (6+ separate documents)
    # nin_uploaded, ssce_uploaded, birth_certificate_uploaded, appointment_letter_uploaded, promotion_letters_uploaded
    # nin_slip, ssce_certificate, birth_certificate, letter_of_first_appointment, promotion_letters
    
    # Other documents (keep these for backward compatibility but they're optional now)
    service_certificate = Column(String(255), nullable=True, comment='Service certificate')
    medical_certificate = Column(String(255), nullable=True, comment='Medical certificate')
    guarantor_form = Column(String(255), nullable=True, comment='Guarantor form')
    other_documents = Column(Text, nullable=True, comment='Other documents JSON array')
    
    # Dashboard tracking
    dashboard_access_count = Column(Integer, default=0, comment='Number of times dashboard accessed')
    last_dashboard_access = Column(DateTime(timezone=True), nullable=True, comment='Last dashboard access timestamp')
    
    # Audit Fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True, comment='Who created this record')
    updated_by = Column(String(100), nullable=True, comment='Who last updated this record')
    
    # Comments/Notes
    admin_notes = Column(Text, nullable=True, comment='Administrator notes')
    rejection_reason = Column(Text, nullable=True, comment='Reason for rejection if applicable')
    
    # Indexes for faster lookups
    __table_args__ = (
        Index('ix_existing_officer_id', 'officer_id'),
        Index('ix_existing_officer_email', 'email'),
        Index('ix_existing_officer_category', 'category'),
        Index('ix_existing_officer_status', 'status'),
        Index('ix_existing_officer_enlistment', 'date_of_enlistment'),
        Index('ix_existing_passport_uploaded', 'passport_uploaded'),
        Index('ix_existing_consolidated_uploaded', 'consolidated_pdf_uploaded'),
    )