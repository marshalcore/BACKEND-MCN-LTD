from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from sqlalchemy import func

router = APIRouter(prefix="/privacy", tags=["Privacy Notice"])

@router.post("/accept")
async def accept_privacy_notice(
    email: str,
    db: Session = Depends(get_db)
):
    """Accept privacy notice (required before form access)"""
    normalized_email = email.strip().lower()
    
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    # Must have verified password first
    if not pre_applicant.is_verified:
        raise HTTPException(
            status_code=403, 
            detail="Verify password first before accepting privacy notice"
        )
    
    # Record acceptance
    current_time = datetime.now(ZoneInfo("UTC"))
    pre_applicant.privacy_accepted = True
    pre_applicant.privacy_accepted_at = current_time
    pre_applicant.status = "privacy_accepted"
    db.commit()
    
    return {
        "status": "accepted",
        "message": "Privacy notice accepted",
        "accepted_at": pre_applicant.privacy_accepted_at.isoformat(),
        "next_step": "application_form"
    }

@router.get("/notice")
async def get_privacy_notice():
    """Return privacy notice text"""
    return {
        "notice": """PRIVACY NOTICE

MBC is an Executive Body under Article 6 Section B of the Constitution 
of Marshal Core of Nigeria, 2025 (as structured) that processes data.

We collect and process your personal information for the purpose of:
1. Application processing and verification
2. Service delivery and program management
3. Communication regarding your application
4. Compliance with legal and regulatory requirements

By accepting this notice, you acknowledge that:
- Your information will be processed in accordance with our privacy policy
- You have the right to access, correct, or delete your personal data
- Your data will be stored securely and only used for stated purposes
- You may withdraw consent at any time by contacting us

For more information, contact: privacy@marshalcoreng.com""",
        "requires_acceptance": True,
        "version": "1.0",
        "last_updated": "2024-01-01"
    }

@router.get("/status/{email}")
async def check_privacy_status(email: str, db: Session = Depends(get_db)):
    """Check if privacy notice has been accepted"""
    normalized_email = email.strip().lower()
    
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    return {
        "privacy_accepted": pre_applicant.privacy_accepted,
        "accepted_at": pre_applicant.privacy_accepted_at.isoformat() if pre_applicant.privacy_accepted else None
    }