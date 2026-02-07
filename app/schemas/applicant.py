# app/schemas/applicant.py - COMPLETE FIXED VERSION
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import Optional, List, Any


class ApplicantBase(BaseModel):
    # SECTION A: Basic Information
    full_name: str
    email: EmailStr
    phone_number: str
    nin_number: str
    date_of_birth: date
    state_of_residence: str
    lga: str
    address: str

    # SECTION B: Documents
    passport_photo: str
    nin_slip: str

    # SECTION C: Application Details
    application_tier: str  # 'regular' or 'vip'
    selected_reasons: List[str]
    additional_details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, title="ApplicantBase")


class ApplicantResponse(ApplicantBase):
    # SECTION D: Meta Information
    id: UUID
    unique_id: Optional[str] = None
    segmentation_tags: Optional[List[str]] = None
    assigned_programs: Optional[List[str]] = None
    
    # SECTION E: Payment Information
    payment_type: Optional[str] = None
    payment_status: Optional[str] = None
    amount_paid: Optional[float] = None
    payment_reference: Optional[str] = None
    
    # SECTION F: Verification Status
    is_verified: bool
    has_paid: bool
    application_password: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    # SECTION G: PDF Tracking
    terms_pdf_path: Optional[str] = None
    application_pdf_path: Optional[str] = None
    terms_generated_at: Optional[datetime] = None
    application_generated_at: Optional[datetime] = None

    model_config = ConfigDict(title="ApplicantResponse")


class ApplicantUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    unique_id: Optional[str] = None   # editable official ID
    is_verified: Optional[bool] = None

    model_config = ConfigDict(title="ApplicantUpdate")


class ApplicantCreate(BaseModel):
    # SECTION A: Basic Information (from form)
    phone_number: str
    nin_number: str
    date_of_birth: date
    state_of_residence: str
    lga: str
    address: str
    
    # SECTION B: Application Details
    selected_reasons: List[str]
    additional_details: Optional[str] = None
    application_tier: str
    
    # SECTION C: Verification
    application_password: str
    
    # SECTION D: Documents (handled separately in form)
    passport_photo: str
    nin_slip: str
    
    # SECTION E: Auto-filled from pre-applicant
    full_name: str
    email: EmailStr

    model_config = ConfigDict(title="ApplicantCreate")


class ApplicantSimpleResponse(BaseModel):
    """Simplified response for basic queries"""
    id: UUID
    full_name: str
    email: EmailStr
    phone_number: str
    application_tier: str
    is_verified: bool
    has_paid: bool
    created_at: datetime

    model_config = ConfigDict(title="ApplicantSimpleResponse")