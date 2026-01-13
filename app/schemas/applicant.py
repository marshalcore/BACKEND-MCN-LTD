# app/schemas/applicant.py
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import date, datetime
from typing import Optional


class ApplicantBase(BaseModel):
    # SECTION A: Personal Information
    category: str
    marital_status: str
    nin_number: str
    full_name: str
    first_name: str
    surname: str
    other_name: Optional[str] = None
    email: EmailStr
    mobile_number: str
    phone_number: str
    gender: str
    nationality: str
    country_of_residence: str
    state_of_origin: str
    state_of_residence: str
    residential_address: str
    local_government_residence: str
    local_government_origin: str
    date_of_birth: date
    religion: str
    place_of_birth: str

    # SECTION B: Documents
    passport_photo: str
    nin_slip: str
    ssce_certificate: str
    higher_education_degree: Optional[str] = None

    # SECTION C: Additional Information
    do_you_smoke: bool
    agree_to_join: bool
    agree_to_abide_rules: bool
    agree_to_return_properties: bool
    additional_skills: Optional[str] = None
    design_rating: Optional[int] = None

    # SECTION D: Financial Information
    bank_name: str
    account_number: str

    model_config = ConfigDict(from_attributes=True, title="ApplicantBase")


class ApplicantResponse(ApplicantBase):
    # SECTION E: Meta Information
    id: UUID
    unique_id: Optional[str] = None
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
