# app/models/__init__.py - UPDATED
from .admin import Admin
from .applicant import Applicant
from .pre_applicant import PreApplicant
from .officer import Officer
from .verification_code import VerificationCode
from .existing_officer import ExistingOfficer
from .payment import Payment
from .immediate_transfer import ImmediateTransfer  # NEW

__all__ = [
    "Admin",
    "Applicant",
    "PreApplicant",
    "Officer",
    "VerificationCode",
    "ExistingOfficer",
    "Payment",
    "ImmediateTransfer",
]