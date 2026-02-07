# app/schemas/pre_applicant.py - COMPLETE FIXED VERSION
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class PreApplicantCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr

    model_config = ConfigDict(title="PreApplicantCreate")


class PreApplicantStatusResponse(BaseModel):
    status: str
    message: str
    redirect_to: str
    email: str
    pre_applicant_id: Optional[str] = None

    model_config = ConfigDict(title="PreApplicantStatusResponse")


class PasswordValidationRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

    model_config = ConfigDict(title="PasswordValidationRequest")


class PreApplicantResponse(BaseModel):
    full_name: str
    email: EmailStr
    has_paid: bool
    selected_tier: Optional[str] = None
    tier_selected_at: Optional[datetime] = None
    privacy_accepted: bool
    status: str
    created_at: datetime
    application_password: Optional[str] = None
    password_expires_at: Optional[datetime] = None
    application_submitted: Optional[bool] = None
    submitted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True, title="PreApplicantResponse")


class PreApplicantSimpleResponse(BaseModel):
    """Simplified response for status checks"""
    full_name: str
    email: EmailStr
    has_paid: bool
    status: str
    can_proceed_to_payment: bool = True
    
    model_config = ConfigDict(title="PreApplicantSimpleResponse")