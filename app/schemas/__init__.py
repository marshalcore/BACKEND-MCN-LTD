# app/schemas/__init__.py
from .officer import (
    OfficerSignup,
    OfficerLogin,
    OfficerSignupResponse,
    VerifyOTPResponse,
    OfficerResponse,
    OfficerProfile,
    OfficerUpdate,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from .payment import ManualPaymentRequest, GatewayCallback
from .pre_applicant import (
    PreApplicantCreate,
    PreApplicantStatusResponse,
    PasswordValidationRequest
)

__all__ = [
    "OfficerSignup",
    "OfficerLogin",
    "OfficerSignupResponse",
    "VerifyOTPResponse",
    "OfficerResponse",
    "OfficerProfile",
    "OfficerUpdate",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "ManualPaymentRequest",
    "GatewayCallback",
    "PreApplicantCreate",
    "PreApplicantStatusResponse",
    "PasswordValidationRequest"
]