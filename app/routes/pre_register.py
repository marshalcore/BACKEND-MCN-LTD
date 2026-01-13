# app/routes/pre_register.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.schemas.pre_applicant import PreApplicantCreate, PreApplicantStatusResponse
from datetime import datetime, timedelta

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
        status="created"
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