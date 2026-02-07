# app/schemas/payment.py - COMPLETE FIXED VERSION
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any
from enum import Enum


class PaymentType(str, Enum):
    REGULAR = "regular"
    VIP = "vip"
    EXISTING_OFFICER = "existing_officer"


class UserType(str, Enum):
    APPLICANT = "applicant"
    PRE_APPLICANT = "pre_applicant"
    OFFICER = "officer"
    EXISTING_OFFICER = "existing_officer"


class PaymentCreate(BaseModel):
    email: EmailStr
    payment_type: PaymentType = Field(..., description="Type of payment: regular, vip, or existing_officer")
    user_type: UserType = Field(..., description="Type of user making payment")
    amount: Optional[int] = Field(None, description="Amount in Naira (auto-calculated based on type)")

    model_config = ConfigDict(use_enum_values=True)


class PaymentVerify(BaseModel):
    reference: str = Field(..., description="Payment reference from gateway")

    model_config = ConfigDict(title="PaymentVerify")


class PaymentCallback(BaseModel):
    email: EmailStr
    reference: str
    status: str
    amount: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(title="PaymentCallback")


# New schemas for immediate transfers
class ImmediateTransferRequest(BaseModel):
    payment_reference: str
    recipient_type: str = Field(..., description="director_general or estech_system")
    amount: float

    model_config = ConfigDict(title="ImmediateTransferRequest")


class RetryTransferRequest(BaseModel):
    payment_reference: str

    model_config = ConfigDict(title="RetryTransferRequest")


# For backward compatibility
class ManualPaymentRequest(BaseModel):
    email: EmailStr

    model_config = ConfigDict(title="ManualPaymentRequest")


class GatewayCallback(BaseModel):
    email: EmailStr
    reference: str = Field(..., min_length=10, max_length=100)

    model_config = ConfigDict(title="GatewayCallback")