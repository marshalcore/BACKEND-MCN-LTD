from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form, Body
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
import logging

from app.database import get_db
from app.models.admin import Admin
from app.models.officer import Officer
from app.models.applicant import Applicant
from app.models.verification_code import VerificationCode
from app.schemas.admin import AdminSignup, AdminLogin, AdminResponse, AdminUpdateUser, ResetUserPassword, OTPVerifyRequest
from app.utils.hash import hash_password, verify_password
from app.utils.token import (
    create_access_token,
    generate_otp,
    store_verification_code,
    verify_otp
)
from app.config import settings
from app.services.email_service import send_password_reset_email, send_otp_email
from enum import Enum
from app.utils.otp import normalize_purpose

router = APIRouter(
    prefix="/admin",
    tags=["Admin Authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")
logger = logging.getLogger(__name__)

# ------------------ Pydantic Schemas ------------------

class OTPPurpose(str, Enum):
    login = "login"
    signup = "signup"
    password_reset = "password_reset"
    officer_signup = "officer_signup"
    admin_login = "admin_login"

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class OfficerUpdate(BaseModel):
    email: Optional[EmailStr] = None
    rank: Optional[str] = None
    position: Optional[str] = None

class ApplicantUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    unique_id: Optional[str] = None

# ------------------ Helpers ------------------

def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None or role != "admin":
            raise credentials_exception
        token_data = TokenData(email=email, role=role)
    except JWTError:
        raise credentials_exception

    admin = db.query(Admin).filter(Admin.email == token_data.email).first()
    if admin is None:
        raise credentials_exception
    return admin

# ------------------ Authentication Endpoints ------------------

@router.post("/verify-otp", response_model=dict)
async def verify_admin_otp(
    request: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify OTP for various purposes"""
    normalized_email = request.email.strip().lower()
    normalized_purpose = normalize_purpose(request.purpose.strip())

    logger.info(f"OTP verification for: {normalized_email} | Purpose: {normalized_purpose}")

    record = db.query(VerificationCode).filter(
        VerificationCode.email == normalized_email,
        VerificationCode.purpose == normalized_purpose,
        VerificationCode.code == request.code,
        VerificationCode.expires_at >= datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP"
        )

    # OTP is valid → delete it
    db.delete(record)
    db.commit()

    response = {
        "status": "success",
        "message": f"OTP verified for {normalized_purpose}",
        "email": normalized_email
    }

    # If purpose is login or admin_login → issue access token
    if normalized_purpose in ["login", "admin_login"]:
        admin = db.query(Admin).filter(
            func.lower(Admin.email) == normalized_email
        ).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        response.update({
            "access_token": create_access_token(
                data={"sub": admin.email, "role": "admin"}
            ),
            "token_type": "bearer"
        })

    return response

@router.post("/signup", response_model=dict)
async def admin_signup(admin_data: AdminSignup, db: Session = Depends(get_db)):
    """Admin signup with OTP and pending verification"""
    normalized_email = admin_data.email.strip().lower()
    logger.info(f"Admin signup started for: {normalized_email}")

    try:
        # Prevent duplicates
        existing_admin = db.query(Admin).filter(
            func.lower(Admin.email) == normalized_email
        ).first()
        if existing_admin:
            logger.warning(f"Email already exists: {normalized_email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create admin with "unverified" flag
        new_admin = Admin(
            full_name=admin_data.full_name,
            email=normalized_email,
            hashed_password=hash_password(admin_data.password),
            is_superuser=True,
            is_verified=False
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        logger.info(f"Admin created: {new_admin.id}")

        # Generate OTP
        code = generate_otp()
        logger.info(f"Generated OTP: {code}")

        # Store OTP
        store_verification_code(
            db=db,
            email=normalized_email,
            purpose="admin_signup",
            code=code
        )

        # Send email
        try:
            await send_otp_email(
                to_email=normalized_email,
                name=new_admin.full_name,
                token=code,
                purpose="admin_signup"
            )
            logger.info("OTP email sent successfully")
        except Exception as e:
            logger.error(f"Email error: {str(e)}")

        return {
            "status": "otp_required",
            "message": "OTP sent to email for verification",
            "email": normalized_email,
            "debug_otp": code if settings.DEBUG else None
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@router.post("/login", response_model=dict)
async def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    """
    Admin login step 1: verify password, then generate & store OTP.
    """
    # Case-insensitive email lookup
    admin = db.query(Admin).filter(
        func.lower(Admin.email) == func.lower(data.email)
    ).first()

    if not admin or not verify_password(data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Generate OTP
    code = generate_otp()

    # Store OTP
    store_verification_code(
        db, email=admin.email, purpose="admin_login", code=code
    )

    # Send OTP by email
    email_sent = False
    email_error = None
    
    try:
        email_sent = await send_otp_email(
            to_email=admin.email,
            name=admin.full_name,
            token=code,
            purpose="admin_login"
        )
        if email_sent:
            logger.info(f"OTP sent successfully to {admin.email}")
        else:
            logger.warning(f"Email service failed for {admin.email}")
            email_error = "Email service failed"
    except Exception as e:
        logger.error(f"Failed to send OTP to {admin.email}: {str(e)}")
        email_error = str(e)

    # Response
    response = {
        "status": "success",
        "message": "OTP generated. Please check your email.",
        "email": admin.email,
        "requires_otp": True,
    }

    # Add warning if email failed
    if not email_sent:
        response["warning"] = "OTP generated but email delivery failed. Contact support."
        response["email_error"] = email_error
        if settings.DEBUG:
            response["debug_otp"] = code
            logger.info(f"DEBUG: OTP for {admin.email} is {code}")

    return response

@router.post("/resend-otp", response_model=dict)
async def resend_otp(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Resend OTP for various purposes"""
    admin = db.query(Admin).filter(Admin.email == request.email).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    code = generate_otp()
    store_verification_code(db, email=request.email, purpose="admin_login", code=code)

    await send_otp_email(
        to_email=request.email,
        name=admin.full_name,
        token=code,
        purpose="admin_login"
    )

    return {"status": "success", "message": "New OTP sent"}

@router.post("/forgot-password", response_model=dict)
async def admin_forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Send password reset OTP"""
    normalized_email = request.email.strip().lower()
    logger.info(f"Password reset requested for: {normalized_email}")

    admin = db.query(Admin).filter(
        func.lower(Admin.email) == normalized_email
    ).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Email not found")

    # Generate OTP
    code = generate_otp()
    logger.info(f"Generated OTP: {code}")

    try:
        # Clear existing OTPs
        db.query(VerificationCode).filter(
            VerificationCode.email == normalized_email,
            VerificationCode.purpose == "password_reset"
        ).delete()

        # Store new OTP
        record = VerificationCode(
            email=normalized_email,
            code=code,
            purpose="password_reset",
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.add(record)
        db.commit()
        logger.info(f"OTP stored for: {normalized_email}")

    except Exception as e:
        db.rollback()
        logger.error(f"OTP storage error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to store verification code"
        )

    # Send email
    try:
        await send_otp_email(
            to_email=normalized_email,
            name=admin.full_name,
            token=code,
            purpose="password_reset"
        )
        logger.info("Password reset OTP sent successfully")
    except Exception as e:
        logger.error(f"Email error: {str(e)}")

    return {
        "status": "success",
        "message": "OTP sent to email",
        "email": normalized_email
    }

@router.post("/reset-password", response_model=dict)
async def admin_reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password with OTP verification"""
    normalized_email = request.email.strip().lower()

    # Verify OTP
    if not verify_otp(db, email=normalized_email, purpose="password_reset", submitted_code=request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # Lookup admin
    admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )

    # Update password
    admin.hashed_password = hash_password(request.new_password)
    db.commit()

    # Cleanup OTP
    db.query(VerificationCode).filter(
        VerificationCode.email == normalized_email,
        VerificationCode.purpose == "password_reset"
    ).delete()
    db.commit()

    return {
        "status": "success",
        "message": "Password updated successfully",
        "email": normalized_email
    }

@router.post("/verify-login-otp", response_model=Token)
async def verify_login_otp(
    request: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify OTP for admin login and return JWT token"""
    normalized_email = request.email.strip().lower()
    logger.info(f"Login OTP verification for: {normalized_email}")

    record = db.query(VerificationCode).filter(
        VerificationCode.email == normalized_email,
        VerificationCode.purpose == "login",
        VerificationCode.code == request.code,
        VerificationCode.expires_at >= datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP"
        )

    # OTP is valid → delete it
    db.delete(record)
    db.commit()

    # Get admin and issue token
    admin = db.query(Admin).filter(
        func.lower(Admin.email) == normalized_email
    ).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    return {
        "access_token": create_access_token(
            data={"sub": admin.email, "role": "admin"}
        ),
        "token_type": "bearer"
    }

# ------------------ Dashboard & Admin Management ------------------

@router.get("/dashboard", response_model=dict)
async def admin_dashboard(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get dashboard statistics"""
    return {
        "total_applicants": db.query(Applicant).count(),
        "total_officers": db.query(Officer).count(),
        "total_admins": db.query(Admin).count()
    }

@router.get("/all-admins", response_model=List[AdminResponse])
async def get_all_admins(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get all admin users"""
    return db.query(Admin).all()

@router.delete("/delete-admin/{email}", response_model=dict)
async def delete_admin(
    email: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Delete an admin user"""
    if not current_admin.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete admins"
        )

    admin = db.query(Admin).filter(Admin.email == email).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )

    db.delete(admin)
    db.commit()
    return {"status": "success", "message": f"Admin {email} deleted"}

# ------------------ Officer Management ------------------

@router.get("/all-officers", response_model=List[dict])
async def get_all_officers(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get all officers"""
    officers = db.query(Officer).all()
    return [{
        "id": o.id,
        "unique_id": o.unique_id,
        "full_name": o.full_name,
        "email": o.email,
        "rank": o.rank,
        "position": o.position
    } for o in officers]

@router.get("/officers/{officer_id}", response_model=dict)
async def get_officer(
    officer_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get officer by ID"""
    officer = db.query(Officer).filter(Officer.id == officer_id).first()
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    return {
        "id": officer.id,
        "unique_id": officer.unique_id,
        "full_name": officer.full_name,
        "email": officer.email,
        "rank": officer.rank,
        "position": officer.position
    }

@router.put("/officers/{officer_id}", response_model=dict)
async def update_officer(
    officer_id: str,
    updates: OfficerUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Update officer details"""
    officer = db.query(Officer).filter(Officer.id == officer_id).first()
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )

    if updates.email:
        officer.email = updates.email
    if updates.rank:
        officer.rank = updates.rank
    if updates.position:
        officer.position = updates.position

    officer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(officer)
    
    return {
        "status": "success",
        "message": "Officer updated",
        "officer": {
            "id": officer.id,
            "email": officer.email,
            "rank": officer.rank,
            "position": officer.position
        }
    }

# ------------------ Applicant Management ------------------

@router.get("/all-applicants", response_model=List[dict])
async def get_all_applicants(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get all applicants"""
    applicants = db.query(Applicant).all()
    return [{
        "id": a.id,
        "unique_id": a.unique_id,
        "full_name": a.full_name,
        "email": a.email,
        "phone_number": a.phone_number,
        "is_verified": a.is_verified
    } for a in applicants]

@router.get("/applicants/{applicant_id}", response_model=dict)
async def get_applicant(
    applicant_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get applicant by ID"""
    applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )
    return {
        "id": applicant.id,
        "unique_id": applicant.unique_id,
        "full_name": applicant.full_name,
        "email": applicant.email,
        "phone_number": applicant.phone_number,
        "is_verified": applicant.is_verified
    }

@router.put("/applicants/{applicant_id}", response_model=dict)
async def update_applicant(
    applicant_id: str,
    updates: ApplicantUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Update applicant details"""
    applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )

    if updates.full_name:
        applicant.full_name = updates.full_name
    if updates.email:
        applicant.email = updates.email
    if updates.phone:
        applicant.phone_number = updates.phone
    if updates.status:
        applicant.is_verified = updates.status
    if updates.unique_id:
        applicant.unique_id = updates.unique_id

    db.commit()
    db.refresh(applicant)
    
    return {
        "status": "success",
        "message": "Applicant updated",
        "applicant": {
            "id": applicant.id,
            "unique_id": applicant.unique_id,
            "full_name": applicant.full_name,
            "email": applicant.email,
            "phone_number": applicant.phone_number,
            "is_verified": applicant.is_verified
        }
    }