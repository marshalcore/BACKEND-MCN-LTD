# app/routes/pre_register.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import ProgrammingError, IntegrityError, OperationalError
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.schemas.pre_applicant import PreApplicantCreate, PreApplicantStatusResponse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

router = APIRouter(prefix="/pre-applicant", tags=["Pre Applicant"])
logger = logging.getLogger(__name__)

# FIXED: Added Form(...) to all parameters
@router.post("/check-status")
async def check_application_status(
    email: str = Form(...),
    full_name: str = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db)
):
    """Check pre-applicant status for continue application feature"""
    normalized_email = email.strip().lower()
    
    logger.info(f"📞 Check status called for: {normalized_email}, {full_name}, {category}")
    
    # Check if pre-applicant exists
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        logger.info(f"❌ No pre-applicant found for: {normalized_email}")
        raise HTTPException(
            status_code=404,
            detail="No application found. Please start a new application."
        )
    
    logger.info(f"✅ Pre-applicant found: {pre_applicant.email}")
    
    # Build response based on current status
    status_info = {
        "email": normalized_email,
        "full_name": pre_applicant.full_name,
        "status": getattr(pre_applicant, "status", "created"),
        "has_paid": getattr(pre_applicant, "has_paid", False),
        "selected_tier": getattr(pre_applicant, "selected_tier", None),
        "privacy_accepted": getattr(pre_applicant, "privacy_accepted", False),
        "application_submitted": getattr(pre_applicant, "application_submitted", False),
        "password_generated": getattr(pre_applicant, "password_generated", False),
        "password_used": getattr(pre_applicant, "password_used", False),
        "password_sent": bool(getattr(pre_applicant, "application_password", None)),
        "created_at": pre_applicant.created_at.isoformat() if pre_applicant.created_at else None,
    }
    
    # Determine current stage for routing
    if getattr(pre_applicant, "application_submitted", False):
        status_info["current_stage"] = "application_submitted"
        status_info["redirect_to"] = "success"
    elif getattr(pre_applicant, "password_used", False):
        status_info["current_stage"] = "password_used"
        status_info["redirect_to"] = "contact_support"
    elif getattr(pre_applicant, "has_paid", False) and getattr(pre_applicant, "application_password", None):
        status_info["current_stage"] = "password_sent"
        status_info["redirect_to"] = "password_input"
    elif getattr(pre_applicant, "has_paid", False):
        status_info["current_stage"] = "payment_completed"
        status_info["redirect_to"] = "password_generation"
    elif getattr(pre_applicant, "selected_tier", None):
        status_info["current_stage"] = "tier_selected"
        status_info["redirect_to"] = "payment"
    else:
        status_info["current_stage"] = "new_applicant"
        status_info["redirect_to"] = "tier_selection"
    
    # Add timestamp info
    if hasattr(pre_applicant, 'updated_at') and pre_applicant.updated_at:
        status_info["last_updated"] = pre_applicant.updated_at.isoformat()
    else:
        status_info["last_updated"] = status_info["created_at"]
    
    # Add pre_applicant_id if available
    if pre_applicant.id:
        status_info["pre_applicant_id"] = str(pre_applicant.id)
    
    logger.info(f"📊 Returning status: {status_info}")
    return status_info

@router.post("/register", response_model=PreApplicantStatusResponse)
async def register_pre_applicant(
    full_name: str = Form(...),
    email: str = Form(...),
    tier: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register new pre-applicant - FIXED to use Form parameters"""
    normalized_email = email.strip().lower()
    
    logger.info(f"📝 Registering pre-applicant: {normalized_email}, {full_name}, {tier}")
    
    # Check if email already exists
    existing = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if existing:
        # Use safe attribute access with defaults
        application_submitted = getattr(existing, "application_submitted", False)
        password_used = getattr(existing, "password_used", False)
        has_paid = getattr(existing, "has_paid", False)
        application_password = getattr(existing, "application_password", None)
        
        if application_submitted:
            return PreApplicantStatusResponse(
                status="already_completed",
                message="Application already submitted with this email",
                redirect_to="completed_page",
                email=normalized_email
            )
        elif password_used:
            return PreApplicantStatusResponse(
                status="password_used",
                message="Password already used. Please contact support if you need assistance.",
                redirect_to="contact_support",
                email=normalized_email
            )
        elif has_paid and application_password:
            return PreApplicantStatusResponse(
                status="password_sent",
                message="Password already sent to your email. Please check your inbox.",
                redirect_to="password_input",
                email=normalized_email
            )
        elif has_paid:
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
                pre_applicant_id=str(existing.id) if existing.id else None
            )
    
    # Create new pre-applicant
    try:
        new_entry = PreApplicant(
            full_name=full_name,
            email=normalized_email,
            status="created",
            created_at=datetime.now(ZoneInfo("UTC"))
        )
        
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        
        logger.info(f"✅ Created new pre-applicant: {normalized_email} with ID: {new_entry.id}")
        
        return PreApplicantStatusResponse(
            status="created",
            message="Pre-registration complete. Proceed to payment.",
            redirect_to="payment",
            email=normalized_email,
            pre_applicant_id=str(new_entry.id)
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating pre-applicant: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create pre-applicant. Please try again."
        )

@router.post("/select-tier")
async def select_application_tier(
    email: str = Form(...),
    tier: str = Form(...),
    db: Session = Depends(get_db)
):
    """Select application tier (Regular ₦5,180 or VIP ₦25,900)"""
    normalized_email = email.strip().lower()
    
    logger.info(f"🎯 Selecting tier: {normalized_email} -> {tier}")
    
    if tier not in ["regular", "vip"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Must be 'regular' or 'vip'")
    
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    try:
        # Update tier selection
        pre_applicant.selected_tier = tier
        pre_applicant.tier_selected_at = datetime.now(ZoneInfo("UTC"))
        pre_applicant.status = "tier_selected"
        
        db.commit()
        logger.info(f"✅ Tier selected: {normalized_email} -> {tier}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating tier: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tier")
    
    # Return payment info
    amount = 5180 if tier == "regular" else 25900
    
    return {
        "status": "tier_selected",
        "tier": tier,
        "amount": amount,
        "amount_display": f"₦{amount:,}",
        "payment_reference": getattr(pre_applicant, 'payment_reference', None) or "not_paid",
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
    
    # Build response with safe attribute access
    response = {
        "full_name": pre_applicant.full_name,
        "email": pre_applicant.email,
        "has_paid": getattr(pre_applicant, "has_paid", False),
        "status": getattr(pre_applicant, "status", "created"),
        "created_at": pre_applicant.created_at.isoformat() if pre_applicant.created_at else None
    }
    
    # Add optional fields if they exist
    optional_fields = [
        "selected_tier",
        "tier_selected_at", 
        "privacy_accepted",
        "privacy_accepted_at",
        "application_submitted",
        "submitted_at",
        "payment_reference"
    ]
    
    for field in optional_fields:
        if hasattr(pre_applicant, field):
            value = getattr(pre_applicant, field)
            if hasattr(value, 'isoformat') and callable(getattr(value, 'isoformat')):
                response[field] = value.isoformat() if value else None
            else:
                response[field] = value
    
    return response

@router.get("/debug/schema")
async def debug_schema(db: Session = Depends(get_db)):
    """Debug endpoint to check database schema"""
    try:
        # Get table info
        result = db.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'pre_applicants'
            ORDER BY ordinal_position
        """).fetchall()
        
        columns = [dict(row) for row in result]
        
        # Get sample data
        sample = db.execute("SELECT * FROM pre_applicants LIMIT 1").fetchone()
        
        return {
            "table": "pre_applicants",
            "columns": columns,
            "column_count": len(columns),
            "sample_row": dict(sample) if sample else "No data",
            "model_columns": [col.name for col in PreApplicant.__table__.columns]
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "model_columns": [col.name for col in PreApplicant.__table__.columns]
        }