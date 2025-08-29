# app/routes/form_submission.py
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.applicant import Applicant
from app.services.email_service import send_guarantor_confirmation_email
from pydantic import EmailStr

router = APIRouter(
    prefix="/form",
    tags=["Form Submission"]
)

@router.post("/submit")
async def submit_application(
    email: EmailStr = Form(...),
    full_name: str = Form(None),  # Optional: can auto-pull from DB
    db: Session = Depends(get_db)
):
    applicant = db.query(Applicant).filter(Applicant.email == email).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    if not applicant.is_verified:
        raise HTTPException(status_code=403, detail="Application not verified")

    name = full_name or applicant.full_name

    await send_guarantor_confirmation_email(applicant.email, name)

    return {
        "message": "Application submitted successfully. Guarantor form sent to email.",
        "guarantor_form_url": "/static/guarantor-form.pdf"
    }
