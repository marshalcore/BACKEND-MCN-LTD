# app/routes/payment.py - PRODUCTION LIVE MODE VERSION - FIXED
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
import uuid

from app.database import get_db
from app.services.payment_service import PaymentService, process_post_payment
from app.models.payment import Payment
from app.models.applicant import Applicant
from app.models.pre_applicant import PreApplicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.schemas.payment import PaymentCreate, PaymentVerify, GatewayCallback, ManualPaymentRequest
from app.config import settings
from app.utils.promote_applicant import promote_to_applicant

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"]
)

# Account details for immediate transfers (DEPRECATED - Using Paystack Native Split Now)
# Kept for backward compatibility reference
IMMEDIATE_TRANSFER_CONFIG = {
    "marshal_core_share": {
        "account_name": settings.MARSHAL_CORE_BANK_ACCOUNT_NAME,
        "account_number": settings.MARSHAL_CORE_ACCOUNT_NUMBER,
        "bank": settings.MARSHAL_CORE_BANK_NAME,
        "bank_code": settings.MARSHAL_CORE_BANK_CODE,
        "recipient_type": "marshal_core_share",
        "description": "MarshalCoreShare - 50% Share"
    },
    "systems_maintainance": {
        "account_name": settings.SYSTEMS_MAINTAINANCE_ACCOUNT_NAME,
        "account_number": settings.SYSTEMS_MAINTAINANCE_ACCOUNT_NUMBER,
        "bank": settings.SYSTEMS_MAINTAINANCE_BANK_NAME,
        "bank_code": settings.SYSTEMS_MAINTAINANCE_BANK_CODE,
        "recipient_type": "systems_maintainance",
        "description": "SystemsMaintainance - 35% Share"
    },
    "estech_digital_systems_limited": {
        "account_name": settings.ESTECH_ACTUAL_BENEFICIARY,
        "account_number": settings.ESTECH_BANK_ACCOUNT_NUMBER,
        "bank": settings.ESTECH_BANK_NAME,
        "bank_code": "100",  # OPay bank code
        "recipient_type": "estech_digital_systems_limited",
        "description": settings.ESTECH_COMMISSION_PURPOSE
    }
}

# Payment configurations for PRODUCTION LIVE MODE WITH PAYSTACK NATIVE SPLIT
PAYMENT_CONFIGS = {
    "regular": {
        "user_amount": settings.REGULAR_APPLICATION_FEE,
        "display": f"₦{settings.REGULAR_APPLICATION_FEE:,} Regular Application Fee",
        "base_amount": 5000,
        "use_native_split": True,  # Enabled - Using Paystack Dashboard Split Group (SPL_KRGO7FYBBU)
        
        # Recipients for native split (Paystack subaccounts)
        "recipients": {
            "marshal_core_share": {
                "percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                "amount": int(settings.REGULAR_APPLICATION_FEE * (settings.MARSHAL_CORE_SHARE_PERCENTAGE / 100)),
                "description": "MarshalCoreShare - 50%",
                "subaccount_code": settings.MARSHAL_CORE_PAYSTACK_SUBACCOUNT_CODE,
            },
            "systems_maintainance": {
                "percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                "amount": int(settings.REGULAR_APPLICATION_FEE * (settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE / 100)),
                "description": "SystemsMaintainance - 35% (FCMB - MARSHAL CORE OF NIGERIA LIMITED)",
                "subaccount_code": settings.SYSTEMS_MAINTAINANCE_PAYSTACK_SUBACCOUNT_CODE,
            },
            "estech_digital_systems_limited": {
                "percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "amount": int(settings.REGULAR_APPLICATION_FEE * (settings.ESTECH_COMMISSION_PERCENTAGE / 100)),
                "description": "eSTechDigitalSystemsLimited - 15%",
                "subaccount_code": settings.ESTECH_PAYSTACK_SUBACCOUNT_CODE,
            }
        },
        
        "user_message": f"Pay ₦{settings.REGULAR_APPLICATION_FEE:,} Application Fee",
        "receipt_description": "Marshal Core Nigeria - Regular Application Fee",
        "category": "regular_application"
    },
    
    "vip": {
        "user_amount": settings.VIP_APPLICATION_FEE,
        "display": f"₦{settings.VIP_APPLICATION_FEE:,} VIP Application Fee",
        "base_amount": 25000,
        "use_native_split": True,  # Enabled - Using Paystack Dashboard Split Group (SPL_KRGO7FYBBU)
        
        "recipients": {
            "marshal_core_share": {
                "percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                "amount": int(settings.VIP_APPLICATION_FEE * (settings.MARSHAL_CORE_SHARE_PERCENTAGE / 100)),
                "description": "MarshalCoreShare - 50%",
            },
            "systems_maintainance": {
                "percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                "amount": int(settings.VIP_APPLICATION_FEE * (settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE / 100)),
                "description": "SystemsMaintainance - 35%",
            },
            "estech_digital_systems_limited": {
                "percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "amount": int(settings.VIP_APPLICATION_FEE * (settings.ESTECH_COMMISSION_PERCENTAGE / 100)),
                "description": "eSTechDigitalSystemsLimited - 15%",
            }
        },
        
        "user_message": f"Pay ₦{settings.VIP_APPLICATION_FEE:,} VIP Application Fee",
        "receipt_description": "Marshal Core Nigeria - VIP Application Fee",
        "category": "vip_application"
    },
    
    "existing_officer": {
        "user_amount": 0,
        "display": "Free Registration",
        "use_native_split": False,
        "category": "existing_officer",
        "user_message": "Free Registration"
    }
}

@router.post("/initiate")
async def initiate_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db)
):
    """
    Initiate payment with immediate split configuration
    PRODUCTION LIVE MODE - Real money transactions only
    """
    try:
        # Log payment initiation attempt
        logger.info(f"💰💰💰 PAYMENT INITIATION REQUEST: {payment_data.email} - {payment_data.payment_type}")
        
        # Convert enum values to strings if needed
        payment_type_str = payment_data.payment_type
        user_type_str = payment_data.user_type
        
        if payment_type_str not in PAYMENT_CONFIGS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment type. Must be one of: {', '.join(PAYMENT_CONFIGS.keys())}"
            )
        
        config = PAYMENT_CONFIGS[payment_type_str]
        
        # Don't require user to exist in database
        # This allows new registrations to make payments
        user = None
        if user_type_str == "applicant":
            user = db.query(Applicant).filter(
                func.lower(Applicant.email) == payment_data.email.lower()
            ).first()
            # Also check pre-applicants for applicants
            if not user:
                user = db.query(PreApplicant).filter(
                    func.lower(PreApplicant.email) == payment_data.email.lower()
                ).first()
        
        elif user_type_str == "pre_applicant":
            user = db.query(PreApplicant).filter(
                func.lower(PreApplicant.email) == payment_data.email.lower()
            ).first()
        
        elif user_type_str == "officer":
            user = db.query(Officer).filter(
                func.lower(Officer.email) == payment_data.email.lower()
            ).first()
        
        elif user_type_str == "existing_officer":
            user = db.query(ExistingOfficer).filter(
                func.lower(ExistingOfficer.email) == payment_data.email.lower()
            ).first()
        
        # Allow payment even if user doesn't exist
        if not user:
            logger.info(f"💰 Payment initiated for new user: {payment_data.email} ({user_type_str})")
        
        # Check for existing successful payment
        existing_payment = db.query(Payment).filter(
            Payment.user_email == payment_data.email.lower(),
            Payment.user_type == user_type_str,
            Payment.payment_type == payment_type_str,
            Payment.status == "success"
        ).first()
        
        if existing_payment:
            return {
                "status": "already_paid",
                "message": "Payment already completed",
                "payment_reference": existing_payment.payment_reference,
                "amount": config["user_amount"],
                "user_message": "Payment already completed",
                "environment": "PRODUCTION LIVE"
            }
        
        # Check for pending payment
        pending_payment = db.query(Payment).filter(
            Payment.user_email == payment_data.email.lower(),
            Payment.user_type == user_type_str,
            Payment.payment_type == payment_type_str,
            Payment.status == "pending"
        ).first()
        
        if pending_payment:
            # Verify if pending payment is still valid
            payment_service = PaymentService()
            verification = payment_service.verify_payment(pending_payment.payment_reference)
            
            if verification.get("status") == "success":
                # Update to success
                pending_payment.status = "success"
                pending_payment.paid_at = datetime.utcnow()
                pending_payment.verification_data = verification
                db.commit()
                
                return {
                    "status": "already_paid",
                    "message": "Payment already completed",
                    "payment_reference": pending_payment.payment_reference,
                    "amount": config["user_amount"],
                    "user_message": "Payment already completed",
                    "environment": "PRODUCTION LIVE"
                }
            else:
                # Return existing pending payment
                return {
                    "status": "pending",
                    "message": "Payment already initiated",
                    "payment_reference": pending_payment.payment_reference,
                    "authorization_url": pending_payment.authorization_url,
                    "amount": config["user_amount"],
                    "user_message": "Continue with existing payment",
                    "environment": "PRODUCTION LIVE"
                }
        
        # Generate new payment reference
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        payment_ref = f"MCN_{payment_type_str.upper()}_{timestamp}"
        
        # Prepare user info
        user_info = {}
        if user:
            user_info = {
                "user_id": str(getattr(user, 'id', '')),
                "full_name": getattr(user, 'full_name', getattr(user, 'name', '')),
                "phone": getattr(user, 'phone_number', getattr(user, 'phone', getattr(user, 'contact_number', '')))
            }
        else:
            user_info = {
                "user_id": "pending_registration",
                "full_name": payment_data.email.split('@')[0],
                "phone": ""
            }
        
        # PRODUCTION LIVE MODE - Always live
        is_live_mode = True
        
        payment_metadata = {
            "user_info": user_info,
            "user_type": user_type_str,
            "email": payment_data.email.lower(),
            "payment_type": payment_type_str,
            "environment": "PRODUCTION LIVE",
            
            "split_config": {
                "user_paid": config["user_amount"],
                "native_split_enabled": config.get("use_native_split", False),
                
                "recipients": {
                    "marshal_core_share": {
                        **config["recipients"].get("marshal_core_share", {}),
                        "account_details": IMMEDIATE_TRANSFER_CONFIG.get("marshal_core_share", {})
                    },
                    "systems_maintainance": {
                        **config["recipients"].get("systems_maintainance", {}),
                        "account_details": IMMEDIATE_TRANSFER_CONFIG.get("systems_maintainance", {})
                    },
                    "estech_digital_systems_limited": {
                        **config["recipients"].get("estech_digital_systems_limited", {}),
                        "account_details": IMMEDIATE_TRANSFER_CONFIG.get("estech_digital_systems_limited", {})
                    }
                },
                
                "fees": {
                    "marshal_core_share_percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                    "systems_maintainance_percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                    "estech_digital_systems_limited_percentage": settings.ESTECH_COMMISSION_PERCENTAGE
                }
            },
            
            "category": config["category"],
            "payment_date": datetime.now().isoformat(),
            "is_live_mode": is_live_mode,
            "system_mode": "PRODUCTION LIVE"
        }
        
        payment_service = PaymentService()
        
        # Handle free payments (existing officers)
        if config["user_amount"] == 0:
            payment = Payment(
                id=str(uuid.uuid4()),
                user_email=payment_data.email.lower(),
                user_type=user_type_str,
                amount=0,
                payment_type=payment_type_str,
                status="success",
                payment_reference=payment_ref,
                payment_metadata=payment_metadata,
                director_general_share=0,
                estech_system_share=0,
                marshal_net_amount=0,
                immediate_transfers_processed=True,
                # REMOVED: is_test_payment=False,  # This field doesn't exist in the model
                paid_at=datetime.utcnow()
            )
            db.add(payment)
            db.commit()
            
            logger.info(f"✅✅✅ FREE REGISTRATION COMPLETED: {payment_data.email}")
            
            return {
                "status": "success",
                "message": "Registration completed successfully",
                "payment_reference": payment_ref,
                "amount": 0,
                "user_message": config["user_message"],
                "environment": "PRODUCTION LIVE"
            }
        else:
            # PRODUCTION callback URL
            callback_url = "https://marshalcoreofnigeria.ng/apply.html?payment_success=true"
            logger.info(f"💰 PRODUCTION CALLBACK URL: {callback_url}")
            
            logger.info(f"💰💰💰 INITIATING PRODUCTION LIVE PAYMENT: {payment_data.email} - ₦{config['user_amount']:,}")
            
            # 🔥 BUILD PAYSTACK NATIVE SPLIT CONFIGURATION
            # Check if using Paystack Dashboard Split Group (split_code) or dynamic splits
            split_subaccounts = []
            use_native_split = config.get("use_native_split", False)
            split_code = None  # Paystack Dashboard Split Code
            
            if settings.PAYSTACK_SPLIT_CODE:
                # Use Paystack Dashboard Split Group - recommended approach
                split_code = settings.PAYSTACK_SPLIT_CODE
                use_native_split = True
                logger.info(f"💰💰💰 USING PAYSTACK DASHBOARD SPLIT GROUP: {split_code}")
            elif use_native_split:
                # Build subaccounts list from config for dynamic split
                for recipient_key, recipient_data in config.get("recipients", {}).items():
                    subaccount_code = recipient_data.get("subaccount_code")
                    if subaccount_code:  # Only add if subaccount code is configured
                        split_subaccounts.append({
                            "subaccount": subaccount_code,
                            "share": recipient_data.get("percentage", 0)  # Percentage (1-100)
                        })
                        logger.info(f"   → Adding split: {recipient_data.get('percentage')}% to {recipient_key}")
                
                logger.info(f"💰💰💰 NATIVE SPLIT CONFIGURED: {len(split_subaccounts)} subaccounts")
            
            # Call payment service with split configuration
            payment_response = payment_service.initiate_payment(
                email=payment_data.email,
                amount=config["user_amount"],
                reference=payment_ref,
                metadata=payment_metadata,
                callback_url=callback_url,
                split_payment=use_native_split,
                split_subaccounts=split_subaccounts if split_subaccounts else None,
                split_code=split_code,
                splitBearer="account"  # eSTech (main account) bears the Paystack fees
            )
            
            if payment_response.get("status") != "success" or not payment_response.get("authorization_url"):
                error_msg = payment_response.get("message", "Payment initialization failed")
                logger.error(f"❌❌❌ PRODUCTION PAYMENT INITIALIZATION ERROR: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize payment: {error_msg}"
                )
            
            # Calculate split amounts for record keeping
            marshal_core_share = config["recipients"].get("marshal_core_share", {}).get("amount", 0)
            systems_maintainance_share = config["recipients"].get("systems_maintainance", {}).get("amount", 0)
            estech_digital_share = config["recipients"].get("estech_digital_systems_limited", {}).get("amount", 0)
            
            payment = Payment(
                id=str(uuid.uuid4()),
                user_email=payment_data.email.lower(),
                user_type=user_type_str,
                amount=config["user_amount"],
                payment_type=payment_type_str,
                status="pending",
                payment_reference=payment_ref,
                paystack_reference=payment_response.get("reference"),  # Store Paystack's actual reference
                authorization_url=payment_response.get("authorization_url"),
                access_code=payment_response.get("access_code"),
                payment_metadata=payment_metadata,
                
                # Updated field names for split payments
                director_general_share=systems_maintainance_share,  # SystemsMaintainance - 35%
                estech_system_share=estech_digital_share,  # eSTechDigitalSystemsLimited - 15%
                marshal_net_amount=marshal_core_share,  # MarshalCoreShare - 50%
                
                immediate_transfers_processed=use_native_split,  # True if using native split
                transfer_metadata={
                    "split_type": "native" if use_native_split else "post_payment",
                    "split_code": split_code,  # Paystack Dashboard Split Code
                    "subaccounts": split_subaccounts if split_subaccounts else [],
                    "marshal_core_share": marshal_core_share,
                    "systems_maintainance_share": systems_maintainance_share,
                    "estech_digital_systems_limited_share": estech_digital_share,
                    "native_split_used": use_native_split,
                    "using_dashboard_split_group": bool(split_code)
                }
            )
            db.add(payment)
            db.commit()
            
            logger.info(f"✅✅✅ PRODUCTION PAYMENT INITIALIZED: {payment_ref} for {payment_data.email}")
            logger.info(f"   → MarshalCoreShare: ₦{marshal_core_share:,} ({settings.MARSHAL_CORE_SHARE_PERCENTAGE}%)")
            logger.info(f"   → SystemsMaintainance: ₦{systems_maintainance_share:,} ({settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%)")
            logger.info(f"   → eSTechDigitalSystemsLimited: ₦{estech_digital_share:,} ({settings.ESTECH_COMMISSION_PERCENTAGE}%)")
            if split_code:
                logger.info(f"   → Using Paystack Dashboard Split Group: {split_code}")
            
            return {
                "status": "success",
                "message": "Payment initialized",
                "payment_reference": payment_ref,
                "paystack_reference": payment_response.get("reference"),  # Paystack's actual reference
                "authorization_url": payment_response.get("authorization_url"),
                "amount": config["user_amount"],
                "amount_display": f"₦{config['user_amount']:,}",
                "user_message": config["user_message"],
                "payment_type": payment_type_str,
                "environment": "PRODUCTION LIVE",
                "native_split_enabled": use_native_split,
                "split_code": split_code,
                "split_details": {
                    "marshal_core_share": {"amount": marshal_core_share, "percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE},
                    "systems_maintainance": {"amount": systems_maintainance_share, "percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE},
                    "estech_digital_systems_limited": {"amount": estech_digital_share, "percentage": settings.ESTECH_COMMISSION_PERCENTAGE}
                } if use_native_split else None
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌❌❌ ERROR INITIATING PRODUCTION PAYMENT: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate payment: {str(e)}"
        )

@router.post("/verify/{reference}")
async def verify_payment(
    reference: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Verify payment and trigger background split processing
    PRODUCTION LIVE MODE - Real money verification
    
    Handles both application references (MCN_*) and Paystack references (T* or R*)
    
    Uses professional background job service for:
    - Automatic payment processing
    - Error checking
    - Retry logic
    - Clear feedback and logging
    """
    try:
        from app.services.background_job_service import background_job_service, JobType
        
        payment_service = PaymentService()
        
        # Try to find payment by app reference first
        payment = db.query(Payment).filter(
            Payment.payment_reference == reference
        ).first()
        
        # If not found by app reference, try Paystack reference
        if not payment:
            logger.info(f"🔍 Payment not found by app reference '{reference}', trying Paystack reference lookup...")
            payment = db.query(Payment).filter(
                Payment.paystack_reference == reference
            ).first()
        
        # If still not found, verify with Paystack and try to find by metadata
        if not payment:
            logger.info(f"🔍 Payment not found by Paystack reference '{reference}', querying Paystack...")
            paystack_verification = payment_service.verify_payment(reference)
            
            if paystack_verification.get("status") == "success":
                # Payment exists in Paystack but not in our DB
                # Try to find by email from metadata
                paystack_metadata = paystack_verification.get("metadata", {})
                user_email = paystack_metadata.get("email")
                user_type = paystack_metadata.get("user_type", "pre_applicant")
                payment_type = paystack_metadata.get("payment_type", "regular")
                
                logger.info(f"🔍 Paystack verification succeeded, looking for payment by email: {user_email}")
                
                # Find the pending payment for this user
                payment = db.query(Payment).filter(
                    Payment.user_email == user_email.lower(),
                    Payment.user_type == user_type,
                    Payment.payment_type == payment_type,
                    Payment.status == "pending"
                ).order_by(desc(Payment.created_at)).first()
                
                if payment:
                    logger.info(f"✅ Found payment by email: {payment.payment_reference}")
                    # Update the Paystack reference if not set
                    if not payment.paystack_reference:
                        payment.paystack_reference = reference
                else:
                    logger.warning(f"⚠️ Could not find corresponding payment in database for Paystack reference: {reference}")
            else:
                logger.warning(f"⚠️ Paystack verification also failed for: {reference}")
        
        if not payment:
            logger.error(f"❌ Payment not found: {reference}")
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        # Check if already verified
        if payment.status == "success":
            logger.info(f"💰 Payment {payment.payment_reference} already verified")
            
            # Get job status
            job_status = background_job_service.get_job_status(payment.payment_reference)
            
            return {
                "status": "success",
                "message": "Payment already verified",
                "payment_reference": payment.payment_reference,
                "paystack_reference": payment.paystack_reference,
                "amount": f"₦{payment.amount:,}",
                "environment": "PRODUCTION LIVE",
                "job_status": job_status.get("latest_status"),
                "split_config": {
                    "marshal_core_share_percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                    "systems_maintainance_percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                    "estech_digital_systems_limited_percentage": settings.ESTECH_COMMISSION_PERCENTAGE
                }
            }
        
        # Verify payment with Paystack PRODUCTION
        logger.info("=" * 60)
        logger.info(f"🔐 VERIFICATION STARTED")
        logger.info(f"   App Reference: {payment.payment_reference}")
        logger.info(f"   Paystack Reference: {reference}")
        logger.info(f"   Amount: ₦{payment.amount:,}")
        logger.info(f"   User Type: {payment.user_type}")
        logger.info("=" * 60)
        
        verification = payment_service.verify_payment(reference)
        
        if verification.get("status") == "success":
            # Update payment status
            payment.status = "success"
            payment.paid_at = datetime.utcnow()
            payment.verification_data = verification
            
            db.commit()
            db.refresh(payment)
            
            logger.info("=" * 60)
            logger.info("✅✅✅ PAYMENT VERIFIED SUCCESSFULLY")
            logger.info(f"   App Reference: {payment.payment_reference}")
            logger.info(f"   Paystack Reference: {reference}")
            logger.info(f"   Amount: ₦{payment.amount:,}")
            logger.info(f"   Time: {datetime.utcnow().isoformat()}")
            logger.info("=" * 60)
            
            # Trigger background job for split processing
            logger.info("📋 Queuing background split job...")
            background_tasks.add_task(
                background_job_service.process_payment_split,
                payment_reference=payment.payment_reference,
                db=db
            )
            
            # Update user status based on user_type
            if payment.user_type == "pre_applicant":
                pre_applicant = db.query(PreApplicant).filter(
                    func.lower(PreApplicant.email) == payment.user_email
                ).first()
                
                if pre_applicant:
                    pre_applicant.has_paid = True
                    pre_applicant.status = "payment_completed"
                    pre_applicant.payment_reference = reference
                    db.commit()
                    
                    try:
                        # Promote to applicant
                        await promote_to_applicant(payment.user_email, db)
                        logger.info(f"✅✅✅ SUCCESSFULLY PROMOTED PRE-APPLICANT: {payment.user_email}")
                    except Exception as e:
                        logger.error(f"❌ ERROR PROMOTING PRE-APPLICANT: {e}")
                        # Store error in payment metadata
                        payment_metadata = payment.payment_metadata or {}
                        payment_metadata["promotion_error"] = str(e)
                        payment.payment_metadata = payment_metadata
                        db.commit()
            
            elif payment.user_type == "applicant":
                applicant = db.query(Applicant).filter(
                    func.lower(Applicant.email) == payment.user_email
                ).first()
                
                if applicant:
                    applicant.payment_status = "paid"
                    applicant.payment_type = payment.payment_type
                    applicant.payment_reference = reference
                    applicant.amount_paid = payment.amount
                    applicant.paid_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"✅✅✅ APPLICANT PAYMENT MARKED AS PAID: {payment.user_email}")
            
            # Calculate and record split amounts
            total_amount = payment.amount
            marshal_share = int(total_amount * (settings.MARSHAL_CORE_SHARE_PERCENTAGE / 100))
            systems_share = int(total_amount * (settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE / 100))
            estech_share = int(total_amount * (settings.ESTECH_COMMISSION_PERCENTAGE / 100))
            
            # Update payment with split amounts
            payment.director_general_share = systems_share
            payment.estech_system_share = estech_share
            payment.marshal_net_amount = marshal_share
            payment.immediate_transfers_processed = True  # Native split handles this
            
            split_metadata = {
                "split_type": "native",
                "timestamp": datetime.utcnow().isoformat(),
                "marshal_core_share": marshal_share,
                "marshal_core_share_percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                "systems_maintainance_share": systems_share,
                "systems_maintainance_share_percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                "estech_digital_systems_limited_share": estech_share,
                "estech_digital_systems_limited_share_percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "processed_via": "background_job_service"
            }
            payment.transfer_metadata = split_metadata
            db.commit()
            
            logger.info("💰 SPLIT AMOUNTS RECORDED:")
            logger.info(f"   MarshalCoreShare (50%): ₦{marshal_share:,}")
            logger.info(f"   SystemsMaintainance (35%): ₦{systems_share:,}")
            logger.info(f"   eSTechDigitalSystemsLimited (15%): ₦{estech_share:,}")
            
            # Process post-payment tasks
            logger.info(f"💰 QUEUING POST-PAYMENT TASKS FOR: {payment.user_email}")
            background_tasks.add_task(
                process_post_payment,
                user_email=payment.user_email,
                user_type=payment.user_type,
                payment_type=payment.payment_type,
                db=db
            )
            
            return {
                "status": "success",
                "message": "Payment successful! Your application is being processed.",
                "payment_reference": payment.payment_reference,
                "paystack_reference": reference,
                "amount": f"₦{payment.amount:,}",
                "payment_date": payment.paid_at.isoformat() if payment.paid_at else None,
                "environment": "PRODUCTION LIVE",
                "split_config": {
                    "marshal_core_share": marshal_share,
                    "marshal_core_share_percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                    "systems_maintainance_share": systems_share,
                    "systems_maintainance_percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                    "estech_digital_systems_limited_share": estech_share,
                    "estech_digital_systems_limited_percentage": settings.ESTECH_COMMISSION_PERCENTAGE
                }
            }
        else:
            # Payment verification failed
            payment.status = "failed"
            payment.verification_data = verification
            db.commit()
            
            error_msg = verification.get("message", "Payment verification failed")
            logger.error(f"❌❌❌ PRODUCTION PAYMENT VERIFICATION FAILED: {error_msg}")
            
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌❌❌ ERROR VERIFYING PRODUCTION PAYMENT: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Payment verification failed: {str(e)}"
        )

@router.post("/callback/paystack")
async def paystack_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Paystack webhook callback - handles payment splits
    PRODUCTION LIVE MODE - Called by Paystack
    
    Uses native split - no manual transfers needed
    """
    try:
        # Get the payload
        payload = await request.json()
        event = payload.get("event")
        data = payload.get("data", {})
        
        logger.info("=" * 60)
        logger.info("📡 PAYSTACK WEBHOOK RECEIVED")
        logger.info(f"   Event: {event}")
        logger.info(f"   Reference: {data.get('reference')}")
        logger.info("=" * 60)
        
        if event == "charge.success":
            reference = data.get("reference")
            if reference:
                payment_service = PaymentService()
                verification = payment_service.verify_payment(reference)
                
                if verification.get("status") == "success":
                    # Look up by Paystack's actual reference first, then our custom reference
                    payment = db.query(Payment).filter(
                        Payment.paystack_reference == reference
                    ).first()

                    if not payment:
                        # Fallback to our custom reference
                        payment = db.query(Payment).filter(
                            Payment.payment_reference == reference
                        ).first()

                    # Update Paystack reference if not set
                    if payment and not payment.paystack_reference:
                        payment.paystack_reference = reference
                    
                    if payment and payment.status != "success":
                        # Update payment status
                        payment.status = "success"
                        payment.paid_at = datetime.utcnow()
                        payment.verification_data = verification
                        
                        # Calculate and record split amounts
                        total_amount = payment.amount
                        marshal_share = int(total_amount * (settings.MARSHAL_CORE_SHARE_PERCENTAGE / 100))
                        systems_share = int(total_amount * (settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE / 100))
                        estech_share = int(total_amount * (settings.ESTECH_COMMISSION_PERCENTAGE / 100))
                        
                        payment.director_general_share = systems_share
                        payment.estech_system_share = estech_share
                        payment.marshal_net_amount = marshal_share
                        payment.immediate_transfers_processed = True
                        
                        split_metadata = {
                            "split_type": "native",
                            "timestamp": datetime.utcnow().isoformat(),
                            "marshal_core_share": marshal_share,
                            "systems_maintainance_share": systems_share,
                            "estech_digital_systems_limited_share": estech_share,
                            "processed_via": "webhook"
                        }
                        payment.transfer_metadata = split_metadata
                        db.commit()
                        
                        logger.info("=" * 60)
                        logger.info("✅✅✅ PAYMENT PROCESSED VIA WEBHOOK")
                        logger.info(f"   Reference: {reference}")
                        logger.info(f"   Amount: ₦{payment.amount:,}")
                        logger.info(f"   MarshalCoreShare: ₦{marshal_share:,}")
                        logger.info(f"   SystemsMaintainance: ₦{systems_share:,}")
                        logger.info(f"   eSTechDigitalSystemsLimited: ₦{estech_share:,}")
                        logger.info("=" * 60)
                        
                        # Process post-payment
                        background_tasks.add_task(
                            process_post_payment,
                            user_email=payment.user_email,
                            user_type=payment.user_type,
                            payment_type=payment.payment_type,
                            db=db
                        )
        
        elif event == "transfer.success":
            logger.info(f"✅ TRANSFER SUCCESS: {data.get('reference')}")
        
        elif event == "transfer.failed":
            logger.error(f"❌ TRANSFER FAILED: {data.get('reference')}")
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(f"❌❌❌ WEBHOOK ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/admin/transfers")
async def get_transfer_history(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: View all immediate transfers
    PRODUCTION LIVE MODE
    """
    try:
        from app.models.immediate_transfer import ImmediateTransfer
        
        query = db.query(ImmediateTransfer)
        
        if status:
            query = query.filter(ImmediateTransfer.status == status)
        if start_date:
            query = query.filter(ImmediateTransfer.created_at >= start_date)
        if end_date:
            query = query.filter(ImmediateTransfer.created_at <= end_date)
        
        transfers = query.order_by(desc(ImmediateTransfer.created_at)).all()
        
        total_amount = sum(t.amount for t in transfers)
        total_marshal_core = sum(t.amount for t in transfers if t.recipient_type == "marshal_core_share")
        total_systems_maintainance = sum(t.amount for t in transfers if t.recipient_type == "systems_maintainance")
        total_estech_digital = sum(t.amount for t in transfers if t.recipient_type == "estech_digital_systems_limited")
        
        return {
            "status": "success",
            "environment": "PRODUCTION LIVE",
            "transfers": [
                {
                    "id": t.id,
                    "payment_reference": t.payment_reference,
                    "recipient_type": t.recipient_type,
                    "recipient_name": t.recipient_account.split(" - ")[0] if t.recipient_account else "",
                    "amount": f"₦{t.amount:,}",
                    "status": t.status,
                    "transfer_reference": t.transfer_reference,
                    "transferred_at": t.transferred_at.isoformat() if t.transferred_at else None,
                    "bank": t.recipient_bank,
                    "is_test_mode": False  # Always false in production
                }
                for t in transfers
            ],
            "summary": {
                "total_transfers": len(transfers),
                "total_amount": f"₦{total_amount:,}",
                "marshal_core_share_total": f"₦{total_marshal_core:,}",
                "systems_maintainance_total": f"₦{total_systems_maintainance:,}",
                "estech_digital_systems_limited_total": f"₦{total_estech_digital:,}",
                "transfer_accounts": IMMEDIATE_TRANSFER_CONFIG
            }
        }
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING TRANSFER HISTORY: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get transfer history"
        )

@router.get("/admin/transfer-status/{payment_reference}")
async def get_transfer_status(
    payment_reference: str,
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: Check transfer status for a specific payment
    PRODUCTION LIVE MODE
    """
    try:
        from app.models.immediate_transfer import ImmediateTransfer
        
        payment = db.query(Payment).filter(
            Payment.payment_reference == payment_reference
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        transfers = db.query(ImmediateTransfer).filter(
            ImmediateTransfer.payment_reference == payment_reference
        ).all()
        
        config = PAYMENT_CONFIGS.get(payment.payment_type, {})
        expected_transfers = []
        
        if config.get("use_native_split", False) and payment.amount > 0:
            expected_transfers = [
                {
                    "recipient": "marshal_core_share",
                    "recipient_display": "MarshalCoreShare - 50%",
                    "expected_amount": config["recipients"].get("marshal_core_share", {}).get("amount", 0),
                    "account": IMMEDIATE_TRANSFER_CONFIG.get("marshal_core_share", {})
                },
                {
                    "recipient": "systems_maintainance",
                    "recipient_display": "SystemsMaintainance - 35%",
                    "expected_amount": config["recipients"].get("systems_maintainance", {}).get("amount", 0),
                    "account": IMMEDIATE_TRANSFER_CONFIG.get("systems_maintainance", {})
                },
                {
                    "recipient": "estech_digital_systems_limited",
                    "recipient_display": "eSTechDigitalSystemsLimited - 15%",
                    "expected_amount": config["recipients"].get("estech_digital_systems_limited", {}).get("amount", 0),
                    "account": IMMEDIATE_TRANSFER_CONFIG.get("estech_digital_systems_limited", {})
                }
            ]
        
        return {
            "status": "success",
            "environment": "PRODUCTION LIVE",
            "payment": {
                "reference": payment.payment_reference,
                "amount": f"₦{payment.amount:,}",
                "type": payment.payment_type,
                "status": payment.status,
                "immediate_transfers_processed": payment.immediate_transfers_processed,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None
            },
            "expected_transfers": expected_transfers,
            "actual_transfers": [
                {
                    "recipient_type": t.recipient_type,
                    "amount": f"₦{t.amount:,}",
                    "status": t.status,
                    "transfer_reference": t.transfer_reference,
                    "transferred_at": t.transferred_at.isoformat() if t.transferred_at else None
                }
                for t in transfers
            ],
            "transfer_status": "complete" if len(transfers) == len(expected_transfers) else "pending"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING TRANSFER STATUS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get transfer status"
        )

@router.get("/user/{email}")
async def get_user_payments(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Get payment history for a user
    PRODUCTION LIVE MODE
    """
    try:
        payments = db.query(Payment).filter(
            func.lower(Payment.user_email) == email.lower()
        ).order_by(desc(Payment.created_at)).all()
        
        user_payments = []
        for payment in payments:
            user_payments.append({
                "payment_reference": payment.payment_reference,
                "amount": f"₦{payment.amount:,}",
                "status": payment.status,
                "payment_type": payment.payment_type,
                "date": payment.paid_at.isoformat() if payment.paid_at else payment.created_at.isoformat(),
                "description": "Application Fee" if payment.payment_type in ["regular", "vip"] else "Registration",
                "environment": "PRODUCTION LIVE"
            })
        
        return {
            "status": "success",
            "environment": "PRODUCTION LIVE",
            "email": email,
            "payments": user_payments,
            "total_count": len(user_payments)
        }
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING USER PAYMENTS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get payment history"
        )

@router.get("/admin/stats")
async def get_payment_stats(
    db: Session = Depends(get_db),
    period: Optional[str] = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    ADMIN ONLY: Comprehensive payment statistics
    PRODUCTION LIVE MODE
    """
    try:
        query = db.query(Payment).filter(Payment.status == "success")
        
        if start_date:
            query = query.filter(Payment.paid_at >= start_date)
        if end_date:
            query = query.filter(Payment.paid_at <= end_date)
        
        all_payments = query.all()
        
        # PRODUCTION LIVE MODE - All payments are live
        live_payments = all_payments
        
        stats = {
            "overall": {
                "total_payments": len(all_payments),
                "live_payments": len(live_payments),
                "total_amount": sum(p.amount for p in all_payments),
                "live_amount": sum(p.amount for p in live_payments),
                "total_marshal_core_share": sum(p.marshal_net_amount or 0 for p in all_payments),  # MarshalCoreShare - 50%
                "total_systems_maintainance": sum(p.director_general_share for p in all_payments),  # SystemsMaintainance - 35%
                "total_estech_digital_systems_limited": sum(p.estech_system_share for p in all_payments),  # eSTechDigitalSystemsLimited - 15%
                "average_payment": sum(p.amount for p in all_payments) / len(all_payments) if all_payments else 0
            },
            
            "by_type": {
                "regular": {
                    "count": len([p for p in all_payments if p.payment_type == "regular"]),
                    "live_count": len([p for p in live_payments if p.payment_type == "regular"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "regular"),
                    "marshal_core_share": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "regular"),
                    "systems_maintainance": sum(p.director_general_share for p in all_payments if p.payment_type == "regular"),
                    "estech_digital_systems_limited": sum(p.estech_system_share for p in all_payments if p.payment_type == "regular")
                },
                "vip": {
                    "count": len([p for p in all_payments if p.payment_type == "vip"]),
                    "live_count": len([p for p in live_payments if p.payment_type == "vip"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "vip"),
                    "marshal_core_share": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "vip"),
                    "systems_maintainance": sum(p.director_general_share for p in all_payments if p.payment_type == "vip"),
                    "estech_digital_systems_limited": sum(p.estech_system_share for p in all_payments if p.payment_type == "vip")
                }
            },
            
            "daily_trend": {},
            "monthly_summary": {}
        }
        
        # Daily trend for last 30 days
        end_date_obj = datetime.now()
        start_date_obj = end_date_obj - timedelta(days=30)
        
        daily_payments = db.query(Payment).filter(
            Payment.status == "success",
            Payment.paid_at >= start_date_obj,
            Payment.paid_at <= end_date_obj
        ).all()
        
        for i in range(30):
            day = start_date_obj + timedelta(days=i)
            day_key = day.strftime("%Y-%m-%d")
            
            day_payments = [p for p in daily_payments if p.paid_at and p.paid_at.date() == day.date()]
            live_day_payments = day_payments  # All payments are live in production
            
            stats["daily_trend"][day_key] = {
                "count": len(day_payments),
                "live_count": len(live_day_payments),
                "total": sum(p.amount for p in day_payments),
                "live_total": sum(p.amount for p in live_day_payments),
                "marshal_core_share": sum(p.marshal_net_amount or 0 for p in day_payments),
                "systems_maintainance": sum(p.director_general_share for p in day_payments),
                "estech_digital_systems_limited": sum(p.estech_system_share for p in day_payments)
            }
        
        # Monthly summary
        for payment in all_payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in stats["monthly_summary"]:
                    stats["monthly_summary"][month_key] = {
                        "count": 0,
                        "live_count": 0,
                        "total": 0,
                        "live_total": 0,
                        "marshal_core_share": 0,
                        "systems_maintainance": 0,
                        "estech_digital_systems_limited": 0
                    }
                
                stats["monthly_summary"][month_key]["count"] += 1
                stats["monthly_summary"][month_key]["total"] += payment.amount
                stats["monthly_summary"][month_key]["marshal_core_share"] += (payment.marshal_net_amount or 0)
                stats["monthly_summary"][month_key]["systems_maintainance"] += payment.director_general_share
                stats["monthly_summary"][month_key]["estech_digital_systems_limited"] += payment.estech_system_share
                
                # PRODUCTION - Always live
                stats["monthly_summary"][month_key]["live_count"] += 1
                stats["monthly_summary"][month_key]["live_total"] += payment.amount
        
        # Format currency
        def format_currency(amount):
            return f"₦{amount:,.2f}" if isinstance(amount, (int, float)) else amount
        
        return {
            "status": "success",
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "environment": "PRODUCTION LIVE",
            "paystack_mode": "LIVE",
            "native_split_enabled": True,  # Using Paystack native split
            "stats": stats,
            "notes": [
                "🚀 PRODUCTION LIVE MODE - REAL MONEY ONLY",
                f"💰 Regular Application Fee: ₦{settings.REGULAR_APPLICATION_FEE:,}",
                f"💰 VIP Application Fee: ₦{settings.VIP_APPLICATION_FEE:,}",
                f"🎯 MarshalCoreShare: {settings.MARSHAL_CORE_SHARE_PERCENTAGE}%",
                f"🎯 SystemsMaintainance: {settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%",
                f"🎯 eSTechDigitalSystemsLimited: {settings.ESTECH_COMMISSION_PERCENTAGE}%",
                f"⚡ Paystack Native Split: ENABLED (Automatic split at payment time)"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING PAYMENT STATS: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get payment statistics"
        )

@router.post("/admin/retry-transfer/{payment_reference}")
async def retry_transfer(
    payment_reference: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: Retry failed transfers for a payment
    PRODUCTION LIVE MODE
    """
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        
        payment = db.query(Payment).filter(
            Payment.payment_reference == payment_reference
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        if payment.status != "success":
            raise HTTPException(
                status_code=400,
                detail="Payment is not successful"
            )
        
        transfer_service = ImmediateTransferService()
        
        background_tasks.add_task(
            transfer_service.retry_failed_transfers,
            payment_reference=payment_reference,
            db=db
        )
        
        return {
            "status": "success",
            "message": "Transfer retry queued",
            "payment_reference": payment_reference,
            "environment": "PRODUCTION LIVE"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌❌❌ ERROR QUEUING TRANSFER RETRY: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to queue transfer retry"
        )

@router.get("/types")
async def get_payment_types():
    """
    Get available payment types
    PRODUCTION LIVE MODE
    """
    return {
        "environment": "PRODUCTION LIVE",
        "paystack_mode": "LIVE",
        "payment_types": {
            "regular": {
                "amount": settings.REGULAR_APPLICATION_FEE,
                "currency": "NGN",
                "description": "Regular Application",
                "user_display": f"Pay ₦{settings.REGULAR_APPLICATION_FEE:,} Application Fee",
                "features": [
                    "Standard application processing",
                    "Normal processing timeline",
                    "Basic support"
                ],
                "split_config": {
                    "marshal_core_share": f"{settings.MARSHAL_CORE_SHARE_PERCENTAGE}%",
                    "systems_maintainance": f"{settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%",
                    "estech_digital_systems_limited": f"{settings.ESTECH_COMMISSION_PERCENTAGE}%"
                }
            },
            "vip": {
                "amount": settings.VIP_APPLICATION_FEE,
                "currency": "NGN",
                "description": "VIP Application",
                "user_display": f"Pay ₦{settings.VIP_APPLICATION_FEE:,} VIP Application Fee",
                "features": [
                    "Priority processing",
                    "Dedicated support",
                    "Expedited timeline",
                    "Additional benefits"
                ],
                "split_config": {
                    "marshal_core_share": f"{settings.MARSHAL_CORE_SHARE_PERCENTAGE}%",
                    "systems_maintainance": f"{settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%",
                    "estech_digital_systems_limited": f"{settings.ESTECH_COMMISSION_PERCENTAGE}%"
                }
            }
        },
        "notes": "🚀 PRODUCTION LIVE MODE - All payments are processed via Paystack with NATIVE SPLIT (automatic split at payment time)"
    }

@router.get("/check/{email}")
async def check_payment_status(
    email: str,
    payment_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Check payment status for a user
    PRODUCTION LIVE MODE
    """
    try:
        query = db.query(Payment).filter(
            func.lower(Payment.user_email) == email.lower(),
            Payment.status.in_(["pending", "success"])
        )
        
        if payment_type:
            query = query.filter(Payment.payment_type == payment_type)
        
        payment = query.order_by(desc(Payment.created_at)).first()
        
        if not payment:
            return {
                "status": "no_payment",
                "message": "No payment found for this user",
                "environment": "PRODUCTION LIVE"
            }
        
        response = {
            "status": payment.status,
            "payment_reference": payment.payment_reference,
            "amount": f"₦{payment.amount:,}",
            "payment_type": payment.payment_type,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "environment": "PRODUCTION LIVE"
        }
        
        if payment.status == "pending" and payment.authorization_url:
            response["authorization_url"] = payment.authorization_url
        
        if payment.status == "success":
            response["paid_at"] = payment.paid_at.isoformat() if payment.paid_at else None
            response["message"] = "Payment completed successfully"
            response["immediate_transfers_processed"] = payment.immediate_transfers_processed
        
        return response
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR CHECKING PAYMENT STATUS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check payment status"
        )

@router.get("/status")
async def get_payment_system_status():
    """
    Get payment system status and configuration
    PRODUCTION LIVE MODE
    """
    try:
        payment_service = PaymentService()
        balance_check = payment_service.check_balance()
        
        from app.services.immediate_transfer import ImmediateTransferService
        transfer_service = ImmediateTransferService()
        transfer_balance = await transfer_service.check_transfer_balance()
        
        return {
            "status": "success",
            "system": {
                "environment": "PRODUCTION LIVE",
                "paystack_mode": "LIVE",
                "paystack_public_key": f"{settings.PAYSTACK_PUBLIC_KEY[:15]}...",
                "paystack_secret_key": f"{settings.PAYSTACK_SECRET_KEY[:15]}...",
                "frontend_url": settings.FRONTEND_URL,
                "native_split_enabled": True,
                "transfer_retry_attempts": settings.TRANSFER_RETRY_ATTEMPTS,
                "transfer_retry_delay": settings.TRANSFER_RETRY_DELAY
            },
            "payment_config": {
                "regular_fee": settings.REGULAR_APPLICATION_FEE,
                "vip_fee": settings.VIP_APPLICATION_FEE,
                "marshal_core_share_percentage": settings.MARSHAL_CORE_SHARE_PERCENTAGE,
                "systems_maintainance_percentage": settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE,
                "estech_digital_systems_limited_percentage": settings.ESTECH_COMMISSION_PERCENTAGE
            },
            "balance": {
                "paystack": balance_check,
                "transfer_balance": transfer_balance
            },
            "status_message": "✅✅✅ PAYMENT SYSTEM IS OPERATIONAL - PRODUCTION LIVE MODE WITH NATIVE SPLIT",
            "notes": [
                "🚀 REAL MONEY TRANSACTIONS ONLY",
                f"💰 MarshalCoreShare: {settings.MARSHAL_CORE_SHARE_PERCENTAGE}%",
                f"💰 SystemsMaintainance: {settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%",
                f"💰 eSTechDigitalSystemsLimited: {settings.ESTECH_COMMISSION_PERCENTAGE}%",
                "⚡ Paystack Native Split: ENABLED (Automatic split at payment time)",
                "🔒 Secured with Paystack LIVE API"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING SYSTEM STATUS: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "environment": "PRODUCTION LIVE"
        }