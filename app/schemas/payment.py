# app/schemas/payment.py - UPDATED FIXED VERSION
from pydantic import BaseModel, EmailStr, Field
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
    payment_type: str = Field(..., description="Type of payment: regular, vip, or existing_officer")  # Changed from PaymentType to str
    user_type: str = Field(..., description="Type of user making payment")  # Changed from UserType to str
    amount: Optional[int] = Field(None, description="Amount in Naira (auto-calculated based on type)")

    class Config:
        json_encoders = {
            Enum: lambda v: v.value  # Ensures enum values are serialized as strings
        }

class PaymentVerify(BaseModel):
    reference: str = Field(..., description="Payment reference from gateway")

class PaymentCallback(BaseModel):
    email: EmailStr
    reference: str
    status: str
    amount: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

# New schemas for immediate transfers
class ImmediateTransferRequest(BaseModel):
    payment_reference: str
    recipient_type: str = Field(..., description="director_general or estech_system")
    amount: float

class RetryTransferRequest(BaseModel):
    payment_reference: str

# For backward compatibility
class ManualPaymentRequest(BaseModel):
    email: EmailStr

class GatewayCallback(BaseModel):
    email: EmailStr
    reference: str = Field(..., min_length=10, max_length=100)