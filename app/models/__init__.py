# app/models/__init__.py
from .admin import Admin
from .applicant import Applicant
from .pre_applicant import PreApplicant
from .officer import Officer
from .verification_code import VerificationCode
from .existing_officer import ExistingOfficer  # NEW

__all__ = [
    "Admin", 
    "Applicant", 
    "PreApplicant", 
    "Officer", 
    "VerificationCode",
    "ExistingOfficer"  # NEW
]