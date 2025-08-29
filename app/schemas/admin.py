# app/schemas/admin.py
from pydantic import BaseModel, EmailStr, validator
from typing import Optional

class AdminSignup(BaseModel):
    full_name: str
    email: EmailStr
    password: str

    class Config:
        title = "AdminSignup"

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

    class Config:
        title = "AdminLogin"

class AdminResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    is_superuser: bool
    is_verified: bool
    is_active: bool

    @validator('is_verified', 'is_active', 'is_superuser', pre=True)
    def convert_none_to_false(cls, v):
        return v if v is not None else False

    class Config:
        title = "AdminResponse"
        from_attributes = True

class AdminUpdateUser(BaseModel):
    email: Optional[EmailStr]
    phone: Optional[str]
    unique_id: Optional[str]
    rank: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool]

    class Config:
        title = "AdminUpdateUser"

class ResetUserPassword(BaseModel):
    new_password: str

    class Config:
        title = "ResetUserPassword"

class OTPVerifyRequest(BaseModel):
    email: str
    code: str
    purpose: str

    class Config:
        title = "OTPVerifyRequest"