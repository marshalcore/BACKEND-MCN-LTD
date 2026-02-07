# app/models/payment.py - COMPLETE UPDATED VERSION
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Payment(Base):
    __tablename__ = "payments"
    
    # FIXED: Ensure consistent String type (not mixing UUID and String)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, index=True, nullable=False)
    user_type = Column(String, nullable=False)  # applicant, pre_applicant, officer, existing_officer
    amount = Column(Integer, nullable=False)  # in Naira (what user paid)
    payment_type = Column(String, nullable=False)  # regular, vip, existing_officer
    status = Column(String, default="pending")  # pending, success, failed, cancelled
    payment_reference = Column(String, unique=True, index=True, nullable=False)
    authorization_url = Column(Text, nullable=True)
    access_code = Column(String, nullable=True)
    
    # NEW: Immediate transfer tracking
    immediate_transfers_processed = Column(Boolean, default=False)
    transfer_metadata = Column(JSONB, nullable=True)  # Changed from JSON to JSONB
    
    # NEW: Split amounts for immediate transfers
    director_general_share = Column(Integer, default=0)  # 35% in Naira
    estech_system_share = Column(Integer, default=0)  # 15% in Naira
    marshal_net_amount = Column(Float, nullable=True)  # Estimated net after fees
    
    # OLD: Keep for backward compatibility (rename estech_share to estech_commission for clarity)
    estech_commission = Column(Integer, default=0)  # Renamed from estech_share
    marshal_share = Column(Integer, default=0)  # Keep for existing code
    
    # OLD: eSTech System payout tracking (now replaced by immediate transfers)
    estech_paid_out = Column(Boolean, default=False)
    estech_payout_date = Column(DateTime(timezone=True), nullable=True)
    estech_payout_reference = Column(String, nullable=True)
    
    # Payment metadata
    payment_metadata = Column(JSONB, nullable=True)  # Changed from JSON to JSONB
    verification_data = Column(JSONB, nullable=True)  # Changed from JSON to JSONB
    
    # FIXED: updated_at should have server_default too
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
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
            "immediate_transfers_processed": self.immediate_transfers_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None
        }
        
        if include_internal:
            # Include split details for admin/internal use
            data.update({
                "director_general_share": self.director_general_share,
                "director_general_share_display": f"₦{self.director_general_share:,}",
                "estech_system_share": self.estech_system_share,
                "estech_system_share_display": f"₦{self.estech_system_share:,}",
                "marshal_net_amount": self.marshal_net_amount,
                "marshal_net_amount_display": f"₦{self.marshal_net_amount:,}" if self.marshal_net_amount else None,
                "estech_commission": self.estech_commission,
                "marshal_share": self.marshal_share,
                "transfer_metadata": self.transfer_metadata,
                "payment_metadata": self.payment_metadata,
                "verification_data": self.verification_data
            })
        
        return data