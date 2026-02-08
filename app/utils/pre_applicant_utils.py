# app/utils/pre_applicant_utils.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.pre_applicant import PreApplicant

def get_or_create_pre_applicant_id(db: Session, email: str, full_name: str = None):
    """
    Get or create a pre-applicant ID for an email
    Returns: (pre_applicant_id, is_new)
    """
    normalized_email = email.strip().lower()
    
    # Try to find existing pre-applicant
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if pre_applicant and pre_applicant.id:
        return str(pre_applicant.id), False
    
    # Create new pre-applicant
    new_pre_applicant = PreApplicant(
        email=normalized_email,
        full_name=full_name or normalized_email.split('@')[0],
        status="created"
    )
    
    db.add(new_pre_applicant)
    db.commit()
    db.refresh(new_pre_applicant)
    
    return str(new_pre_applicant.id), True