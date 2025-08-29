from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.pre_applicant import PreApplicant
from app.services.email_service import send_application_password_email
from app.utils.password import generate_password
from pydantic import EmailStr, BaseModel

router = APIRouter(
    prefix="/access",
    tags=["Application Access"]
)

@router.post("/generate-password")
async def generate_application_password(email: EmailStr, db: Session = Depends(get_db)):
    pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()
    if not pre_applicant:
        raise HTTPException(status_code=404, detail="Pre-applicant not found")

    if not pre_applicant.has_paid:
        raise HTTPException(status_code=403, detail="Payment not verified")

    # ✅ Skip if password already generated
    if pre_applicant.application_password:
        return {"message": "Password already generated."}

    password = generate_password()
    pre_applicant.application_password = password
    db.commit()

    await send_application_password_email(email, pre_applicant.full_name, password)
    return {"message": "Password sent to email"}


class VerifyRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/verify")
def verify_password(payload: VerifyRequest, db: Session = Depends(get_db)):
    email = payload.email
    password = payload.password

    pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()
    if not pre_applicant or pre_applicant.application_password != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    pre_applicant.is_verified = True
    db.commit()
    return {"message": "Verified. You can now access the form."}
