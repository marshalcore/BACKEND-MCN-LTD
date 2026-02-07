# app/routes/application_access.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, HTTPException, Depends, status, Request, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.models.applicant import Applicant
from app.services.email_service import send_application_password_email
from app.utils.password import generate_password
from pydantic import EmailStr, BaseModel
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
import logging

router = APIRouter(
    prefix="/access",
    tags=["Application Access"]
)

logger = logging.getLogger(__name__)

def ensure_timezone_aware(dt):
    """Helper function to ensure datetime is timezone-aware"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt

class VerifyRequest(BaseModel):
    email: EmailStr
    password: str

class EmailRequest(BaseModel):
    email: EmailStr
    
@router.post("/generate-password")
async def generate_application_password(
    request: Request,
    payload: Optional[EmailRequest] = Body(None),
    db: Session = Depends(get_db),
):
    """
    Backwards-compatible generator:
    - Accepts JSON object: { "email": "..." } (preferred)
    - Falls back to legacy raw-body (e.g., "user@example.com" or plain text)
    """
    # Determine email from JSON payload or raw body
    if payload and payload.email:
        normalized_email = payload.email.strip().lower()
    else:
        body_bytes = await request.body()
        if not body_bytes:
            raise HTTPException(status_code=400, detail="Request body missing")
        try:
            import json
            parsed = json.loads(body_bytes)
            if isinstance(parsed, dict) and parsed.get("email"):
                normalized_email = str(parsed["email"]).strip().lower()
            elif isinstance(parsed, str):
                normalized_email = parsed.strip().lower()
            else:
                raise ValueError("Unsupported body shape")
        except json.JSONDecodeError:
            # Not JSON — treat as raw text
            normalized_email = body_bytes.decode("utf-8").strip().strip('"').lower()

    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()

    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Pre-applicant not found")

    if not pre_applicant.has_paid:
        raise HTTPException(status_code=403, detail="Payment not verified")

    # Check if password was already generated and is still valid
    current_time = datetime.now(ZoneInfo("UTC"))
    
    # FIX: Handle None values and ensure timezone-aware comparison
    if (pre_applicant.application_password and 
        pre_applicant.password_expires_at):
        
        # Ensure both datetimes are timezone-aware before comparing
        expires_at = ensure_timezone_aware(pre_applicant.password_expires_at)
        
        # Now compare timezone-aware datetimes
        if expires_at > current_time:
            return {"message": "Password already generated and still valid."}

    # Generate new password with 7-day validity
    password = generate_password()
    pre_applicant.application_password = password
    pre_applicant.password_generated = True
    pre_applicant.password_generated_at = current_time
    # Store as timezone-aware datetime
    pre_applicant.password_expires_at = current_time + timedelta(days=7)  # 7-day validity
    pre_applicant.status = "password_sent"

    db.commit()

    # Use normalized_email when sending
    try:
        await send_application_password_email(normalized_email, pre_applicant.full_name, password)
        return {"message": "Password sent to email"}
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"message": "Password generated but email sending failed", "password": password}

@router.post("/verify")
def verify_password(payload: VerifyRequest, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    password = payload.password

    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if payment is completed
    if not pre_applicant.has_paid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payment not completed. Please complete payment first."
        )

    # Check if password matches
    if pre_applicant.application_password != password:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Check if password is expired (7-day validity)
    current_time = datetime.now(ZoneInfo("UTC"))
    if not pre_applicant.password_expires_at:
        raise HTTPException(status_code=401, detail="Password not properly generated")
    
    # FIX: Ensure both datetimes are timezone-aware before comparing
    expires_at = ensure_timezone_aware(pre_applicant.password_expires_at)
    
    # Now compare timezone-aware datetimes
    if expires_at <= current_time:
        raise HTTPException(status_code=401, detail="Password expired (7-day validity)")

    # Check if password was already used
    if pre_applicant.password_used:
        raise HTTPException(status_code=401, detail="This password has already been used")

    # Mark as verified but don't mark password as used yet
    # Password will be marked as used when application is submitted
    pre_applicant.is_verified = True
    pre_applicant.status = "verified"
    db.commit()
    
    return {"message": "Verified. You can now access the form.", "valid": True}

@router.post("/check-status")
def check_application_status(email: EmailStr, db: Session = Depends(get_db)):
    """Check application status including password expiry"""
    normalized_email = email.strip().lower()
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Pre-applicant not found")
    
    # Calculate password expiry info
    current_time = datetime.now(ZoneInfo("UTC"))
    password_expires_in = None
    
    if pre_applicant.password_expires_at:
        # FIX: Ensure both datetimes are timezone-aware before comparing
        expires_at = ensure_timezone_aware(pre_applicant.password_expires_at)
        
        remaining = expires_at - current_time
        if remaining.total_seconds() > 0:
            password_expires_in = {
                "days": remaining.days,
                "hours": remaining.seconds // 3600,
                "minutes": (remaining.seconds % 3600) // 60
            }
    
    return {
        "has_paid": pre_applicant.has_paid,
        "password_generated": pre_applicant.password_generated,
        "password_used": pre_applicant.password_used,
        "application_submitted": pre_applicant.application_submitted,
        "privacy_accepted": pre_applicant.privacy_accepted,
        "selected_tier": pre_applicant.selected_tier,
        "status": pre_applicant.status,
        "password_expires_in": password_expires_in,
        "can_access_form": (
            pre_applicant.has_paid and 
            pre_applicant.is_verified and 
            pre_applicant.privacy_accepted and 
            not pre_applicant.application_submitted
        )
    }

@router.get("/debug/timezone/{email}")
def debug_timezone_info(email: str, db: Session = Depends(get_db)):
    """Debug endpoint to check datetime timezone info"""
    normalized_email = email.strip().lower()
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Not found")
    
    current_time = datetime.now(ZoneInfo("UTC"))
    
    expires_info = {}
    if pre_applicant.password_expires_at:
        expires_info = {
            "value": pre_applicant.password_expires_at.isoformat() if pre_applicant.password_expires_at else None,
            "tzinfo": str(pre_applicant.password_expires_at.tzinfo) if pre_applicant.password_expires_at else None,
            "is_aware": pre_applicant.password_expires_at.tzinfo is not None if pre_applicant.password_expires_at else None
        }
    
    generated_info = {}
    if pre_applicant.password_generated_at:
        generated_info = {
            "value": pre_applicant.password_generated_at.isoformat() if pre_applicant.password_generated_at else None,
            "tzinfo": str(pre_applicant.password_generated_at.tzinfo) if pre_applicant.password_generated_at else None,
            "is_aware": pre_applicant.password_generated_at.tzinfo is not None if pre_applicant.password_generated_at else None
        }
    
    return {
        "email": normalized_email,
        "current_time": {
            "iso": current_time.isoformat(),
            "tzinfo": str(current_time.tzinfo)
        },
        "password_expires_at": expires_info,
        "password_generated_at": generated_info,
        "has_password": bool(pre_applicant.application_password),
        "is_verified": pre_applicant.is_verified
    }