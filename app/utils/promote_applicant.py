from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.pre_applicant import PreApplicant
from app.models.applicant import Applicant
import uuid

def promote_to_applicant(email: str, db: Session):
    # Check for pre-applicant first
    pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Pre-applicant not found.")

    # Check if already promoted (has full profile)
    existing_applicant = db.query(Applicant).filter(Applicant.email == email).first()
    if existing_applicant:
        print("✅ Applicant already promoted.")
        return  # Stop here. Don't overwrite.

    # DO NOT create partial applicant record without full profile.
    # Instead, leave pre_applicant alone until they complete password verification and profile.

    print("✅ Payment verified but awaiting password generation and full application.")
    # You can add an optional flag or email notification here.

    return  # Intentionally do not promote yet