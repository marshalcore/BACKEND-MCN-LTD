# app/schemas/payment.py - COMPLETE FIXED VERSION
from pydantic import BaseModel, EmailStr, Field, ConfigDict, validator
from typing import Optional, Dict, Any, Union
from datetime import datetime
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


# NEW: Payment response schema that matches your model
class PaymentResponse(BaseModel):
    id: str
    user_email: EmailStr
    user_type: str
    amount: int
    payment_type: str
    status: str
    payment_reference: str
    immediate_transfers_processed: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    
    # Optional fields (include only when needed)
    authorization_url: Optional[str] = None
    access_code: Optional[str] = None
    director_general_share: Optional[int] = None
    estech_system_share: Optional[int] = None
    marshal_net_amount: Optional[float] = None
    estech_commission: Optional[int] = None
    marshal_share: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True, title="PaymentResponse")


# NEW: Payment update schema
class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    immediate_transfers_processed: Optional[bool] = None
    director_general_share: Optional[int] = None
    estech_system_share: Optional[int] = None
    marshal_net_amount: Optional[float] = None
    transfer_metadata: Optional[Dict[str, Any]] = None
    payment_metadata: Optional[Dict[str, Any]] = None
    verification_data: Optional[Dict[str, Any]] = None
    paid_at: Optional[datetime] = None

    model_config = ConfigDict(title="PaymentUpdate")