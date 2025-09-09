# app/schemas/pre_applicant.py

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class PreApplicantCreate(BaseModel):
    full_name: str
    email: EmailStr

class PreApplicantStatusResponse(BaseModel):
    status: str
    message: str
    redirect_to: str
    email: str
    pre_applicant_id: Optional[str] = None

class PasswordValidationRequest(BaseModel):
    email: EmailStr
    password: str