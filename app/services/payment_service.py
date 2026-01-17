# app/services/payment_service.py
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.config import settings
from app.models.payment import Payment
from app.models.applicant import Applicant
from app.models.pre_applicant import PreApplicant
from app.models.officer import Officer
from app.services.email_service import send_confirmation_email, send_payment_receipt_email
from sqlalchemy import func
import json

logger = logging.getLogger(__name__)

class PaymentService:
    """Payment service with eSTech System commission tracking"""
    
    def __init__(self):
        self.paystack_secret_key = settings.PAYSTACK_SECRET_KEY
        self.paystack_public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.paystack_secret_key}",
            "Content-Type": "application/json"
        }
    
    def initiate_payment(
        self,
        email: str,
        amount: int,
        reference: str,
        metadata: Dict[str, Any],
        callback_url: str
    ) -> Dict[str, Any]:
        """
        Initialize payment with Paystack
        Note: Split payments are tracked internally, not via Paystack subaccounts
        """
        try:
            # Convert amount to kobo
            amount_kobo = amount * 100
            
            payment_data = {
                "email": email,
                "amount": amount_kobo,
                "reference": reference,
                "metadata": metadata,  # Internal tracking data
                "callback_url": callback_url,
                "channels": ["card", "bank", "ussd", "qr", "mobile_money"],
                "currency": "NGN",
                "bearer": "account"
            }
            
            # For TEST environment, you can use test cards
            if settings.ENVIRONMENT == "testing":
                payment_data["metadata"]["test_mode"] = True
            
            response = httpx.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=payment_data,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data["status"]:
                logger.info(f"Payment initialized: {reference} for {email}")
                
                return {
                    "authorization_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": reference,
                    "status": "pending",
                    "message": data.get("message", "")
                }
            else:
                error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except httpx.RequestError as e:
            logger.error(f"Network error initiating payment: {str(e)}")
            raise Exception(f"Payment service unavailable")
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            raise
    
    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify payment with Paystack"""
        try:
            response = httpx.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data["status"] and data["data"]["status"] == "success":
                # Convert amount from kobo to Naira
                amount = data["data"]["amount"] / 100
                
                logger.info(f"Payment verified successfully: {reference}")
                
                return {
                    "status": "success",
                    "amount": amount,
                    "currency": data["data"]["currency"],
                    "paid_at": data["data"]["paid_at"],
                    "channel": data["data"]["channel"],
                    "reference": reference,
                    "gateway_response": data["data"]["gateway_response"],
                    "customer": data["data"]["customer"],
                    "metadata": data["data"]["metadata"]
                }
            else:
                logger.warning(f"Payment verification failed: {reference}")
                return {
                    "status": "failed",
                    "message": data["data"].get("gateway_response", "Payment failed"),
                    "reference": reference
                }
                
        except httpx.RequestError as e:
            logger.error(f"Network error verifying payment: {str(e)}")
            return {
                "status": "error",
                "message": "Verification service unavailable"
            }
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def create_transfer_recipient(
        self,
        account_number: str,
        bank_code: str,
        account_name: str = "eSTech System",
        type: str = "nuban"
    ) -> Dict[str, Any]:
        """Create transfer recipient for eSTech System payouts"""
        try:
            data = {
                "type": type,
                "name": account_name,
                "account_number": account_number,
                "bank_code": bank_code,
                "currency": "NGN"
            }
            
            response = httpx.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result["status"]:
                logger.info(f"Recipient created for eSTech System: {account_number}")
                return {
                    "status": "success",
                    "recipient_code": result["data"]["recipient_code"],
                    "account_name": result["data"]["name"],
                    "account_number": result["data"]["details"]["account_number"],
                    "bank": result["data"]["details"]["bank_name"]
                }
            else:
                logger.error(f"Recipient creation failed: {result.get('message')}")
                return {
                    "status": "error",
                    "message": result.get("message", "Recipient creation failed")
                }
                
        except Exception as e:
            logger.error(f"Error creating recipient: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def initiate_transfer(
        self,
        recipient_code: str,
        amount: int,  # in kobo
        reason: str = "Monthly Commission - Technical Support Services"
    ) -> Dict[str, Any]:
        """Initiate transfer to eSTech System"""
        try:
            data = {
                "source": "balance",
                "amount": amount,
                "recipient": recipient_code,
                "reason": reason,
                "currency": "NGN"
            }
            
            response = httpx.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result["status"]:
                logger.info(f"Transfer initiated: ₦{amount/100:,.2f} to eSTech System")
                return {
                    "status": "success",
                    "transfer_code": result["data"]["transfer_code"],
                    "reference": result["data"]["reference"],
                    "amount": amount / 100,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Transfer failed: {result.get('message')}")
                return {
                    "status": "error",
                    "message": result.get("message", "Transfer failed")
                }
                
        except Exception as e:
            logger.error(f"Error initiating transfer: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

async def process_post_payment(
    user_email: str,
    user_type: str,
    payment_type: str,
    db: Session
):
    """Background task after successful payment"""
    try:
        # Find the payment
        payment = db.query(Payment).filter(
            func.lower(Payment.user_email) == user_email.lower(),
            Payment.user_type == user_type,
            Payment.payment_type == payment_type,
            Payment.status == "success"
        ).order_by(Payment.paid_at.desc()).first()
        
        if not payment:
            logger.error(f"Payment not found for {user_email}")
            return
        
        # Get user details
        user = None
        user_name = ""
        
        if user_type == "applicant":
            user = db.query(Applicant).filter(
                func.lower(Applicant.email) == user_email.lower()
            ).first()
            if user:
                user_name = user.full_name
        elif user_type == "pre_applicant":
            user = db.query(PreApplicant).filter(
                func.lower(PreApplicant.email) == user_email.lower()
            ).first()
            if user:
                user_name = user.full_name
        elif user_type in ["officer", "existing_officer"]:
            # Handle officer types
            from app.models.officer import Officer
            from app.models.existing_officer import ExistingOfficer
            
            if user_type == "officer":
                user = db.query(Officer).filter(
                    func.lower(Officer.email) == user_email.lower()
                ).first()
            else:
                user = db.query(ExistingOfficer).filter(
                    func.lower(ExistingOfficer.email) == user_email.lower()
                ).first()
            
            if user:
                user_name = user.full_name
        
        # Send confirmation email to user
        if user_email and user_name:
            try:
                # Simple confirmation email (NO split details)
                await send_confirmation_email(
                    to_email=user_email,
                    name=user_name,
                    amount=payment.amount,
                    reference=payment.payment_reference,
                    payment_type=payment.payment_type
                )
                logger.info(f"Confirmation email sent to {user_email}")
                
                # Internal logging of split payment (NOT sent to user)
                logger.info(
                    f"PAYMENT SPLIT LOGGED - {user_email}: "
                    f"Total: ₦{payment.amount:,}, "
                    f"eSTech System: ₦{payment.estech_share:,} (15%), "
                    f"Marshal Core: ₦{payment.marshal_share:,} (85%)"
                )
                
            except Exception as email_error:
                logger.error(f"Failed to send email to {user_email}: {str(email_error)}")
        
    except Exception as e:
        logger.error(f"Error in post-payment processing: {str(e)}", exc_info=True)

def verify_paystack_payment(reference: str) -> bool:
    """Verify Paystack payment reference (legacy support)"""
    try:
        service = PaymentService()
        result = service.verify_payment(reference)
        return result.get("status") == "success"
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return False

def verify_flutterwave_payment(reference: str) -> bool:
    """Verify Flutterwave payment reference (legacy support)"""
    if not settings.FLUTTERWAVE_SECRET_KEY:
        logger.error("Flutterwave secret key not configured")
        return False
    
    headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}
    url = f"https://api.flutterwave.com/v3/transactions/{reference}/verify"
    
    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        
        data = response.json().get("data", {})
        return data.get("status") == "successful"
        
    except Exception as e:
        logger.error(f"Flutterwave verification error: {str(e)}")
        return False

async def process_payment_success(email: str, db: Session):
    """Legacy function for backward compatibility"""
    from app.utils.password import generate_password
    from app.services.email_service import send_application_password_email
    from datetime import datetime, timedelta
    
    try:
        normalized_email = email.strip().lower()
        
        # Find pre-applicant
        pre_applicant = db.query(PreApplicant).filter(
            func.lower(PreApplicant.email) == normalized_email
        ).first()
        
        if not pre_applicant:
            raise HTTPException(status_code=404, detail="User not found")
        
        if pre_applicant.has_paid:
            return {"message": "Already paid."}
        
        # Mark as paid
        pre_applicant.has_paid = True
        pre_applicant.status = "payment_completed"
        
        # Generate password if needed
        needs_new_password = True
        if pre_applicant.application_password:
            if (pre_applicant.password_expires_at and 
                pre_applicant.password_expires_at > datetime.utcnow()):
                needs_new_password = False
        
        if needs_new_password:
            password = generate_password()
            pre_applicant.application_password = password
            pre_applicant.password_generated = True
            pre_applicant.password_generated_at = datetime.utcnow()
            pre_applicant.password_expires_at = datetime.utcnow() + timedelta(hours=24)
            pre_applicant.status = "password_sent"
            
            # Send password email
            await send_application_password_email(
                email, 
                pre_applicant.full_name, 
                password
            )
        
        db.commit()
        logger.info(f"Legacy payment processed for {email}")
        
        return {"message": "Payment verified successfully."}
        
    except Exception as e:
        logger.error(f"Error processing legacy payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Payment processing failed")