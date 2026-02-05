# app/services/payment_service.py - COMPLETE UPDATED VERSION
"""
Payment service for handling Paystack integration
"""
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.config import settings

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling Paystack payments"""
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    def initiate_payment(
        self,
        email: str,
        amount: float,
        reference: str,
        metadata: Optional[Dict] = None,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize payment with Paystack
        """
        try:
            amount_kobo = int(amount * 100)  # Convert to kobo
            
            payload = {
                "email": email,
                "amount": amount_kobo,
                "reference": reference,
                "metadata": metadata or {},
                "currency": "NGN"
            }
            
            if callback_url:
                payload["callback_url"] = callback_url
            
            response = httpx.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"Payment initialized: {reference} for {email} - ₦{amount:,}")
                return {
                    "status": "success",
                    "authorization_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": reference,
                    "message": data.get("message", "Payment initialized")
                }
            else:
                error_msg = data.get("message", "Payment initialization failed")
                logger.error(f"Paystack initialization failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg
                }
                
        except httpx.RequestError as e:
            logger.error(f"Network error initializing payment: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while initializing payment"
            }
        except Exception as e:
            logger.error(f"Error initializing payment: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verify payment status with Paystack
        """
        try:
            response = httpx.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                payment_data = data["data"]
                
                return {
                    "status": payment_data["status"],
                    "reference": payment_data["reference"],
                    "amount": payment_data["amount"] / 100,  # Convert from kobo
                    "currency": payment_data["currency"],
                    "paid_at": payment_data.get("paid_at"),
                    "channel": payment_data.get("channel"),
                    "ip_address": payment_data.get("ip_address"),
                    "metadata": payment_data.get("metadata", {}),
                    "customer": {
                        "email": payment_data.get("customer", {}).get("email"),
                        "customer_code": payment_data.get("customer", {}).get("customer_code")
                    },
                    "authorization": payment_data.get("authorization"),
                    "raw_response": data
                }
            else:
                error_msg = data.get("message", "Payment verification failed")
                logger.error(f"Paystack verification failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg
                }
                
        except httpx.RequestError as e:
            logger.error(f"Network error verifying payment: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while verifying payment"
            }
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Get transaction details
        """
        try:
            response = httpx.get(
                f"{self.base_url}/transaction/{reference}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "data": data["data"]
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to get transaction")
                }
                
        except Exception as e:
            logger.error(f"Error getting transaction: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def list_transactions(
        self,
        per_page: int = 50,
        page: int = 1,
        customer: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List transactions with optional filters
        """
        try:
            params = {
                "perPage": per_page,
                "page": page
            }
            
            if customer:
                params["customer"] = customer
            if status:
                params["status"] = status
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            if amount:
                params["amount"] = amount
            
            response = httpx.get(
                f"{self.base_url}/transaction",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "transactions": data["data"],
                    "meta": data.get("meta", {})
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to list transactions")
                }
                
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def charge_authorization(
        self,
        email: str,
        amount: float,
        authorization_code: str,
        reference: str
    ) -> Dict[str, Any]:
        """
        Charge a previously authorized payment
        """
        try:
            amount_kobo = int(amount * 100)
            
            payload = {
                "email": email,
                "amount": amount_kobo,
                "authorization_code": authorization_code,
                "reference": reference
            }
            
            response = httpx.post(
                f"{self.base_url}/transaction/charge_authorization",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "data": data["data"]
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Charge authorization failed")
                }
                
        except Exception as e:
            logger.error(f"Error charging authorization: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def check_balance(self) -> Dict[str, Any]:
        """
        Check Paystack account balance
        """
        try:
            response = httpx.get(
                f"{self.base_url}/balance",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "balance": data["data"][0]["balance"] / 100,  # Convert from kobo
                    "currency": data["data"][0]["currency"]
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to check balance")
                }
                
        except Exception as e:
            logger.error(f"Error checking balance: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def create_customer(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a customer in Paystack
        """
        try:
            payload = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name
            }
            
            if phone:
                payload["phone"] = phone
            
            response = httpx.post(
                f"{self.base_url}/customer",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "customer_code": data["data"]["customer_code"],
                    "data": data["data"]
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to create customer")
                }
                
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def refund_transaction(
        self,
        reference: str,
        amount: Optional[float] = None,
        merchant_note: Optional[str] = None,
        customer_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refund a transaction
        """
        try:
            payload = {
                "transaction": reference
            }
            
            if amount:
                payload["amount"] = int(amount * 100)
            if merchant_note:
                payload["merchant_note"] = merchant_note
            if customer_note:
                payload["customer_note"] = customer_note
            
            response = httpx.post(
                f"{self.base_url}/refund",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                return {
                    "status": "success",
                    "data": data["data"]
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Refund failed")
                }
                
        except Exception as e:
            logger.error(f"Error refunding transaction: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }


def process_post_payment(user_email: str, user_type: str, payment_type: str, db):
    """
    Process post-payment actions
    This is called after successful payment verification
    """
    from app.utils.promote_applicant import promote_to_applicant
    from app.models.applicant import Applicant
    from app.models.pre_applicant import PreApplicant
    from sqlalchemy import func
    
    try:
        logger.info(f"Processing post-payment for {user_email} ({user_type}) - {payment_type}")
        
        if user_type == "pre_applicant":
            pre_applicant = db.query(PreApplicant).filter(
                func.lower(PreApplicant.email) == user_email.lower()
            ).first()
            
            if pre_applicant:
                # Update pre-applicant status
                pre_applicant.has_paid = True
                pre_applicant.status = "payment_completed"
                pre_applicant.updated_at = datetime.utcnow()
                db.commit()
                
                # Promote to applicant
                promote_to_applicant(user_email, db)
                
                logger.info(f"Pre-applicant {user_email} promoted to applicant")
        
        elif user_type == "applicant":
            applicant = db.query(Applicant).filter(
                func.lower(Applicant.email) == user_email.lower()
            ).first()
            
            if applicant:
                applicant.payment_status = "paid"
                applicant.payment_type = payment_type
                applicant.paid_at = datetime.utcnow()
                applicant.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Applicant {user_email} payment marked as paid")
        
        elif user_type == "existing_officer":
            logger.info(f"Existing officer {user_email} registration completed")
        
        logger.info(f"Post-payment processing completed for {user_email}")
        
    except Exception as e:
        logger.error(f"Error in post-payment processing: {str(e)}", exc_info=True)
        raise