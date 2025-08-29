from pydantic import BaseModel, EmailStr

class ManualPaymentRequest(BaseModel):
    email: EmailStr

class GatewayCallback(BaseModel):
    email: EmailStr
    reference: str
