# app/models/payment.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, index=True, nullable=False)
    user_type = Column(String, nullable=False)  # applicant, pre_applicant, officer, existing_officer
    amount = Column(Integer, nullable=False)  # in Naira
    payment_type = Column(String, nullable=False)  # regular, vip, existing_officer
    status = Column(String, default="pending")  # pending, success, failed, cancelled
    payment_reference = Column(String, unique=True, index=True, nullable=False)
    authorization_url = Column(Text, nullable=True)
    access_code = Column(String, nullable=True)
    
    # Split payment tracking (INTERNAL USE ONLY)
    estech_share = Column(Integer, default=0)  # in Naira (15% commission)
    marshal_share = Column(Integer, default=0)  # in Naira (85% share)
    
    # eSTech System payout tracking
    estech_paid_out = Column(Boolean, default=False)
    estech_payout_date = Column(DateTime(timezone=True), nullable=True)
    estech_payout_reference = Column(String, nullable=True)
    
    # Payment metadata (CHANGED from 'metadata' to avoid conflict)
    payment_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata'
    verification_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Payment {self.payment_reference}: {self.user_email} - ₦{self.amount}>"
    
    def to_dict(self, include_internal=False):
        """Convert to dictionary, optionally including internal split details"""
        data = {
            "id": self.id,
            "user_email": self.user_email,
            "user_type": self.user_type,
            "amount": self.amount,
            "amount_display": f"₦{self.amount:,}",
            "payment_type": self.payment_type,
            "status": self.status,
            "payment_reference": self.payment_reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None
        }
        
        if include_internal:
            # Only include split details for admin/internal use
            data.update({
                "estech_share": self.estech_share,
                "estech_share_display": f"₦{self.estech_share:,}",
                "marshal_share": self.marshal_share,
                "marshal_share_display": f"₦{self.marshal_share:,}",
                "estech_paid_out": self.estech_paid_out,
                "estech_payout_date": self.estech_payout_date.isoformat() if self.estech_payout_date else None,
                "estech_payout_reference": self.estech_payout_reference
            })
        
        return data