# app/routes/payment.py - COMPLETE UPDATED VERSION WITH ALL FIXES
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

# Account details for immediate transfers (INTERNAL USE ONLY)
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
        "account_name": settings.ESTECH_BANK_ACCOUNT_NAME,
        "account_number": settings.ESTECH_BANK_ACCOUNT_NUMBER,
        "bank": settings.ESTECH_BANK_NAME,
        "bank_code": "100",
        "recipient_type": "estech_system",
        "description": settings.ESTECH_COMMISSION_PURPOSE
    }
}

# Updated payment configurations with immediate transfers
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
    User pays exact amount, splits happen automatically after payment
    """
    try:
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
            logger.info(f"Payment initiated for new user: {payment_data.email} ({user_type_str})")
        
        existing_payment = db.query(Payment).filter(
            Payment.user_email == payment_data.email.lower(),
            Payment.user_type == user_type_str,
            Payment.payment_type == payment_type_str,
            Payment.status.in_(["pending", "success"])
        ).first()
        
        if existing_payment:
            if existing_payment.status == "success":
                return {
                    "status": "already_paid",
                    "message": "Payment already completed",
                    "payment_reference": existing_payment.payment_reference,
                    "amount": config["user_amount"],
                    "user_message": "Payment already completed"
                }
            else:
                return {
                    "status": "pending",
                    "message": "Payment already initiated",
                    "payment_reference": existing_payment.payment_reference,
                    "authorization_url": existing_payment.authorization_url,
                    "amount": config["user_amount"],
                    "user_message": "Continue with existing payment"
                }
        
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
        
        payment_metadata = {
            "user_info": user_info,
            "user_type": user_type_str,
            "email": payment_data.email.lower(),
            "payment_type": payment_type_str,
            
            "split_config": {
                "user_paid": config["user_amount"],
                "immediate_transfers": config.get("immediate_transfers", False),
                
                "recipients": {
                    "director_general": {
                        **config["recipients"]["director_general"],
                        "account_details": IMMEDIATE_TRANSFER_CONFIG["director_general"]
                    },
                    "estech_system": {
                        **config["recipients"]["estech_system"],
                        "account_details": IMMEDIATE_TRANSFER_CONFIG["estech_system"]
                    }
                } if config.get("immediate_transfers") else {},
                
                "marshal_core": config.get("marshal_core", {}),
                
                "fees": {
                    "paystack_processing": config.get("marshal_core", {}).get("estimated_paystack_fees", 0),
                    "transfer_fees": config.get("marshal_core", {}).get("estimated_transfer_fees", 0),
                    "marshal_net": config.get("marshal_core", {}).get("estimated_net", 0)
                }
            },
            
            "category": config["category"],
            "payment_date": datetime.now().isoformat()
        }
        
        payment_service = PaymentService()
        
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
                paid_at=datetime.utcnow()
            )
            db.add(payment)
            db.commit()
            
            return {
                "status": "success",
                "message": "Registration completed successfully",
                "payment_reference": payment_ref,
                "amount": 0,
                "user_message": config["user_message"]
            }
        else:
            # Use the callback URL from settings
            callback_url = None
            if hasattr(settings, 'PAYMENT_SUCCESS_URL') and hasattr(settings, 'FRONTEND_URL'):
                callback_url = f"{settings.FRONTEND_URL}{settings.PAYMENT_SUCCESS_URL}"
            else:
                # Fallback to a sensible default
                callback_url = f"http://localhost:8000/api/payments/verify/{payment_ref}"
            
            payment_response = payment_service.initiate_payment(
                email=payment_data.email,
                amount=config["user_amount"],
                reference=payment_ref,
                metadata=payment_metadata,
                callback_url=callback_url
            )
            
            if payment_response.get("status") != "success" or not payment_response.get("authorization_url"):
                error_msg = payment_response.get("message", "Payment initialization failed")
                logger.error(f"Payment initialization error: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=error_msg
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
                transfer_metadata=None
            )
            db.add(payment)
            db.commit()
            
            return {
                "status": "success",
                "message": "Payment initialized",
                "payment_reference": payment_ref,
                "authorization_url": payment_response.get("authorization_url"),
                "amount": config["user_amount"],
                "amount_display": f"₦{config['user_amount']:,}",
                "user_message": config["user_message"],
                "payment_type": payment_type_str,
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate payment: {str(e)}"
        )

@router.post("/verify/{reference}")
async def verify_payment(
    reference: str,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Verify payment and trigger immediate transfers
    """
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        
        payment_service = PaymentService()
        transfer_service = ImmediateTransferService()
        
        # Query by payment_reference (string) not id
        payment = db.query(Payment).filter(
            Payment.payment_reference == reference
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )
        
        if payment.status == "success":
            return {
                "status": "success",
                "message": "Payment already verified",
                "payment_reference": reference,
                "amount": f"₦{payment.amount:,}"
            }
        
        verification = payment_service.verify_payment(reference)
        
        if verification.get("status") == "success":
            # Update the payment object directly
            payment.status = "success"
            payment.paid_at = datetime.utcnow()
            payment.verification_data = verification
            
            # Just commit the changes to the object we already have
            db.commit()
            db.refresh(payment)
            
            logger.info(f"Payment {reference} verified successfully, ID: {payment.id}")
            
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
                    
                    # Promote to applicant
                    try:
                        await promote_to_applicant(payment.user_email, db)
                    except Exception as e:
                        logger.error(f"Error promoting pre-applicant: {e}")
            
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
            
            # Process immediate transfers if applicable
            if payment.amount > 0:
                try:
                    config = PAYMENT_CONFIGS.get(payment.payment_type, {})
                    
                    if config.get("immediate_transfers", False):
                        if background_tasks:
                            background_tasks.add_task(
                                transfer_service.process_immediate_splits,
                                payment_reference=reference,
                                payment_amount=payment.amount,
                                db=db
                            )
                            logger.info(f"Immediate transfers queued for {reference}")
                        else:
                            # Run synchronously if no background tasks
                            await transfer_service.process_immediate_splits(
                                payment_reference=reference,
                                payment_amount=payment.amount,
                                db=db
                            )
                except Exception as transfer_error:
                    logger.error(f"Failed to queue immediate transfers: {str(transfer_error)}")
            
            # Process post-payment tasks
            if background_tasks:
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
            }
        else:
            payment.status = "failed"
            db.commit()
            
            raise HTTPException(
                status_code=400,
                detail="Payment verification failed"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}", exc_info=True)
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
    """
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        
        payload = await request.json()
        logger.info(f"Paystack callback received: {payload.get('event')}")
        
        event = payload.get("event")
        data = payload.get("data", {})
        
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
                        payment.status = "success"
                        payment.paid_at = datetime.utcnow()
                        payment.verification_data = verification
                        db.commit()
                        
                        if payment.amount > 0:
                            try:
                                transfer_service = ImmediateTransferService()
                                config = PAYMENT_CONFIGS.get(payment.payment_type, {})
                                
                                if config.get("immediate_transfers", False):
                                    background_tasks.add_task(
                                        transfer_service.process_immediate_splits,
                                        payment_reference=reference,
                                        payment_amount=payment.amount,
                                        db=db
                                    )
                            except Exception as transfer_error:
                                logger.error(f"Failed to queue transfers in webhook: {str(transfer_error)}")
                        
                        await process_post_payment(
                            user_email=payment.user_email,
                            user_type=payment.user_type,
                            payment_type=payment.payment_type,
                            db=db
                        )
                        
                        logger.info(f"Payment {reference} processed via webhook with immediate transfers")
        
        return {"status": "success", "message": "Callback processed"}
        
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
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
    """
    try:
        from app.models.immediate_transfer import ImmediateTransfer
        
        query = db.query(ImmediateTransfer)
        
        if status:
            query = query.filter(ImmediateTransfer.status == status)
        if start_date:
            query = query.filter(ImmediateTransfer.transferred_at >= start_date)
        if end_date:
            query = query.filter(ImmediateTransfer.transferred_at <= end_date)
        
        transfers = query.order_by(desc(ImmediateTransfer.transferred_at)).all()
        
        total_amount = sum(t.amount for t in transfers)
        total_dg = sum(t.amount for t in transfers if t.recipient_type == "director_general")
        total_estech = sum(t.amount for t in transfers if t.recipient_type == "estech_system")
        
        return {
            "status": "success",
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
                    "bank": t.recipient_bank
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
        logger.error(f"Error getting transfer history: {str(e)}")
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
            "payment": {
                "reference": payment.payment_reference,
                "amount": f"₦{payment.amount:,}",
                "type": payment.payment_type,
                "status": payment.status,
                "immediate_transfers_processed": payment.immediate_transfers_processed
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
        logger.error(f"Error getting transfer status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get transfer status"
        )

@router.post("/manual/confirm")
async def manual_payment(data: ManualPaymentRequest, db: Session = Depends(get_db)):
    """Legacy endpoint - forward to new payment system"""
    payment_data = PaymentCreate(
        email=data.email,
        payment_type="regular",
        user_type="pre_applicant"
    )
    return await initiate_payment(payment_data, db)

@router.post("/paystack/verify")
async def paystack_verify(data: GatewayCallback, db: Session = Depends(get_db)):
    """Legacy endpoint"""
    return await verify_payment(data.reference, db)

@router.get("/user/{email}")
async def get_user_payments(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Get payment history for a user
    Returns SIMPLE info (no split details)
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
                "description": "Application Fee" if payment.payment_type in ["regular", "vip"] else "Registration"
            })
        
        return {
            "status": "success",
            "email": email,
            "payments": user_payments,
            "total_count": len(user_payments)
        }
        
    except Exception as e:
        logger.error(f"Error getting user payments: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get payment history"
        )

@router.get("/admin/estech-balance")
async def get_estech_balance(
    db: Session = Depends(get_db),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[str] = None
):
    """
    ADMIN ONLY: Get eSTech System accumulated commission
    This is INTERNAL and NOT exposed to users
    """
    try:
        query = db.query(Payment).filter(
            Payment.status == "success",
            Payment.estech_system_share > 0
        )
        
        if month:
            query = query.filter(
                db.func.strftime('%Y-%m', Payment.paid_at) == month
            )
        elif start_date:
            query = query.filter(Payment.paid_at >= start_date)
            if end_date:
                query = query.filter(Payment.paid_at <= end_date)
        
        payments = query.order_by(desc(Payment.paid_at)).all()
        
        total_estech = sum(p.estech_system_share for p in payments)
        total_dg = sum(p.director_general_share for p in payments)
        total_amount = sum(p.amount for p in payments)
        
        monthly_data = {}
        for payment in payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "estech_total": 0,
                        "dg_total": 0,
                        "payment_count": 0,
                        "payments": []
                    }
                
                monthly_data[month_key]["estech_total"] += payment.estech_system_share
                monthly_data[month_key]["dg_total"] += payment.director_general_share
                monthly_data[month_key]["payment_count"] += 1
                monthly_data[month_key]["payments"].append({
                    "reference": payment.payment_reference,
                    "date": payment.paid_at.isoformat(),
                    "applicant": payment.user_email,
                    "type": payment.payment_type,
                    "total": f"₦{payment.amount:,}",
                    "estech_share": f"₦{payment.estech_system_share:,}",
                    "dg_share": f"₦{payment.director_general_share:,}"
                })
        
        current_month = datetime.now().strftime("%Y-%m")
        current_month_estech = monthly_data.get(current_month, {"estech_total": 0})["estech_total"]
        current_month_dg = monthly_data.get(current_month, {"dg_total": 0})["dg_total"]
        
        return {
            "status": "success",
            "company": settings.ESTECH_COMPANY_NAME,
            "bank_details": {
                "account_name": settings.ESTECH_BANK_ACCOUNT_NAME,
                "account_number": settings.ESTECH_BANK_ACCOUNT_NUMBER,
                "bank": settings.ESTECH_BANK_NAME,
                "beneficiary": settings.ESTECH_ACTUAL_BENEFICIARY
            },
            "commission_rate": f"{settings.ESTECH_COMMISSION_PERCENTAGE}% of all application fees",
            "purpose": settings.ESTECH_COMMISSION_PURPOSE,
            
            "totals": {
                "all_time": {
                    "estech_balance": f"₦{total_estech:,}",
                    "director_general_balance": f"₦{total_dg:,}",
                    "total_processed": f"₦{total_amount:,}",
                    "payment_count": len(payments)
                },
                "current_month": {
                    "month": current_month,
                    "estech_balance": f"₦{current_month_estech:,}",
                    "dg_balance": f"₦{current_month_dg:,}",
                    "payment_count": monthly_data.get(current_month, {"payment_count": 0})["payment_count"]
                }
            },
            
            "monthly_breakdown": {
                month: {
                    "estech_total": f"₦{data['estech_total']:,}",
                    "dg_total": f"₦{data['dg_total']:,}",
                    "payment_count": data["payment_count"],
                    "status": "immediate_transfer"
                }
                for month, data in monthly_data.items()
            },
            
            "recent_payments": [
                {
                    "date": p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "N/A",
                    "applicant": p.user_email,
                    "type": p.payment_type.upper(),
                    "total": f"₦{p.amount:,}",
                    "estech_commission": f"₦{p.estech_system_share:,}",
                    "dg_share": f"₦{p.director_general_share:,}",
                    "purpose": settings.ESTECH_COMMISSION_PURPOSE,
                    "reference": p.payment_reference,
                    "immediate_transfer": p.immediate_transfers_processed
                }
                for p in payments[:10]
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting eSTech balance: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get eSTech System balance"
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
    Shows split between recipients
    """
    try:
        query = db.query(Payment).filter(Payment.status == "success")
        
        if start_date:
            query = query.filter(Payment.paid_at >= start_date)
        if end_date:
            query = query.filter(Payment.paid_at <= end_date)
        
        all_payments = query.all()
        
        stats = {
            "overall": {
                "total_payments": len(all_payments),
                "total_amount": sum(p.amount for p in all_payments),
                "total_director_general": sum(p.director_general_share for p in all_payments),
                "total_estech_system": sum(p.estech_system_share for p in all_payments),
                "total_marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments),
                "average_payment": sum(p.amount for p in all_payments) / len(all_payments) if all_payments else 0
            },
            
            "by_type": {
                "regular": {
                    "count": len([p for p in all_payments if p.payment_type == "regular"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "regular"),
                    "director_general": sum(p.director_general_share for p in all_payments if p.payment_type == "regular"),
                    "estech_system": sum(p.estech_system_share for p in all_payments if p.payment_type == "regular"),
                    "marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "regular")
                },
                "vip": {
                    "count": len([p for p in all_payments if p.payment_type == "vip"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "vip"),
                    "director_general": sum(p.director_general_share for p in all_payments if p.payment_type == "vip"),
                    "estech_system": sum(p.estech_system_share for p in all_payments if p.payment_type == "vip"),
                    "marshal_net": sum(p.marshal_net_amount or 0 for p in all_payments if p.payment_type == "vip")
                }
            },
            
            "daily_trend": {},
            "monthly_summary": {}
        }
        
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
            
            stats["daily_trend"][day_key] = {
                "count": len(day_payments),
                "total": sum(p.amount for p in day_payments),
                "director_general": sum(p.director_general_share for p in day_payments),
                "estech_system": sum(p.estech_system_share for p in day_payments),
                "marshal_net": sum(p.marshal_net_amount or 0 for p in day_payments)
            }
        
        for payment in all_payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in stats["monthly_summary"]:
                    stats["monthly_summary"][month_key] = {
                        "count": 0,
                        "total": 0,
                        "director_general": 0,
                        "estech_system": 0,
                        "marshal_net": 0
                    }
                
                stats["monthly_summary"][month_key]["count"] += 1
                stats["monthly_summary"][month_key]["total"] += payment.amount
                stats["monthly_summary"][month_key]["director_general"] += payment.director_general_share
                stats["monthly_summary"][month_key]["estech_system"] += payment.estech_system_share
                stats["monthly_summary"][month_key]["marshal_net"] += (payment.marshal_net_amount or 0)
        
        def format_currency(amount):
            return f"₦{amount:,.2f}" if isinstance(amount, (int, float)) else amount
        
        for key in ["overall", "by_type"]:
            if key == "overall":
                for subkey in ["total_amount", "total_director_general", "total_estech_system", "total_marshal_net", "average_payment"]:
                    if subkey in stats[key]:
                        stats[key][subkey + "_formatted"] = format_currency(stats[key][subkey])
            elif key == "by_type":
                for type_key in ["regular", "vip"]:
                    if type_key in stats[key]:
                        for subkey in ["total", "director_general", "estech_system", "marshal_net"]:
                            if subkey in stats[key][type_key]:
                                stats[key][type_key][subkey + "_formatted"] = format_currency(stats[key][type_key][subkey])
        
        return {
            "status": "success",
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "stats": stats,
            "immediate_transfer_config": IMMEDIATE_TRANSFER_CONFIG,
            "notes": [
                f"Immediate transfers enabled: {settings.DG_SHARE_PERCENTAGE}% to Director General, {settings.ESTECH_COMMISSION_PERCENTAGE}% to eSTech System",
                "Marshal Core bears all transaction fees and receives remainder",
                "All transfers happen automatically after successful payment",
                "All amounts are in Nigerian Naira (₦)"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting payment stats: {str(e)}", exc_info=True)
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
            "payment_reference": payment_reference
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error queuing transfer retry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to queue transfer retry"
        )

@router.get("/types")
async def get_payment_types():
    """
    Get available payment types
    Returns SIMPLE info for frontend display
    """
    return {
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
                ]
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
                ]
            }
        },
        "notes": "All payments are processed securely via Paystack with immediate fund distribution"
    }

@router.get("/check/{email}")
async def check_payment_status(
    email: str,
    payment_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Check payment status for a user
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
                "message": "No payment found for this user"
            }
        
        response = {
            "status": payment.status,
            "payment_reference": payment.payment_reference,
            "amount": f"₦{payment.amount:,}",
            "payment_type": payment.payment_type,
            "created_at": payment.created_at.isoformat() if payment.created_at else None
        }
        
        if payment.status == "pending" and payment.authorization_url:
            response["authorization_url"] = payment.authorization_url
        
        if payment.status == "success":
            response["paid_at"] = payment.paid_at.isoformat() if payment.paid_at else None
            response["message"] = "Payment completed successfully"
            response["immediate_transfers_processed"] = payment.immediate_transfers_processed
        
        return response
        
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check payment status"
        )