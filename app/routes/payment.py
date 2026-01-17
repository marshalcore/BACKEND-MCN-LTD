# app/routes/payment.py
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta

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
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"]
)

# eSTech System bank details (INTERNAL USE ONLY)
ESTECH_BANK_DETAILS = {
    "account_name": "eSTech System",  # Display name on receipts
    "account_number": "8030903037",
    "bank": "Opay",
    "beneficiary_name": "Godwin Wisdom Author",  # Actual account holder
    "description": "Technical Support & Software Development Services"
}

# Payment configurations - eSTech System gets 15% for technical services
PAYMENT_CONFIGS = {
    "regular": {
        "amount": 5000,  # ₦5,000
        "description": "Marshal Core Regular Application Fee",
        "estech_percentage": 15,  # 15% to eSTech System
        "estech_amount": 750,  # ₦750 (15% of ₦5,000)
        "marshal_amount": 4250,  # ₦4,250 (85% of ₦5,000)
        "category": "regular_application",
        "receipt_description": "Marshal Core Nigeria - Regular Application Fee",
        "user_message": "Pay ₦5,000 Application Fee"
    },
    "vip": {
        "amount": 15000,  # ₦15,000
        "description": "Marshal Core VIP Application Fee",
        "estech_percentage": 15,  # 15% to eSTech System
        "estech_amount": 2250,  # ₦2,250 (15% of ₦15,000)
        "marshal_amount": 12750,  # ₦12,750 (85% of ₦15,000)
        "category": "vip_application",
        "receipt_description": "Marshal Core Nigeria - VIP Application Fee",
        "user_message": "Pay ₦15,000 VIP Application Fee"
    },
    "existing_officer": {
        "amount": 0,  # Free for existing officers
        "description": "Marshal Core Existing Officer Registration",
        "estech_percentage": 0,
        "estech_amount": 0,
        "marshal_amount": 0,
        "category": "existing_officer",
        "receipt_description": "Marshal Core Nigeria - Officer Registration",
        "user_message": "Free Registration"
    }
}

@router.post("/initiate")
async def initiate_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db)
):
    """
    Initiate payment for applicant (Regular or VIP)
    
    IMPORTANT: User ONLY sees simple payment amount
    NO mention of eSTech System or split payments!
    """
    try:
        # Validate payment type
        if payment_data.payment_type not in PAYMENT_CONFIGS:
            raise HTTPException(
                status_code=400,
                detail="Invalid payment type"
            )
        
        # Get payment config
        config = PAYMENT_CONFIGS[payment_data.payment_type]
        
        # Find user based on user_type
        user = None
        if payment_data.user_type == "applicant":
            user = db.query(Applicant).filter(
                func.lower(Applicant.email) == payment_data.email.lower()
            ).first()
        elif payment_data.user_type == "pre_applicant":
            user = db.query(PreApplicant).filter(
                func.lower(PreApplicant.email) == payment_data.email.lower()
            ).first()
        elif payment_data.user_type == "officer":
            user = db.query(Officer).filter(
                func.lower(Officer.email) == payment_data.email.lower()
            ).first()
        elif payment_data.user_type == "existing_officer":
            user = db.query(ExistingOfficer).filter(
                func.lower(ExistingOfficer.email) == payment_data.email.lower()
            ).first()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Check if payment already exists and is pending/success
        existing_payment = db.query(Payment).filter(
            Payment.user_email == payment_data.email.lower(),
            Payment.user_type == payment_data.user_type,
            Payment.payment_type == payment_data.payment_type,
            Payment.status.in_(["pending", "success"])
        ).first()
        
        if existing_payment:
            if existing_payment.status == "success":
                return {
                    "status": "already_paid",
                    "message": "Payment already completed",
                    "payment_reference": existing_payment.payment_reference,
                    "amount": config["amount"],
                    "user_message": "Payment already completed"
                }
            else:
                # Return existing pending payment
                return {
                    "status": "pending",
                    "message": "Payment already initiated",
                    "payment_reference": existing_payment.payment_reference,
                    "authorization_url": existing_payment.authorization_url,
                    "amount": config["amount"],
                    "user_message": "Continue with existing payment"
                }
        
        # Create payment reference
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        payment_ref = f"MCN_{payment_data.payment_type.upper()}_{timestamp}"
        
        # Prepare payment_metadata (INTERNAL USE ONLY - not shown to user)
        # CHANGED: metadata -> payment_metadata
        payment_metadata = {
            "user_id": str(getattr(user, 'id', '')),
            "user_type": payment_data.user_type,
            "full_name": getattr(user, 'full_name', ''),
            "email": payment_data.email.lower(),
            "payment_type": payment_data.payment_type,
            "split_details": {  # INTERNAL - not exposed to user
                "estech_percentage": config["estech_percentage"],
                "estech_amount": config["estech_amount"],
                "estech_purpose": "Technical Support & Software Development",
                "marshal_amount": config["marshal_amount"],
                "total_amount": config["amount"]
            },
            "estech_bank": ESTECH_BANK_DETAILS,  # INTERNAL - for admin payout tracking
            "category": config["category"],
            "payment_date": datetime.now().isoformat()
        }
        
        # Initialize payment
        payment_service = PaymentService()
        
        if config["amount"] == 0:
            # Free payment for existing officers
            payment = Payment(
                user_email=payment_data.email.lower(),
                user_type=payment_data.user_type,
                amount=0,
                payment_type=payment_data.payment_type,
                status="success",
                payment_reference=payment_ref,
                # CHANGED: metadata -> payment_metadata
                payment_metadata=payment_metadata,
                estech_share=0,
                marshal_share=0,
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
            # Paid payment - initiate with Paystack
            payment_response = payment_service.initiate_payment(
                email=payment_data.email,
                amount=config["amount"],
                reference=payment_ref,
                # CHANGED: metadata -> payment_metadata
                metadata=payment_metadata,  # Internal tracking only
                callback_url=f"{settings.FRONTEND_URL}{settings.PAYMENT_SUCCESS_URL}"
            )
            
            if not payment_response.get("authorization_url"):
                raise HTTPException(
                    status_code=500,
                    detail="Payment initialization failed"
                )
            
            # Save payment record with split tracking
            payment = Payment(
                user_email=payment_data.email.lower(),
                user_type=payment_data.user_type,
                amount=config["amount"],
                payment_type=payment_data.payment_type,
                status="pending",
                payment_reference=payment_ref,
                authorization_url=payment_response.get("authorization_url"),
                access_code=payment_response.get("access_code"),
                # CHANGED: metadata -> payment_metadata
                payment_metadata=payment_metadata,
                estech_share=config["estech_amount"],
                marshal_share=config["marshal_amount"]
            )
            db.add(payment)
            db.commit()
            
            # User ONLY sees simple payment info
            return {
                "status": "success",
                "message": "Payment initialized",
                "payment_reference": payment_ref,
                "authorization_url": payment_response.get("authorization_url"),
                "amount": config["amount"],
                "amount_display": f"₦{config['amount']:,}",
                "user_message": config["user_message"],  # Simple message for user
                "payment_type": payment_data.payment_type,
                # NO split info exposed to user!
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate payment"
        )

@router.post("/verify/{reference}")
async def verify_payment(
    reference: str,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Verify payment with Paystack
    Returns SIMPLE success message to user
    """
    try:
        payment_service = PaymentService()
        
        # Find payment record
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
        
        # Verify with Paystack
        verification = payment_service.verify_payment(reference)
        
        if verification.get("status") == "success":
            # Update payment status
            payment.status = "success"
            payment.paid_at = datetime.utcnow()
            payment.verification_data = verification
            db.commit()
            
            # Update user status based on user_type
            if payment.user_type == "pre_applicant":
                pre_applicant = db.query(PreApplicant).filter(
                    func.lower(PreApplicant.email) == payment.user_email
                ).first()
                
                if pre_applicant:
                    pre_applicant.has_paid = True
                    pre_applicant.status = "payment_completed"
                    db.commit()
                    
                    # Promote to applicant
                    promote_to_applicant(payment.user_email, db)
            
            elif payment.user_type == "applicant":
                applicant = db.query(Applicant).filter(
                    func.lower(Applicant.email) == payment.user_email
                ).first()
                
                if applicant:
                    applicant.payment_status = "paid"
                    applicant.payment_type = payment.payment_type
                    applicant.paid_at = datetime.utcnow()
                    db.commit()
            
            # Add background task for post-payment processing
            if background_tasks:
                background_tasks.add_task(
                    process_post_payment,
                    user_email=payment.user_email,
                    user_type=payment.user_type,
                    payment_type=payment.payment_type,
                    db=db
                )
            
            # SIMPLE success message for user
            return {
                "status": "success",
                "message": "Payment successful! You can now proceed with your application.",
                "payment_reference": reference,
                "amount": f"₦{payment.amount:,}",
                "payment_date": payment.paid_at.isoformat() if payment.paid_at else None,
                # NO split info shown to user!
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
        logger.error(f"Error verifying payment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Payment verification failed"
        )

@router.post("/callback/paystack")
async def paystack_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Paystack webhook callback (INTERNAL USE)
    """
    try:
        payload = await request.json()
        logger.info(f"Paystack callback received: {payload.get('event')}")
        
        event = payload.get("event")
        data = payload.get("data", {})
        
        if event == "charge.success":
            reference = data.get("reference")
            if reference:
                # Verify and process payment
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
                        
                        # Process post-payment
                        await process_post_payment(
                            user_email=payment.user_email,
                            user_type=payment.user_type,
                            payment_type=payment.payment_type,
                            db=db
                        )
                        
                        logger.info(f"Payment {reference} processed via webhook")
        
        return {"status": "success", "message": "Callback processed"}
        
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return {"status": "error", "message": str(e)}

# Legacy endpoints for backward compatibility
@router.post("/manual/confirm")
async def manual_payment(data: ManualPaymentRequest, db: Session = Depends(get_db)):
    """Legacy endpoint - forward to new payment system"""
    # Create payment for pre_applicant type
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
            Payment.estech_share > 0
        )
        
        # Date filtering
        if month:
            query = query.filter(
                db.func.strftime('%Y-%m', Payment.paid_at) == month
            )
        elif start_date:
            query = query.filter(Payment.paid_at >= start_date)
            if end_date:
                query = query.filter(Payment.paid_at <= end_date)
        
        payments = query.order_by(desc(Payment.paid_at)).all()
        
        total_balance = sum(p.estech_share for p in payments)
        total_marshal = sum(p.marshal_share for p in payments)
        total_amount = sum(p.amount for p in payments)
        
        # Group by month for payout tracking
        monthly_data = {}
        for payment in payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "estech_total": 0,
                        "payment_count": 0,
                        "payments": []
                    }
                
                monthly_data[month_key]["estech_total"] += payment.estech_share
                monthly_data[month_key]["payment_count"] += 1
                monthly_data[month_key]["payments"].append({
                    "reference": payment.payment_reference,
                    "date": payment.paid_at.isoformat(),
                    "applicant": payment.user_email,
                    "type": payment.payment_type,
                    "total": f"₦{payment.amount:,}",
                    "estech_share": f"₦{payment.estech_share:,}",
                    "marshal_share": f"₦{payment.marshal_share:,}"
                })
        
        # Current month balance
        current_month = datetime.now().strftime("%Y-%m")
        current_month_balance = monthly_data.get(current_month, {"estech_total": 0})["estech_total"]
        
        return {
            "status": "success",
            "company": "eSTech System",
            "bank_details": ESTECH_BANK_DETAILS,
            "commission_rate": "15% of all application fees",
            "purpose": "Technical Support & Software Development Services",
            
            "totals": {
                "all_time": {
                    "estech_balance": f"₦{total_balance:,}",
                    "marshal_balance": f"₦{total_marshal:,}",
                    "total_processed": f"₦{total_amount:,}",
                    "payment_count": len(payments)
                },
                "current_month": {
                    "month": current_month,
                    "estech_balance": f"₦{current_month_balance:,}",
                    "payment_count": monthly_data.get(current_month, {"payment_count": 0})["payment_count"]
                }
            },
            
            "monthly_breakdown": {
                month: {
                    "estech_total": f"₦{data['estech_total']:,}",
                    "payment_count": data["payment_count"],
                    "due_date": f"{month}-28",  # Payout at month end
                    "status": "pending_payout" if month != current_month else "accumulating"
                }
                for month, data in monthly_data.items()
            },
            
            "recent_payments": [
                {
                    "date": p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "N/A",
                    "applicant": p.user_email,
                    "type": p.payment_type.upper(),
                    "total": f"₦{p.amount:,}",
                    "estech_commission": f"₦{p.estech_share:,}",
                    "purpose": "Technical Support & Software Development",
                    "reference": p.payment_reference
                }
                for p in payments[:10]  # Last 10 payments
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
    period: Optional[str] = "month",  # day, week, month, year
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    ADMIN ONLY: Comprehensive payment statistics
    Shows split between eSTech System and Marshal Core
    """
    try:
        # Base query for successful payments
        query = db.query(Payment).filter(Payment.status == "success")
        
        # Apply date filters
        if start_date:
            query = query.filter(Payment.paid_at >= start_date)
        if end_date:
            query = query.filter(Payment.paid_at <= end_date)
        
        all_payments = query.all()
        
        # Calculate statistics
        stats = {
            "overall": {
                "total_payments": len(all_payments),
                "total_amount": sum(p.amount for p in all_payments),
                "total_estech": sum(p.estech_share for p in all_payments),
                "total_marshal": sum(p.marshal_share for p in all_payments),
                "average_payment": sum(p.amount for p in all_payments) / len(all_payments) if all_payments else 0
            },
            
            "by_type": {
                "regular": {
                    "count": len([p for p in all_payments if p.payment_type == "regular"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "regular"),
                    "estech": sum(p.estech_share for p in all_payments if p.payment_type == "regular"),
                    "marshal": sum(p.marshal_share for p in all_payments if p.payment_type == "regular")
                },
                "vip": {
                    "count": len([p for p in all_payments if p.payment_type == "vip"]),
                    "total": sum(p.amount for p in all_payments if p.payment_type == "vip"),
                    "estech": sum(p.estech_share for p in all_payments if p.payment_type == "vip"),
                    "marshal": sum(p.marshal_share for p in all_payments if p.payment_type == "vip")
                }
            },
            
            "daily_trend": {},
            "monthly_summary": {}
        }
        
        # Daily trend (last 30 days)
        end_date_obj = datetime.now()
        start_date_obj = end_date_obj - timedelta(days=30)
        
        daily_payments = db.query(Payment).filter(
            Payment.status == "success",
            Payment.paid_at >= start_date_obj,
            Payment.paid_at <= end_date_obj
        ).all()
        
        # Group by day
        for i in range(30):
            day = start_date_obj + timedelta(days=i)
            day_key = day.strftime("%Y-%m-%d")
            
            day_payments = [p for p in daily_payments if p.paid_at and p.paid_at.date() == day.date()]
            
            stats["daily_trend"][day_key] = {
                "count": len(day_payments),
                "total": sum(p.amount for p in day_payments),
                "estech": sum(p.estech_share for p in day_payments),
                "marshal": sum(p.marshal_share for p in day_payments)
            }
        
        # Monthly summary
        for payment in all_payments:
            if payment.paid_at:
                month_key = payment.paid_at.strftime("%Y-%m")
                if month_key not in stats["monthly_summary"]:
                    stats["monthly_summary"][month_key] = {
                        "count": 0,
                        "total": 0,
                        "estech": 0,
                        "marshal": 0
                    }
                
                stats["monthly_summary"][month_key]["count"] += 1
                stats["monthly_summary"][month_key]["total"] += payment.amount
                stats["monthly_summary"][month_key]["estech"] += payment.estech_share
                stats["monthly_summary"][month_key]["marshal"] += payment.marshal_share
        
        # Format currency
        def format_currency(amount):
            return f"₦{amount:,.2f}" if isinstance(amount, (int, float)) else amount
        
        # Format all currency values
        for key in ["overall", "by_type"]:
            if key == "overall":
                for subkey in ["total_amount", "total_estech", "total_marshal", "average_payment"]:
                    if subkey in stats[key]:
                        stats[key][subkey + "_formatted"] = format_currency(stats[key][subkey])
            elif key == "by_type":
                for type_key in ["regular", "vip"]:
                    if type_key in stats[key]:
                        for subkey in ["total", "estech", "marshal"]:
                            if subkey in stats[key][type_key]:
                                stats[key][type_key][subkey + "_formatted"] = format_currency(stats[key][type_key][subkey])
        
        return {
            "status": "success",
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "stats": stats,
            "estech_bank": ESTECH_BANK_DETAILS,
            "notes": [
                "eSTech System receives 15% commission for Technical Support & Software Development",
                "Payouts are processed monthly to the designated Opay account",
                "All amounts are in Nigerian Naira (₦)"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting payment stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get payment statistics"
        )

@router.post("/admin/payout-completed")
async def mark_payout_completed(
    month: str,
    transaction_reference: str,
    amount: float,
    db: Session = Depends(get_db)
):
    """
    ADMIN ONLY: Mark monthly payout as completed
    Records payout to eSTech System
    """
    try:
        # Validate month format
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid month format. Use YYYY-MM"
            )
        
        # Get payments for that month
        payments = db.query(Payment).filter(
            Payment.status == "success",
            db.func.strftime('%Y-%m', Payment.paid_at) == month,
            Payment.estech_share > 0,
            Payment.estech_paid_out == False
        ).all()
        
        if not payments:
            raise HTTPException(
                status_code=404,
                detail=f"No pending payments found for {month}"
            )
        
        total_estech = sum(p.estech_share for p in payments)
        
        # Validate amount matches (allow small rounding differences)
        if abs(total_estech - amount) > 10:  # Allow ₦10 difference
            raise HTTPException(
                status_code=400,
                detail=f"Amount mismatch. Calculated: ₦{total_estech:,}, Provided: ₦{amount:,}"
            )
        
        # Mark payments as paid out
        for payment in payments:
            payment.estech_paid_out = True
            payment.estech_payout_date = datetime.utcnow()
            payment.estech_payout_reference = transaction_reference
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Payout for {month} marked as completed",
            "payout_details": {
                "month": month,
                "transaction_reference": transaction_reference,
                "amount": f"₦{amount:,}",
                "payment_count": len(payments),
                "bank_details": ESTECH_BANK_DETAILS,
                "processed_at": datetime.utcnow().isoformat(),
                "status": "completed"
            },
            "affected_payments": len(payments)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error recording payout: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to record payout"
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
                "amount": 5000,
                "currency": "NGN",
                "description": "Regular Application",
                "user_display": "Pay ₦5,000 Application Fee",
                "features": [
                    "Standard application processing",
                    "Normal processing timeline",
                    "Basic support"
                ]
            },
            "vip": {
                "amount": 15000,
                "currency": "NGN",
                "description": "VIP Application",
                "user_display": "Pay ₦15,000 VIP Application Fee",
                "features": [
                    "Priority processing",
                    "Dedicated support",
                    "Expedited timeline",
                    "Additional benefits"
                ]
            }
        },
        "notes": "All payments are processed securely via Paystack"
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
        
        return response
        
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check payment status"
        )