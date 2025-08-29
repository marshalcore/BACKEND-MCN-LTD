# app/routes/pre_register.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.schemas.pre_applicant import PreApplicantCreate

router = APIRouter(prefix="/pre-applicant", tags=["Pre Applicant"])

@router.post("/register")
def register_pre_applicant(data: PreApplicantCreate, db: Session = Depends(get_db)):
    existing = db.query(PreApplicant).filter(func.lower(PreApplicant.email) == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="This email is already pre-registered.")

    new_entry = PreApplicant(full_name=data.full_name, email=data.email)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return {
        "status": "success",
        "message": "Pre-registration complete. Proceed to payment.",
        "pre_applicant_id": str(new_entry.id),
    }
