from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import Optional, List


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
    is_verified: bool
    has_paid: bool
    application_password: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = ConfigDict(title="ApplicantResponse")


class ApplicantUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    unique_id: Optional[str] = None   # <-- editable official ID
    is_verified: Optional[bool] = None

    class Config:
        title = "ApplicantUpdate"


class ApplicantCreate(BaseModel):
    # Basic Information
    phone_number: str
    nin_number: str
    date_of_birth: date
    state_of_residence: str
    lga: str
    address: str
    
    # Application Details
    selected_reasons: List[str]
    additional_details: Optional[str] = None
    application_tier: str
    
    # Password for verification
    application_password: str
    
    class Config:
        title = "ApplicantCreate"