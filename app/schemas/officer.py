from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from uuid import UUID

# Add these missing models
class OfficerSignup(BaseModel):
    unique_id: str
    email: EmailStr
    phone: str
    password: str

    class Config:
        title = "OfficerSignup"

class OfficerLogin(BaseModel):
    unique_id: str
    password: str

    class Config:
        title = "OfficerLogin"

class OfficerSignupResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]
    next_steps: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Officer registered successfully",
                "data": {"officer_id": "123e4567-e89b-12d3-a456-426614174000"},
                "next_steps": "verify_email"
            }
        }

class VerifyOTPResponse(BaseModel):  # Add this new response model
    status: str
    message: str
    data: Dict[str, Any]
    next_steps: Optional[str] = None  # Make next_steps optional for OTP verification

class OfficerResponse(BaseModel):
    id: UUID
    unique_id: str
    email: EmailStr
    phone: str
    is_active: bool
    role: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    passport: Optional[str] = None
    rank: Optional[str] = None
    position: Optional[str] = None
    applicant_id: UUID
    
    # Personal Information
    full_name: Optional[str] = None
    nin_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    residential_address: Optional[str] = None
    state_of_residence: Optional[str] = None
    local_government_residence: Optional[str] = None
    additional_skills: Optional[str] = None
    
    # Additional Fields
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    state_of_origin: Optional[str] = None
    local_government_origin: Optional[str] = None
    religion: Optional[str] = None
    place_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    category: Optional[str] = None
    other_name: Optional[str] = None
    do_you_smoke: Optional[bool] = None

    class Config:
        from_attributes = True

class OfficerProfile(OfficerResponse):
    applicant_data: Optional[dict] = None

class OfficerUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    full_name: Optional[str] = None
    nin_number: Optional[str] = None
    gender: Optional[str] = None
    rank: Optional[str] = None
    position: Optional[str] = None
    residential_address: Optional[str] = None
    state_of_residence: Optional[str] = None
    local_government_residence: Optional[str] = None
    additional_skills: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    do_you_smoke: Optional[bool] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str