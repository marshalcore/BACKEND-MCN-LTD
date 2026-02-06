from pydantic import BaseModel, EmailStr
from typing import Optional

class EmailCheckRequest(BaseModel):
    email: EmailStr

class EmailCheckResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None

class SendVerificationRequest(BaseModel):
    email: EmailStr

class SendVerificationResponse(BaseModel):
    sent: bool
    expires_in_minutes: int

class ConfirmVerificationRequest(BaseModel):
    email: EmailStr
    code: str

class ConfirmVerificationResponse(BaseModel):
    verified: bool