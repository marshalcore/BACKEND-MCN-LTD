# app/schemas/pre_applicant.py

from pydantic import BaseModel, EmailStr

class PreApplicantCreate(BaseModel):
    full_name: str
    email: EmailStr
