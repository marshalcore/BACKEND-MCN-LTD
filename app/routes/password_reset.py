from fastapi import APIRouter, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.officer import Officer
from app.services.email_service import send_password_reset_email
from app.utils.token import generate_otp, store_verification_code, verify_otp

router = APIRouter(prefix="/officer", tags=["Password Reset"])

@router.post("/forgot-password")
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    officer = db.query(Officer).filter(Officer.email == email).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")

    otp_code = generate_otp()
    store_verification_code(db, email=email, purpose="officer_reset", code=otp_code)
    await send_password_reset_email(to_email=email, name=officer.email.split("@")[0], token=otp_code)

    return {"message": "A 6-digit verification code has been sent to your email."}


@router.post("/reset-password")
async def reset_password(
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not verify_otp(db, email=email, purpose="officer_reset", submitted_code=code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    officer = db.query(Officer).filter(Officer.email == email).first()
    if not officer:
        raise HTTPException(status_code=404, detail="User no longer exists")

    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    officer.password = pwd_ctx.hash(new_password)

    db.commit()
    return {"message": "Password reset successful"}
