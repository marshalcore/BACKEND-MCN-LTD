# app/services/payment_service.py - PRODUCTION LIVE MODE OPTIMIZED
"""
Payment service for handling Paystack integration with LIVE keys
PRODUCTION LIVE MODE - REAL MONEY ONLY
"""
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.config import settings

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling Paystack payments with LIVE keys - PRODUCTION ONLY"""
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        self.is_live_mode = True  # Force LIVE mode for production
        
        logger.info("💰 PaymentService initialized: PRODUCTION LIVE MODE")
        logger.info(f"💰 Public Key: {self.public_key[:15]}...")
        logger.info("💰 REAL MONEY TRANSACTIONS ONLY")
    
    def initiate_payment(
        self,
        email: str,
        amount: float,
        reference: str,
        metadata: Optional[Dict] = None,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize payment with Paystack LIVE - PRODUCTION
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
            
            logger.info(f"💰 INITIATING LIVE PAYMENT: {reference} - ₦{amount:,}")
            logger.info(f"💰 Callback URL: {callback_url}")
            
            response = httpx.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅✅✅ LIVE PAYMENT INITIALIZED: {reference} for {email} - ₦{amount:,}")
                logger.info(f"💰 Authorization URL: {data['data']['authorization_url'][:50]}...")
                
                return {
                    "status": "success",
                    "authorization_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": reference,
                    "message": data.get("message", "Payment initialized"),
                    "mode": "LIVE"
                }
            else:
                error_msg = data.get("message", "Payment initialization failed")
                logger.error(f"❌❌❌ LIVE Paystack initialization failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "mode": "LIVE"
                }
                
        except httpx.RequestError as e:
            logger.error(f"❌❌❌ Network error initializing LIVE payment: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while initializing payment",
                "mode": "LIVE"
            }
        except Exception as e:
            logger.error(f"❌❌❌ Error initializing LIVE payment: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verify payment status with Paystack LIVE - PRODUCTION
        """
        try:
            logger.info(f"💰 VERIFYING LIVE PAYMENT: {reference}")
            
            response = httpx.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                payment_data = data["data"]
                
                if payment_data["status"] == "success":
                    logger.info(f"✅✅✅ LIVE PAYMENT VERIFIED SUCCESS: {reference} - ₦{payment_data['amount']/100:,}")
                    
                    return {
                        "status": "success",
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
                        "raw_response": data,
                        "mode": "LIVE"
                    }
                else:
                    logger.warning(f"⚠️ Payment {reference} status: {payment_data['status']}")
                    return {
                        "status": payment_data["status"],
                        "reference": reference,
                        "amount": payment_data["amount"] / 100,
                        "message": f"Payment status: {payment_data['status']}",
                        "mode": "LIVE"
                    }
            else:
                error_msg = data.get("message", "Payment verification failed")
                logger.error(f"❌❌❌ LIVE Paystack verification failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "mode": "LIVE"
                }
                
        except httpx.RequestError as e:
            logger.error(f"❌❌❌ Network error verifying LIVE payment: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while verifying payment",
                "mode": "LIVE"
            }
        except Exception as e:
            logger.error(f"❌❌❌ Error verifying LIVE payment: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def get_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Get transaction details - PRODUCTION
        """
        try:
            logger.info(f"💰 Getting LIVE transaction: {reference}")
            
            response = httpx.get(
                f"{self.base_url}/transaction/{reference}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅ Retrieved LIVE transaction: {reference}")
                return {
                    "status": "success",
                    "data": data["data"],
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ Failed to get LIVE transaction: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to get transaction"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error getting LIVE transaction: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
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
        List transactions with optional filters - PRODUCTION
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
            
            logger.info(f"💰 Listing LIVE transactions (page {page})")
            
            response = httpx.get(
                f"{self.base_url}/transaction",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅ Retrieved {len(data['data'])} LIVE transactions")
                return {
                    "status": "success",
                    "transactions": data["data"],
                    "meta": data.get("meta", {}),
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ Failed to list LIVE transactions: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to list transactions"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error listing LIVE transactions: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def charge_authorization(
        self,
        email: str,
        amount: float,
        authorization_code: str,
        reference: str
    ) -> Dict[str, Any]:
        """
        Charge a previously authorized payment - PRODUCTION
        """
        try:
            amount_kobo = int(amount * 100)
            
            payload = {
                "email": email,
                "amount": amount_kobo,
                "authorization_code": authorization_code,
                "reference": reference
            }
            
            logger.info(f"💰 Charging LIVE authorization: {reference} - ₦{amount:,}")
            
            response = httpx.post(
                f"{self.base_url}/transaction/charge_authorization",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅✅✅ LIVE authorization charged: {reference}")
                return {
                    "status": "success",
                    "data": data["data"],
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ LIVE authorization charge failed: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Charge authorization failed"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error charging LIVE authorization: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def check_balance(self) -> Dict[str, Any]:
        """
        Check Paystack account balance - PRODUCTION LIVE
        """
        try:
            logger.info("💰 Checking LIVE Paystack balance...")
            
            response = httpx.get(
                f"{self.base_url}/balance",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                balance = data["data"][0]["balance"] / 100
                logger.info(f"💰💰💰 LIVE PAYSTACK BALANCE: ₦{balance:,.2f}")
                return {
                    "status": "success",
                    "balance": balance,
                    "currency": data["data"][0]["currency"],
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ Failed to check LIVE balance: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to check balance"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error checking LIVE balance: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def create_customer(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a customer in Paystack - PRODUCTION
        """
        try:
            payload = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name
            }
            
            if phone:
                payload["phone"] = phone
            
            logger.info(f"💰 Creating LIVE customer: {email}")
            
            response = httpx.post(
                f"{self.base_url}/customer",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅ Created LIVE customer: {email}")
                return {
                    "status": "success",
                    "customer_code": data["data"]["customer_code"],
                    "data": data["data"],
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ Failed to create LIVE customer: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to create customer"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error creating LIVE customer: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }
    
    def refund_transaction(
        self,
        reference: str,
        amount: Optional[float] = None,
        merchant_note: Optional[str] = None,
        customer_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refund a transaction - PRODUCTION
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
            
            logger.info(f"💰 Processing LIVE refund: {reference}")
            
            response = httpx.post(
                f"{self.base_url}/refund",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                logger.info(f"✅✅✅ LIVE refund processed: {reference}")
                return {
                    "status": "success",
                    "data": data["data"],
                    "mode": "LIVE"
                }
            else:
                logger.error(f"❌ LIVE refund failed: {data.get('message')}")
                return {
                    "status": "error",
                    "message": data.get("message", "Refund failed"),
                    "mode": "LIVE"
                }
                
        except Exception as e:
            logger.error(f"❌❌❌ Error processing LIVE refund: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "mode": "LIVE"
            }


def process_post_payment(user_email: str, user_type: str, payment_type: str, db):
    """
    Process post-payment actions - PRODUCTION
    This is called after successful payment verification
    """
    from app.utils.promote_applicant import promote_to_applicant
    from app.models.applicant import Applicant
    from app.models.pre_applicant import PreApplicant
    from sqlalchemy import func
    
    try:
        logger.info(f"💰 PROCESSING POST-PAYMENT FOR: {user_email} ({user_type}) - {payment_type}")
        
        if user_type == "pre_applicant":
            pre_applicant = db.query(PreApplicant).filter(
                func.lower(PreApplicant.email) == user_email.lower()
            ).first()
            
            if pre_applicant:
                pre_applicant.has_paid = True
                pre_applicant.status = "payment_completed"
                pre_applicant.updated_at = datetime.utcnow()
                db.commit()
                
                try:
                    promote_to_applicant(user_email, db)
                    logger.info(f"✅✅✅ Pre-applicant {user_email} promoted to applicant")
                except Exception as promote_error:
                    logger.error(f"❌ Error promoting pre-applicant: {str(promote_error)}")
                    # Don't re-raise, just log - we can retry later
            else:
                logger.warning(f"⚠️ No pre-applicant found for {user_email}")
        
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
                logger.info(f"✅✅✅ Applicant {user_email} payment marked as paid")
            else:
                logger.warning(f"⚠️ No applicant found for {user_email}")
        
        elif user_type == "existing_officer":
            logger.info(f"✅✅✅ Existing officer {user_email} registration completed")
        
        logger.info(f"✅✅✅ POST-PAYMENT PROCESSING COMPLETED FOR {user_email}")
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR IN POST-PAYMENT PROCESSING: {str(e)}", exc_info=True)
        # Don't re-raise - let the payment verification succeed even if post-processing fails