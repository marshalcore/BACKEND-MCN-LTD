from pydantic import BaseModel, EmailStr, Field


class ManualPaymentRequest(BaseModel):
    email: EmailStr


class GatewayCallback(BaseModel):
    email: EmailStr
    reference: str = Field(..., min_length=10, max_length=100)