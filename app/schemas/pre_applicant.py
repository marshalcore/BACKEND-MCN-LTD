from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class PreApplicantCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr


class PreApplicantStatusResponse(BaseModel):
    status: str
    message: str
    redirect_to: str
    email: str
    pre_applicant_id: Optional[str] = None


class PasswordValidationRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class PreApplicantResponse(BaseModel):
    full_name: str
    email: EmailStr
    has_paid: bool
    selected_tier: Optional[str] = None
    tier_selected_at: Optional[datetime] = None
    privacy_accepted: bool
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True