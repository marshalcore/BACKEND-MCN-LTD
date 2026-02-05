# app/models/immediate_transfer.py - COMPLETE
"""
Database model to track immediate transfers to DG and eSTech System
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.sql import func
from app.database import Base
import uuid

class ImmediateTransfer(Base):
    __tablename__ = "immediate_transfers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Link to payment
    payment_reference = Column(String, index=True, nullable=False)
    
    # Recipient details
    recipient_type = Column(String, nullable=False)  # "director_general" or "estech_system"
    recipient_account = Column(String, nullable=False)  # "Name - Account Number"
    recipient_bank = Column(String, nullable=False)  # "UBA" or "OPay"
    
    # Transfer details
    amount = Column(Float, nullable=False)  # Amount in Naira
    transfer_reference = Column(String, index=True, nullable=True)  # Paystack transfer reference
    status = Column(String, default="pending")  # pending, initiated, success, failed, retried
    
    # Paystack response data
    paystack_response = Column(JSON, nullable=True)
    paystack_transfer_code = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    transferred_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Retry information
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<ImmediateTransfer {self.transfer_reference or self.id}: ₦{self.amount:,} to {self.recipient_type}>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "payment_reference": self.payment_reference,
            "recipient_type": self.recipient_type,
            "recipient_account": self.recipient_account,
            "recipient_bank": self.recipient_bank,
            "amount": self.amount,
            "amount_display": f"₦{self.amount:,}",
            "transfer_reference": self.transfer_reference,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "transferred_at": self.transferred_at.isoformat() if self.transferred_at else None,
            "retry_count": self.retry_count,
            "paystack_transfer_code": self.paystack_transfer_code
        }