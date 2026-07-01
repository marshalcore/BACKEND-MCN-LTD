# app/schemas/immediate_transfer.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TransferRecipientType(str, Enum):
    MARSHAL_CORE_SHARE = "marshal_core_share"  # MarshalCoreShare - 50%
    SYSTEMS_MAINTAINANCE = "systems_maintainance"  # SystemsMaintainance - 35%
    ESTECH_DIGITAL_SYSTEMS_LIMITED = "estech_digital_systems_limited"  # eSTechDigitalSystemsLimited - 15%

class TransferStatus(str, Enum):
    PENDING = "pending"
    INITIATED = "initiated"
    SUCCESS = "success"
    FAILED = "failed"
    RETRIED = "retried"

class ImmediateTransferBase(BaseModel):
    payment_reference: str = Field(..., description="Payment reference for which transfer was made")
    recipient_type: TransferRecipientType = Field(..., description="Type of recipient")
    amount: float = Field(..., description="Transfer amount in Naira")
    recipient_account: str = Field(..., description="Recipient account details")
    recipient_bank: str = Field(..., description="Recipient bank name")

class ImmediateTransferCreate(ImmediateTransferBase):
    transfer_reference: Optional[str] = Field(None, description="Paystack transfer reference")
    status: TransferStatus = Field(default=TransferStatus.PENDING, description="Transfer status")
    paystack_response: Optional[Dict[str, Any]] = Field(None, description="Paystack API response")
    paystack_transfer_code: Optional[str] = Field(None, description="Paystack transfer code")

class ImmediateTransferUpdate(BaseModel):
    status: Optional[TransferStatus] = None
    transfer_reference: Optional[str] = None
    paystack_response: Optional[Dict[str, Any]] = None
    paystack_transfer_code: Optional[str] = None
    retry_count: Optional[int] = None

class ImmediateTransferResponse(ImmediateTransferBase):
    id: str
    transfer_reference: Optional[str] = None
    status: TransferStatus
    created_at: datetime
    transferred_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    retry_count: int = 0
    paystack_transfer_code: Optional[str] = None

    class Config:
        from_attributes = True

class TransferRecipient(BaseModel):
    account_name: str
    account_number: str
    bank: str
    bank_code: str
    description: str

class ImmediateTransferConfig(BaseModel):
    marshal_core_share: TransferRecipient  # MarshalCoreShare - 50%
    systems_maintainance: TransferRecipient  # SystemsMaintainance - 35%
    estech_digital_systems_limited: TransferRecipient  # eSTechDigitalSystemsLimited - 15%

class PaymentSplitConfig(BaseModel):
    user_amount: int
    base_amount: int
    native_split_enabled: bool
    
    marshal_core_share: Dict[str, Any]  # MarshalCoreShare - 50%
    systems_maintainance: Dict[str, Any]  # SystemsMaintainance - 35%
    estech_digital_systems_limited: Dict[str, Any]  # eSTechDigitalSystemsLimited - 15%
    
    user_message: str
    receipt_description: str
    category: str

class ProcessImmediateSplitsRequest(BaseModel):
    payment_reference: str
    payment_amount: float

class RetryTransferRequest(BaseModel):
    payment_reference: str

class TransferHistoryFilters(BaseModel):
    status: Optional[TransferStatus] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    recipient_type: Optional[TransferRecipientType] = None

class TransferSummary(BaseModel):
    total_transfers: int
    total_amount: str
    marshal_core_share_total: str  # MarshalCoreShare - 50%
    systems_maintainance_total: str  # SystemsMaintainance - 35%
    estech_digital_systems_limited_total: str  # eSTechDigitalSystemsLimited - 15%

class TransferHistoryResponse(BaseModel):
    status: str
    transfers: list[ImmediateTransferResponse]
    summary: TransferSummary
    transfer_accounts: ImmediateTransferConfig