# app/routes/payment.py - PRODUCTION LIVE MODE VERSION
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

# Account details for immediate transfers (PRODUCTION LIVE MODE)
IMMEDIATE_TRANSFER_CONFIG = {
    "director_general": {
        "account_name": settings.DG_ACCOUNT_NAME,
        "account_number": settings.DG_ACCOUNT_NUMBER,
        "bank": settings.DG_BANK_NAME,
        "bank_code": settings.DG_BANK_CODE,
        "recipient_type": "director_general",
        "description": "Director General - Immediate 35% Share"
    },
    "estech_system": {
        "account_name": "AUTHOR WISDOM GODWIN",  # Actual beneficiary
        "account_number": settings.ESTECH_BANK_ACCOUNT_NUMBER,
        "bank": settings.ESTECH_BANK_NAME,
        "bank_code": "100",  # OPay bank code
        "recipient_type": "estech_system",
        "description": settings.ESTECH_COMMISSION_PURPOSE
    }
}

# Payment configurations for PRODUCTION LIVE MODE
PAYMENT_CONFIGS = {
    "regular": {
        "user_amount": settings.REGULAR_APPLICATION_FEE,
        "display": f"₦{settings.REGULAR_APPLICATION_FEE:,} Regular Application Fee",
        "base_amount": 5000,
        "immediate_transfers": True,
        
        "recipients": {
            "director_general": {
                "percentage": settings.DG_SHARE_PERCENTAGE,
                "amount": int(settings.REGULAR_APPLICATION_FEE * (settings.DG_SHARE_PERCENTAGE / 100)),
                "transfer_type": "immediate",
                "description": "Director General Share"
            },
            "estech_system": {
                "percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "amount": int(settings.REGULAR_APPLICATION_FEE * (settings.ESTECH_COMMISSION_PERCENTAGE / 100)),
                "transfer_type": "immediate",
                "description": settings.ESTECH_COMMISSION_PURPOSE
            }
        },
        
        "marshal_core": {
            "percentage": settings.MARSHAL_SHARE_PERCENTAGE,
            "gross_amount": int(settings.REGULAR_APPLICATION_FEE * (settings.MARSHAL_SHARE_PERCENTAGE / 100)),
            "estimated_paystack_fees": 177.70,
            "estimated_transfer_fees": 20,
            "estimated_net": 2392.30
        },
        
        "user_message": f"Pay ₦{settings.REGULAR_APPLICATION_FEE:,} Application Fee",
        "receipt_description": "Marshal Core Nigeria - Regular Application Fee",
        "category": "regular_application"
    },
    
    "vip": {
        "user_amount": settings.VIP_APPLICATION_FEE,
        "display": f"₦{settings.VIP_APPLICATION_FEE:,} VIP Application Fee",
        "base_amount": 25000,
        "immediate_transfers": True,
        
        "recipients": {
            "director_general": {
                "percentage": settings.DG_SHARE_PERCENTAGE,
                "amount": int(settings.VIP_APPLICATION_FEE * (settings.DG_SHARE_PERCENTAGE / 100)),
                "transfer_type": "immediate"
            },
            "estech_system": {
                "percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "amount": int(settings.VIP_APPLICATION_FEE * (settings.ESTECH_COMMISSION_PERCENTAGE / 100)),
                "transfer_type": "immediate"
            }
        },
        
        "marshal_core": {
            "percentage": settings.MARSHAL_SHARE_PERCENTAGE,
            "gross_amount": int(settings.VIP_APPLICATION_FEE * (settings.MARSHAL_SHARE_PERCENTAGE / 100)),
            "estimated_paystack_fees": 877,
            "estimated_transfer_fees": 20,
            "estimated_net": 12053
        },
        
        "user_message": f"Pay ₦{settings.VIP_APPLICATION_FEE:,} VIP Application Fee",
        "receipt_description": "Marshal Core Nigeria - VIP Application Fee",
        "category": "vip_application"
    },
    
    "existing_officer": {
        "user_amount": 0,
        "display": "Free Registration",
        "immediate_transfers": False,
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
                "immediate_transfers": config.get("immediate_transfers", False) and settings.ENABLE_IMMEDIATE_TRANSFERS,
                
                "recipients": {
                    "director_general": {
                        **config["recipients"]["director_general"],
                        "account_details": IMMEDIATE_TRANSFER_CONFIG["director_general"]
                    },
                    "estech_system": {
                        **config["recipients"]["estech_system"],
                        "account_details": IMMEDIATE_TRANSFER_CONFIG["estech_system"]
                    }
                } if config.get("immediate_transfers") and settings.ENABLE_IMMEDIATE_TRANSFERS else {},
                
                "marshal_core": config.get("marshal_core", {}),
                
                "fees": {
                    "paystack_processing": config.get("marshal_core", {}).get("estimated_paystack_fees", 0),
                    "transfer_fees": config.get("marshal_core", {}).get("estimated_transfer_fees", 0),
                    "marshal_net": config.get("marshal_core", {}).get("estimated_net", 0)
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
                is_test_payment=False,  # Always false in production
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
            
            payment_response = payment_service.initiate_payment(
                email=payment_data.email,
                amount=config["user_amount"],
                reference=payment_ref,
                metadata=payment_metadata,
                callback_url=callback_url
            )
            
            if payment_response.get("status") != "success" or not payment_response.get("authorization_url"):
                error_msg = payment_response.get("message", "Payment initialization failed")
                logger.error(f"❌❌❌ PRODUCTION PAYMENT INITIALIZATION ERROR: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize payment: {error_msg}"
                )
            
            payment = Payment(
                id=str(uuid.uuid4()),
                user_email=payment_data.email.lower(),
                user_type=user_type_str,
                amount=config["user_amount"],
                payment_type=payment_type_str,
                status="pending",
                payment_reference=payment_ref,
                authorization_url=payment_response.get("authorization_url"),
                access_code=payment_response.get("access_code"),
                payment_metadata=payment_metadata,
                
                director_general_share=config["recipients"]["director_general"]["amount"],
                estech_system_share=config["recipients"]["estech_system"]["amount"],
                marshal_net_amount=config["marshal_core"]["estimated_net"],
                
                immediate_transfers_processed=False,
                is_test_payment=False,  # Always false in production
                transfer_metadata=None
            )
            db.add(payment)
            db.commit()
            
            logger.info(f"✅✅✅ PRODUCTION PAYMENT INITIALIZED: {payment_ref} for {payment_data.email}")
            
            return {
                "status": "success",
                "message": "Payment initialized",
                "payment_reference": payment_ref,
                "authorization_url": payment_response.get("authorization_url"),
                "amount": config["user_amount"],
                "amount_display": f"₦{config['user_amount']:,}",
                "user_message": config["user_message"],
                "payment_type": payment_type_str,
                "environment": "PRODUCTION LIVE",
                "immediate_transfers_enabled": config.get("immediate_transfers", False) and settings.ENABLE_IMMEDIATE_TRANSFERS
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
    Verify payment and trigger immediate transfers
    PRODUCTION LIVE MODE - Real money verification
    """
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        
        payment_service = PaymentService()
        transfer_service = ImmediateTransferService()
        
        # Query by payment_reference
        payment = db.query(Payment).filter(
            Payment.payment_reference == reference
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        # Check if already verified
        if payment.status == "success":
            logger.info(f"💰 Payment {reference} already verified")
            return {
                "status": "success",
                "message": "Payment already verified",
                "payment_reference": reference,
                "amount": f"₦{payment.amount:,}",
                "environment": "PRODUCTION LIVE"
            }
        
        # Verify payment with Paystack PRODUCTION
        logger.info(f"💰💰💰 VERIFYING PRODUCTION PAYMENT: {reference}")
        verification = payment_service.verify_payment(reference)
        
        if verification.get("status") == "success":
            # Update payment status
            payment.status = "success"
            payment.paid_at = datetime.utcnow()
            payment.verification_data = verification
            
            db.commit()
            db.refresh(payment)
            
            logger.info(f"✅✅✅ PRODUCTION PAYMENT VERIFIED SUCCESSFULLY: {reference}")
            logger.info(f"💰💰💰 AMOUNT: ₦{payment.amount:,} - MODE: PRODUCTION LIVE")
            
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
            
            # Process immediate transfers if enabled and amount > 0
            if payment.amount > 0 and settings.ENABLE_IMMEDIATE_TRANSFERS:
                try:
                    config = PAYMENT_CONFIGS.get(payment.payment_type, {})
                    
                    if config.get("immediate_transfers", False):
                        logger.info(f"💰💰💰 QUEUING IMMEDIATE TRANSFERS FOR: {reference}")
                        background_tasks.add_task(
                            transfer_service.process_immediate_splits,
                            payment_reference=reference,
                            payment_amount=payment.amount,
                            db=db
                        )
                        logger.info(f"✅✅✅ IMMEDIATE TRANSFERS QUEUED FOR: {reference}")
                except Exception as transfer_error:
                    logger.error(f"❌❌❌ FAILED TO QUEUE IMMEDIATE TRANSFERS: {str(transfer_error)}")
            
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
                "payment_reference": reference,
                "amount": f"₦{payment.amount:,}",
                "payment_date": payment.paid_at.isoformat() if payment.paid_at else None,
                "environment": "PRODUCTION LIVE",
                "immediate_transfers_queued": settings.ENABLE_IMMEDIATE_TRANSFERS
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
    Paystack webhook callback - triggers immediate transfers
    PRODUCTION LIVE MODE - Called by Paystack
    """
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        
        # Get the payload
        payload = await request.json()
        event = payload.get("event")
        data = payload.get("data", {})
        
        logger.info(f"💰💰💰 PAYSTACK PRODUCTION WEBHOOK RECEIVED: {event}")
        logger.info(f"💰💰💰 WEBHOOK DATA REFERENCE: {data.get('reference')}")
        
        # Verify webhook signature (recommended for production)
        # signature = request.headers.get('x-paystack-signature')
        # if not verify_signature(payload, signature):
        #     logger.error("Invalid webhook signature")
        #     return {"status": "error", "message": "Invalid signature"}
        
        if event == "charge.success":
            reference = data.get("reference")
            if reference:
                payment_service = PaymentService()
                verification = payment_service.verify_payment(reference)
                
                if verification.get("status") == "success":
                    payment = db.query(Payment).filter(
                        Payment.payment_reference == reference
                    ).first()
                    
                    if payment and payment.status != "success":
                        # Update payment
                        payment.status = "success"
                        payment.paid_at = datetime.utcnow()
                        payment.verification_data = verification
                        db.commit()
                        
                        logger.info(f"✅✅✅ PAYMENT PROCESSED VIA PRODUCTION WEBHOOK: {reference}")
                        
                        # Process immediate transfers
                        if payment.amount > 0 and settings.ENABLE_IMMEDIATE_TRANSFERS:
                            try:
                                transfer_service = ImmediateTransferService()
                                config = PAYMENT_CONFIGS.get(payment.payment_type, {})
                                
                                if config.get("immediate_transfers", False):
                                    logger.info(f"💰💰💰 PROCESSING IMMEDIATE TRANSFERS VIA WEBHOOK: {reference}")
                                    background_tasks.add_task(
                                        transfer_service.process_immediate_splits,
                                        payment_reference=reference,
                                        payment_amount=payment.amount,
                                        db=db
                                    )
                            except Exception as transfer_error:
                                logger.error(f"❌❌❌ WEBHOOK TRANSFER ERROR: {str(transfer_error)}")
                        
                        # Process post-payment
                        background_tasks.add_task(
                            process_post_payment,
                            user_email=payment.user_email,
                            user_type=payment.user_type,
                            payment_type=payment.payment_type,
                            db=db
                        )
                        
                        logger.info(f"✅✅✅ PRODUCTION WEBHOOK PROCESSING COMPLETE FOR {reference}")
        
        elif event == "transfer.success":
            logger.info(f"✅✅✅ PRODUCTION TRANSFER SUCCESSFUL: {data.get('reference')}")
            # You can update transfer status here if needed
        
        elif event == "transfer.failed":
            logger.error(f"❌❌❌ PRODUCTION TRANSFER FAILED: {data.get('reference')}")
            # Handle failed transfers
        
        return {"status": "success", "message": "PRODUCTION webhook processed"}
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR PROCESSING PRODUCTION WEBHOOK: {str(e)}")
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
        total_dg = sum(t.amount for t in transfers if t.recipient_type == "director_general")
        total_estech = sum(t.amount for t in transfers if t.recipient_type == "estech_system")
        
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
                "director_general_total": f"₦{total_dg:,}",
                "estech_system_total": f"₦{total_estech:,}",
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
        
        if config.get("immediate_transfers", False) and payment.amount > 0:
            expected_transfers = [
                {
                    "recipient": "director_general",
                    "expected_amount": config["recipients"]["director_general"]["amount"],
                    "account": IMMEDIATE_TRANSFER_CONFIG["director_general"]
                },
                {
                    "recipient": "estech_system",
                    "expected_amount": config["recipients"]["estech_system"]["amount"],
                    "account": IMMEDIATE_TRANSFER_CONFIG["estech_system"]
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
                "is_test_payment": False,  # Always false in production
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
                    "transferred_at": t.transferred_at.isoformat() if t.transferred_at else None,
                    "is_test_mode": False  # Always false in production
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
                "is_test_payment": False,  # Always false in production
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
        
        # PRODUCTION LIVE MODE - No test payments
        live_payments = all_payments
        
        stats = {
            "overall": {
                "total_payments": len(all_payments),
                "live_payments": len(live_payments),
                "test_payments": 0,  # Always 0 in production
                "total_amount": sum(p.amount for p in all_payments),
                "live_amount": sum(p.amount for p in live_payments),
                "test_amount": 0,  # Always 0 in production
                "total_director_general": sum(p.director_general_share for p in all_payments),
                "total_estech_system": sum(p.estech_system_share for p in all_payments),
                "total_marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments),
                "average_payment": sum(p.amount for p in all_payments) / len(all_payments) if all_payments else 0
            },
            
            "by_type": {
                "regular": {
                    "count": len([p for p in all_payments if p.payment_type == "regular"]),
                    "live_count": len([p for p in live_payments if p.payment_type == "regular"]),
                    "test_count": 0,
                    "total": sum(p.amount for p in all_payments if p.payment_type == "regular"),
                    "director_general": sum(p.director_general_share for p in all_payments if p.payment_type == "regular"),
                    "estech_system": sum(p.estech_system_share for p in all_payments if p.payment_type == "regular"),
                    "marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "regular")
                },
                "vip": {
                    "count": len([p for p in all_payments if p.payment_type == "vip"]),
                    "live_count": len([p for p in live_payments if p.payment_type == "vip"]),
                    "test_count": 0,
                    "total": sum(p.amount for p in all_payments if p.payment_type == "vip"),
                    "director_general": sum(p.director_general_share for p in all_payments if p.payment_type == "vip"),
                    "estech_system": sum(p.estech_system_share for p in all_payments if p.payment_type == "vip"),
                    "marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "vip")
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
            live_day_payments = day_payments
            
            stats["daily_trend"][day_key] = {
                "count": len(day_payments),
                "live_count": len(live_day_payments),
                "test_count": 0,
                "total": sum(p.amount for p in day_payments),
                "live_total": sum(p.amount for p in live_day_payments),
                "test_total": 0,
                "director_general": sum(p.director_general_share for p in day_payments),
                "estech_system": sum(p.estech_system_share for p in day_payments),
                "marshal_net": sum(p.marshal_net_amount or 0 for p in day_payments)
            }
        
        # Monthly summary
        for payment in all_payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in stats["monthly_summary"]:
                    stats["monthly_summary"][month_key] = {
                        "count": 0,
                        "live_count": 0,
                        "test_count": 0,
                        "total": 0,
                        "live_total": 0,
                        "test_total": 0,
                        "director_general": 0,
                        "estech_system": 0,
                        "marshal_net": 0
                    }
                
                stats["monthly_summary"][month_key]["count"] += 1
                stats["monthly_summary"][month_key]["total"] += payment.amount
                stats["monthly_summary"][month_key]["director_general"] += payment.director_general_share
                stats["monthly_summary"][month_key]["estech_system"] += payment.estech_system_share
                stats["monthly_summary"][month_key]["marshal_net"] += (payment.marshal_net_amount or 0)
                
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
            "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS,
            "stats": stats,
            "notes": [
                "🚀 PRODUCTION LIVE MODE - REAL MONEY ONLY",
                f"💰 Regular Application Fee: ₦{settings.REGULAR_APPLICATION_FEE:,}",
                f"💰 VIP Application Fee: ₦{settings.VIP_APPLICATION_FEE:,}",
                f"🎯 DG Share: {settings.DG_SHARE_PERCENTAGE}%",
                f"🎯 eSTech Share: {settings.ESTECH_COMMISSION_PERCENTAGE}%",
                f"🎯 Marshal Core Share: {settings.MARSHAL_SHARE_PERCENTAGE}%",
                f"⚡ Immediate Transfers: {'ENABLED' if settings.ENABLE_IMMEDIATE_TRANSFERS else 'DISABLED'}"
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
                    "dg_share": f"{settings.DG_SHARE_PERCENTAGE}%",
                    "estech_share": f"{settings.ESTECH_COMMISSION_PERCENTAGE}%",
                    "marshal_share": f"{settings.MARSHAL_SHARE_PERCENTAGE}%"
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
                    "dg_share": f"{settings.DG_SHARE_PERCENTAGE}%",
                    "estech_share": f"{settings.ESTECH_COMMISSION_PERCENTAGE}%",
                    "marshal_share": f"{settings.MARSHAL_SHARE_PERCENTAGE}%"
                }
            }
        },
        "notes": "🚀 PRODUCTION LIVE MODE - All payments are processed securely via Paystack LIVE with immediate fund distribution"
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
            "is_test_payment": False,  # Always false in production
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
                "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS,
                "transfer_retry_attempts": settings.TRANSFER_RETRY_ATTEMPTS,
                "transfer_retry_delay": settings.TRANSFER_RETRY_DELAY
            },
            "payment_config": {
                "regular_fee": settings.REGULAR_APPLICATION_FEE,
                "vip_fee": settings.VIP_APPLICATION_FEE,
                "dg_share_percentage": settings.DG_SHARE_PERCENTAGE,
                "estech_share_percentage": settings.ESTECH_COMMISSION_PERCENTAGE,
                "marshal_share_percentage": settings.MARSHAL_SHARE_PERCENTAGE
            },
            "balance": {
                "paystack": balance_check,
                "transfer_balance": transfer_balance
            },
            "status_message": "✅✅✅ PAYMENT SYSTEM IS OPERATIONAL - PRODUCTION LIVE MODE",
            "notes": [
                "🚀 REAL MONEY TRANSACTIONS ONLY",
                "💰 Immediate transfers active",
                "🔒 Secured with Paystack LIVE API",
                "⚡ Ready for production traffic"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR GETTING SYSTEM STATUS: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "environment": "PRODUCTION LIVE"
        }