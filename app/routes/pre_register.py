from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.schemas.pre_applicant import PreApplicantCreate, PreApplicantStatusResponse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/pre-applicant", tags=["Pre Applicant"])

@router.post("/register", response_model=PreApplicantStatusResponse)
def register_pre_applicant(data: PreApplicantCreate, db: Session = Depends(get_db)):
    normalized_email = data.email.strip().lower()
    
    # Check if pre-applicant already exists
    existing = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if existing:
        # Check what step they completed and return appropriate redirect
        if existing.application_submitted:
            return PreApplicantStatusResponse(
                status="already_completed",
                message="Application already submitted with this email",
                redirect_to="completed_page",
                email=normalized_email
            )
        elif existing.password_used:
            return PreApplicantStatusResponse(
                status="password_used",
                message="Password already used. Please contact support if you need assistance.",
                redirect_to="contact_support",
                email=normalized_email
            )
        elif existing.has_paid and existing.application_password:
            return PreApplicantStatusResponse(
                status="password_sent",
                message="Password already sent to your email. Please check your inbox.",
                redirect_to="password_input",
                email=normalized_email
            )
        elif existing.has_paid:
            return PreApplicantStatusResponse(
                status="payment_completed",
                message="Payment already completed. Please wait for password generation.",
                redirect_to="payment_success",
                email=normalized_email
            )
        else:
            return PreApplicantStatusResponse(
                status="exists_not_paid",
                message="Pre-applicant exists but payment not completed",
                redirect_to="payment",
                email=normalized_email,
                pre_applicant_id=str(existing.id)
            )
    
    # New pre-applicant - create record
    new_entry = PreApplicant(
        full_name=data.full_name,
        email=normalized_email,
        status="created",
        created_at=datetime.now(ZoneInfo("UTC"))
    )
    
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    return PreApplicantStatusResponse(
        status="created",
        message="Pre-registration complete. Proceed to payment.",
        redirect_to="payment",
        email=normalized_email,
        pre_applicant_id=str(new_entry.id)
    )

@router.post("/select-tier")
async def select_application_tier(
    email: str,
    tier: str,  # 'regular' or 'vip'
    db: Session = Depends(get_db)
):
    """Select application tier (Regular ₦5,180 or VIP ₦25,900)"""
    normalized_email = email.strip().lower()
    
    if tier not in ["regular", "vip"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Must be 'regular' or 'vip'")
    
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    # Update tier selection
    pre_applicant.selected_tier = tier
    pre_applicant.tier_selected_at = datetime.now(ZoneInfo("UTC"))
    pre_applicant.status = "tier_selected"
    db.commit()
    
    # Return payment info
    amount = 5180 if tier == "regular" else 25900
    
    return {
        "status": "tier_selected",
        "tier": tier,
        "amount": amount,
        "amount_display": f"₦{amount:,}",
        "payment_reference": pre_applicant.payment_reference or "not_paid",
        "next_step": "payment",
        "payment_endpoint": "/api/payments/initiate"
    }

@router.get("/status/{email}")
async def get_pre_applicant_status(email: str, db: Session = Depends(get_db)):
    """Get pre-applicant status including tier selection"""
    normalized_email = email.strip().lower()
    
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    return {
        "full_name": pre_applicant.full_name,
        "email": pre_applicant.email,
        "has_paid": pre_applicant.has_paid,
        "selected_tier": pre_applicant.selected_tier,
        "tier_selected_at": pre_applicant.tier_selected_at.isoformat() if pre_applicant.tier_selected_at else None,
        "privacy_accepted": pre_applicant.privacy_accepted,
        "status": pre_applicant.status,
        "created_at": pre_applicant.created_at.isoformat() if pre_applicant.created_at else None
    }