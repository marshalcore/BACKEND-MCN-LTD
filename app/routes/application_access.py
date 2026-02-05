from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.services.email_service import send_application_password_email
from app.utils.password import generate_password
from pydantic import EmailStr, BaseModel
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

router = APIRouter(
    prefix="/access",
    tags=["Application Access"]
)

class VerifyRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/generate-password")
async def generate_application_password(email: EmailStr, db: Session = Depends(get_db)):
    normalized_email = email.strip().lower()
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Pre-applicant not found")

    if not pre_applicant.has_paid:
        raise HTTPException(status_code=403, detail="Payment not verified")

    # Check if password was already generated and is still valid
    current_time = datetime.now(ZoneInfo("UTC"))
    if (pre_applicant.application_password and 
        pre_applicant.password_expires_at and 
        pre_applicant.password_expires_at > current_time):
        return {"message": "Password already generated and still valid."}

    # Generate new password with 7-day validity
    password = generate_password()
    pre_applicant.application_password = password
    pre_applicant.password_generated = True
    pre_applicant.password_generated_at = current_time
    pre_applicant.password_expires_at = current_time + timedelta(days=7)  # 7-day validity
    pre_applicant.status = "password_sent"
    
    db.commit()

    await send_application_password_email(email, pre_applicant.full_name, password)
    return {"message": "Password sent to email"}

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
    
    if pre_applicant.password_expires_at <= current_time:
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
        remaining = pre_applicant.password_expires_at - current_time
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