# app/routes/email_verification.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import random
import dns.resolver

from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.models.verification_code import VerificationCode
from app.services.email_service import send_verification_code_email
from app.schemas.email_verification import (
    EmailCheckRequest,
    EmailCheckResponse,
    SendVerificationRequest,
    SendVerificationResponse,
    ConfirmVerificationRequest,
    ConfirmVerificationResponse,
)

router = APIRouter(prefix="/pre-applicant", tags=["Email Verification"])

DISPOSABLE_DOMAINS = {"mailinator.com", "tempmail.com", "10minutemail.com", "maildrop.cc"}

@router.post("/check-email", response_model=EmailCheckResponse)
def check_email(payload: EmailCheckRequest):
    email = payload.email.strip().lower()
    domain = email.split("@")[-1]
    if domain in DISPOSABLE_DOMAINS:
        return EmailCheckResponse(valid=False, reason="Disposable email providers are not allowed")
    try:
        answers = dns.resolver.resolve(domain, "MX")
        if not answers:
            return EmailCheckResponse(valid=False, reason="Domain has no MX records")
    except Exception:
        return EmailCheckResponse(valid=False, reason="Domain not resolvable or DNS timeout")
    return EmailCheckResponse(valid=True)

@router.post("/send-verification", response_model=SendVerificationResponse)
def send_verification(payload: SendVerificationRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    code = f"{random.randint(0, 999999):06d}"
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=20)

    ev = VerificationCode(
        email=email,
        code=code,
        purpose="email_verification",
        used=False,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(ev)
    db.commit()

    background_tasks.add_task(send_verification_code_email, email, code)
    return SendVerificationResponse(sent=True, expires_in_minutes=20)

@router.post("/confirm-verification", response_model=ConfirmVerificationResponse)
def confirm_verification(payload: ConfirmVerificationRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    code = payload.code.strip()

    ev = db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.code == code,
        VerificationCode.used == False,
        VerificationCode.expires_at >= datetime.utcnow()
    ).order_by(VerificationCode.created_at.desc()).first()

    if not ev:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    ev.used = True
    db.query(PreApplicant).filter(func.lower(PreApplicant.email) == email).update({
        "email_verified": True,
        "email_verified_at": datetime.utcnow()
    })
    db.commit()
    return ConfirmVerificationResponse(verified=True)