from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship  # <-- Add this import
from app.database import Base
import uuid
from datetime import datetime

class Applicant(Base):
    __tablename__ = "applicants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    unique_id = Column(String(50), unique=True, nullable=True)

    # SECTION A: Personal Information
    category = Column(String(50), nullable=False)
    marital_status = Column(String(20), nullable=False)
    nin_number = Column(String(20), nullable=False, unique=True)
    full_name = Column(String(100), nullable=False)
    first_name = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)
    other_name = Column(String(50), nullable=True)
    email = Column(String(255), nullable=False, unique=True)
    mobile_number = Column(String(20), nullable=False)
    phone_number = Column(String(20), nullable=False)
    gender = Column(String(10), nullable=False)
    nationality = Column(String(50), nullable=False)
    country_of_residence = Column(String(50), nullable=False)
    state_of_origin = Column(String(50), nullable=False)
    state_of_residence = Column(String(50), nullable=False)
    residential_address = Column(Text, nullable=False)
    local_government_residence = Column(String(50), nullable=False)
    local_government_origin = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    religion = Column(String(30), nullable=False)
    place_of_birth = Column(String(100), nullable=False)

    # SECTION B: Documents
    passport_photo = Column(String(255), nullable=False)
    nin_slip = Column(String(255), nullable=False)
    ssce_certificate = Column(String(255), nullable=False)
    higher_education_degree = Column(String(255), nullable=True)

    # SECTION C: Additional Information
    do_you_smoke = Column(Boolean, nullable=False, default=False)
    agree_to_join = Column(Boolean, nullable=False, default=False)
    agree_to_abide_rules = Column(Boolean, nullable=False, default=False)
    agree_to_return_properties = Column(Boolean, nullable=False, default=False)
    additional_skills = Column(Text, nullable=True)
    design_rating = Column(Integer, nullable=True)

    # SECTION D: Financial Information
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(20), nullable=False)

    # SECTION E: Meta Information
    application_password = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    has_paid = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    officer = relationship("Officer", back_populates="applicant", cascade="all, delete")