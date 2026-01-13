# app/schemas/existing_officer.py
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from uuid import UUID
import re


class ExistingOfficerVerify(BaseModel):
    """Schema for verifying existing officer credentials"""
    officer_id: str = Field(..., min_length=3, max_length=50, description="Officer ID from legacy system")
    email: EmailStr = Field(..., description="Officer email address")
    
    @validator('officer_id')
    def validate_officer_id(cls, v):
        if not re.match(r'^[A-Za-z0-9\-_]+$', v):
            raise ValueError('Officer ID can only contain letters, numbers, hyphens, and underscores')
        return v


class ExistingOfficerRegister(BaseModel):
    """Schema for registering an existing officer"""
    # Credentials
    officer_id: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    phone: str = Field(..., pattern=r'^\+?[\d\s\-\(\)]{10,20}$')
    password: str = Field(..., min_length=8)
    
    # Personal Information
    full_name: str = Field(..., min_length=2, max_length=100)
    nin_number: str = Field(..., min_length=11, max_length=20)
    gender: str = Field(..., pattern='^(male|female|other)$')
    date_of_birth: date
    place_of_birth: str = Field(..., min_length=2, max_length=100)
    nationality: str = Field(..., min_length=2, max_length=50)
    marital_status: str = Field(..., pattern='^(single|married|divorced|widowed)$')
    
    # Contact Information
    residential_address: str = Field(..., min_length=5, max_length=500)
    state_of_residence: str = Field(..., min_length=2, max_length=50)
    local_government_residence: str = Field(..., min_length=2, max_length=50)
    country_of_residence: str = Field(..., min_length=2, max_length=50)
    
    # Origin Information
    state_of_origin: str = Field(..., min_length=2, max_length=50)
    local_government_origin: str = Field(..., min_length=2, max_length=50)
    
    # Professional Information
    rank: str = Field(..., min_length=2, max_length=50)
    position: str = Field(..., min_length=2, max_length=100)
    years_of_service: Optional[str] = Field(None, max_length=20)
    service_number: Optional[str] = Field(None, max_length=50)
    
    # Additional Information
    religion: Optional[str] = Field(None, max_length=30)
    additional_skills: Optional[str] = Field(None, max_length=1000)
    
    # Financial Information
    bank_name: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=20, pattern=r'^\d+$')


class ExistingOfficerDocument(BaseModel):
    """Schema for document upload metadata"""
    document_type: str = Field(
        ...,
        description="Type of document being uploaded",
        pattern="^(passport|nin_slip|ssce|birth_certificate|appointment_letter|promotion_letter|service_certificate|medical_certificate|guarantor_form|other)$"
    )
    description: Optional[str] = Field(None, max_length=200)


class ExistingOfficerResponse(BaseModel):
    """Response schema for existing officer data"""
    id: UUID
    officer_id: str
    email: EmailStr
    phone: str
    status: str
    is_verified: bool
    is_active: bool
    full_name: str
    nin_number: str
    rank: str
    position: str
    created_at: datetime
    updated_at: Optional[datetime]
    verification_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class ExistingOfficerDetailResponse(ExistingOfficerResponse):
    """Detailed response schema for existing officer"""
    gender: str
    date_of_birth: date
    place_of_birth: str
    nationality: str
    marital_status: str
    residential_address: str
    state_of_residence: str
    local_government_residence: str
    country_of_residence: str
    state_of_origin: str
    local_government_origin: str
    years_of_service: Optional[str]
    service_number: Optional[str]
    religion: Optional[str]
    additional_skills: Optional[str]
    bank_name: Optional[str]
    account_number: Optional[str]
    last_login: Optional[datetime]
    admin_notes: Optional[str]
    rejection_reason: Optional[str]
    
    # Document paths
    passport_photo: Optional[str]
    nin_slip: Optional[str]
    ssce_certificate: Optional[str]
    birth_certificate: Optional[str]
    letter_of_first_appointment: Optional[str]
    promotion_letters: Optional[str]
    service_certificate: Optional[str]
    medical_certificate: Optional[str]
    guarantor_form: Optional[str]
    other_documents: Optional[str]


class ExistingOfficerUpdate(BaseModel):
    """Schema for updating existing officer status (admin only)"""
    status: Optional[str] = Field(None, pattern='^(pending|verified|approved|rejected)$')
    is_active: Optional[bool] = None
    admin_notes: Optional[str] = Field(None, max_length=1000)
    rejection_reason: Optional[str] = Field(None, max_length=1000)


class ExistingOfficerLogin(BaseModel):
    """Schema for existing officer login"""
    officer_id: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class VerifyResponse(BaseModel):
    """Response for verification endpoint"""
    verified: bool
    message: str
    officer_data: Optional[dict] = None


class RegisterResponse(BaseModel):
    """Response for registration endpoint"""
    status: str
    message: str
    officer_id: str
    email: str
    next_steps: List[str] = Field(default_factory=list)