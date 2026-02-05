# app/schemas/__init__.py - UPDATED
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
from .payment import (
    ManualPaymentRequest, 
    GatewayCallback,
    PaymentCreate,
    PaymentVerify,
    PaymentCallback,
    PaymentType,
    UserType
)
from .pre_applicant import (
    PreApplicantCreate,
    PreApplicantStatusResponse,
    PasswordValidationRequest
)
from .immediate_transfer import (
    TransferRecipientType,
    TransferStatus,
    ImmediateTransferBase,
    ImmediateTransferCreate,
    ImmediateTransferUpdate,
    ImmediateTransferResponse,
    TransferRecipient,
    ImmediateTransferConfig,
    PaymentSplitConfig,
    ProcessImmediateSplitsRequest,
    RetryTransferRequest,
    TransferHistoryFilters,
    TransferSummary,
    TransferHistoryResponse
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
    "PaymentCreate",
    "PaymentVerify",
    "PaymentCallback",
    "PaymentType",
    "UserType",
    "PreApplicantCreate",
    "PreApplicantStatusResponse",
    "PasswordValidationRequest",
    # Immediate Transfer Schemas
    "TransferRecipientType",
    "TransferStatus",
    "ImmediateTransferBase",
    "ImmediateTransferCreate",
    "ImmediateTransferUpdate",
    "ImmediateTransferResponse",
    "TransferRecipient",
    "ImmediateTransferConfig",
    "PaymentSplitConfig",
    "ProcessImmediateSplitsRequest",
    "RetryTransferRequest",
    "TransferHistoryFilters",
    "TransferSummary",
    "TransferHistoryResponse"
]