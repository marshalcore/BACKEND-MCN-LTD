# app/schemas/payment.py
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
    payment_type: PaymentType = Field(..., description="Type of payment: regular, vip, or existing_officer")
    user_type: UserType = Field(..., description="Type of user making payment")
    amount: Optional[int] = Field(None, description="Amount in Naira (auto-calculated based on type)")

class PaymentVerify(BaseModel):
    reference: str = Field(..., description="Payment reference from gateway")

class PaymentCallback(BaseModel):
    email: EmailStr
    reference: str
    status: str
    amount: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

# For backward compatibility
class ManualPaymentRequest(BaseModel):
    email: EmailStr

class GatewayCallback(BaseModel):
    email: EmailStr
    reference: str = Field(..., min_length=10, max_length=100)