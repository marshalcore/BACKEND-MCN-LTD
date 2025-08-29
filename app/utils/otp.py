# app/utils/otp.py
from datetime import datetime, timedelta
import random
import string
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.verification_code import VerificationCode


# -------------------- PURPOSE NORMALIZER --------------------
def normalize_purpose(purpose: str) -> str:
    """
    Normalize OTP purposes so admin_* and officer_* map to base ones.
    Ensures consistency between storage and verification.
    """
    purpose = purpose.lower().strip()

    mapping = {
        "admin_login": "login",
        "admin_signup": "signup",
        "admin_reset": "password_reset",
        "officer_signup": "signup",
        "officer_login": "login",
    }

    return mapping.get(purpose, purpose)


# -------------------- OTP GENERATOR --------------------
def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP of given length (default 6 digits)."""
    return ''.join(random.choices(string.digits, k=length))


# -------------------- STORE OTP --------------------
def store_verification_code(db: Session, email: str, purpose: str, code: str):
    """Store OTP in DB after clearing existing ones for same email+purpose."""
    normalized_email = email.strip().lower()
    normalized_purpose = normalize_purpose(purpose)

    print(f"\n[OTP STORAGE] Storing for {normalized_email} | Purpose: {normalized_purpose} | Code: {code}")

    try:
        # Remove existing OTPs for same email + purpose
        db.query(VerificationCode).filter(
            VerificationCode.email == normalized_email,
            VerificationCode.purpose == normalized_purpose
        ).delete()
        db.flush()

        record = VerificationCode(
            email=normalized_email,
            code=code,
            purpose=normalized_purpose,
            expires_at=datetime.utcnow() + timedelta(minutes=10)  # 10 min validity
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        print(f"[OTP STORAGE] Success. ID: {record.id}")
        return record

    except Exception as e:
        db.rollback()
        print(f"[OTP STORAGE ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store OTP: {str(e)}"
        )


# -------------------- VERIFY OTP --------------------
def verify_otp(db: Session, email: str, purpose: str, submitted_code: str) -> bool:
    """
    Verify submitted OTP for given email & purpose.
    Deletes OTP on success.
    """
    normalized_email = email.strip().lower()
    normalized_purpose = normalize_purpose(purpose)

    print(f"\n[OTP VERIFICATION] For: {normalized_email} | Code: {submitted_code} | Purpose: {normalized_purpose}")

    try:
        # Fetch all OTPs for this email+purpose (newest first)
        records = db.query(VerificationCode).filter(
            VerificationCode.email == normalized_email,
            VerificationCode.purpose == normalized_purpose
        ).order_by(VerificationCode.expires_at.desc()).all()

        print(f"[DEBUG] Available OTPs ({normalized_purpose}): {len(records)}")

        for record in records:
            print(f"[OTP RECORD] Code: {record.code} | Expires: {record.expires_at}")
            print(f"[TIME CHECK] Current UTC: {datetime.utcnow()}")

            if record.code == submitted_code:
                if record.expires_at >= datetime.utcnow():
                    print("[OTP VERIFICATION] ✅ Valid OTP found - deleting record")
                    db.delete(record)
                    db.commit()
                    return True
                else:
                    print("[OTP VERIFICATION] ⚠️ Found matching but expired OTP")

        print("[OTP VERIFICATION] ❌ No valid OTP found")
        return False

    except Exception as e:
        db.rollback()
        print(f"[OTP VERIFICATION ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error verifying OTP: {str(e)}"
        )
