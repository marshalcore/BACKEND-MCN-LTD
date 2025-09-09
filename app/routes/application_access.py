from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.services.email_service import send_application_password_email
from app.utils.password import generate_password
from pydantic import EmailStr, BaseModel
from datetime import datetime, timedelta

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
    if (pre_applicant.application_password and 
        pre_applicant.password_expires_at and 
        pre_applicant.password_expires_at > datetime.utcnow()):
        return {"message": "Password already generated and still valid."}

    # Generate new password
    password = generate_password()
    pre_applicant.application_password = password
    pre_applicant.password_generated = True
    pre_applicant.password_generated_at = datetime.utcnow()
    pre_applicant.password_expires_at = datetime.utcnow() + timedelta(hours=24)  # 24-hour validity
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

    # Check if password matches and is not expired
    if (pre_applicant.application_password != password or
        not pre_applicant.password_expires_at or
        pre_applicant.password_expires_at <= datetime.utcnow()):
        raise HTTPException(status_code=401, detail="Invalid or expired password")

    # Check if password was already used
    if pre_applicant.password_used:
        raise HTTPException(status_code=401, detail="This password has already been used")

    # Mark as verified but don't mark password as used yet
    # Password will be marked as used when application is submitted
    pre_applicant.is_verified = True
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
    
    return {
        "has_paid": pre_applicant.has_paid,
        "password_generated": pre_applicant.password_generated,
        "password_used": pre_applicant.password_used,
        "application_submitted": pre_applicant.application_submitted,
        "status": pre_applicant.status
    }