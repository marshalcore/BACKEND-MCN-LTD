from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session, Load, undefer
from datetime import timedelta, datetime
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.database import get_db
from app.models.officer import Officer
from app.models.applicant import Applicant
from app.models.verification_code import VerificationCode
from app.schemas.officer import OfficerSignup, OfficerLogin, OfficerResponse, OfficerSignupResponse
from app.schemas.token import Token, TokenData
from app.utils.hash import hash_password, verify_password
from app.utils.token import create_access_token, decode_access_token, get_current_officer
from app.config import settings
from app.services.email_service import send_otp_email
from app.schemas.officer import VerifyOTPResponse


router = APIRouter(prefix="/officer", tags=["Officer Auth"])

# Password Reset Models
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

# Add this new OTP verification model BEFORE the routes
class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str
    purpose: str = "officer_signup"

# Email configuration (using the correct variable names from your .env)
EMAIL_CONFIG = {
    "SMTP_SERVER": settings.EMAIL_HOST,
    "SMTP_PORT": settings.EMAIL_PORT,
    "SMTP_USERNAME": settings.EMAIL_HOST_USER,
    "SMTP_PASSWORD": settings.EMAIL_HOST_PASSWORD,
    "FROM_EMAIL": settings.EMAIL_FROM,
    "RESET_CODE_EXPIRE_MINUTES": 30  # Code expires after 30 minutes
}



def generate_reset_code() -> str:
    """Generate a 6-digit alphanumeric reset code"""
    return secrets.token_hex(3).upper()[:6]  # Returns 6-character uppercase code

async def send_reset_email(email: str, code: str):
    """Send password reset email with the code"""
    message = MIMEMultipart()
    message["From"] = EMAIL_CONFIG["FROM_EMAIL"]
    message["To"] = email
    message["Subject"] = "Password Reset Code"
    
    body = f"""
    <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Your password reset code is: <strong>{code}</strong></p>
            <p>This code will expire in {EMAIL_CONFIG['RESET_CODE_EXPIRE_MINUTES']} minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
    </html>
    """
    
    message.attach(MIMEText(body, "html"))
    
    try:
        with smtplib.SMTP(EMAIL_CONFIG["SMTP_SERVER"], EMAIL_CONFIG["SMTP_PORT"]) as server:
            server.starttls()
            server.login(EMAIL_CONFIG["SMTP_USERNAME"], EMAIL_CONFIG["SMTP_PASSWORD"])
            server.send_message(message)
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")

# Define generate_otp function BEFORE it's used
def generate_otp() -> str:
    """Generate a 6-digit numeric OTP"""
    return ''.join(secrets.choice('0123456789') for _ in range(6))

async def send_officer_signup_otp(email: str, name: str, otp_code: str):
    """Send OTP email for officer signup verification"""
    return await send_otp_email(
        to_email=email,
        name=name,
        token=otp_code,
        purpose="officer_signup"
    )

def verify_otp_code(db: Session, email: str, code: str, purpose: str) -> bool:
    """Verify OTP code"""
    verification = db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.code == code,
        VerificationCode.purpose == purpose,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()
    
    return verification is not None

# Now define the routes AFTER all the required functions and classes
@router.post("/signup", response_model=OfficerSignupResponse)
async def officer_signup(data: OfficerSignup, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    applicant = db.query(Applicant).filter(Applicant.unique_id == data.unique_id).first()

    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant record not found. Please complete your application first."
        )

    if db.query(Officer).filter_by(email=data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An officer with this email already exists. Please use a different email."
        )

    # Generate OTP
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)  # OTP expires in 10 minutes

    # Store OTP in verification codes table
    verification_code = VerificationCode(
        email=data.email,
        code=otp_code,
        purpose="officer_signup",
        expires_at=expires_at
    )
    
    # Remove any existing OTP for this email and purpose
    db.query(VerificationCode).filter(
        VerificationCode.email == data.email,
        VerificationCode.purpose == "officer_signup"
    ).delete()
    
    db.add(verification_code)
    db.commit()

    # Send OTP email in background
    background_tasks.add_task(send_officer_signup_otp, data.email, applicant.full_name, otp_code)

    return {
        "status": "otp_required",
        "message": "OTP sent to your email for verification",
        "data": {
            "email": data.email,
            "unique_id": data.unique_id
        },
        "next_steps": "Check your email for the verification code to complete signup"
    }

@router.post("/verify-signup-otp", response_model=OfficerSignupResponse)
async def verify_officer_signup_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    # Verify OTP code
    if not verify_otp_code(db, request.email, request.code, "officer_signup"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )

    # Return response with all required fields including next_steps
    return {
        "status": "success",
        "message": "OTP verified successfully. Please complete your signup.",
        "data": {
            "email": request.email,
            "verified": True
        },
        "next_steps": "proceed_to_complete_profile"  # Add this required field
    }

@router.post("/complete-signup", response_model=OfficerSignupResponse)
async def complete_officer_signup(data: OfficerSignup, db: Session = Depends(get_db)):
    """Complete officer signup after OTP verification"""
    applicant = db.query(Applicant).filter(Applicant.unique_id == data.unique_id).first()

    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant record not found."
        )

    if db.query(Officer).filter_by(email=data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An officer with this email already exists."
        )

    # Create new officer
    new_officer = Officer(
        unique_id=data.unique_id,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        applicant_id=applicant.id,
        full_name=applicant.full_name,
        nin_number=applicant.nin_number,
        gender=applicant.gender,
        date_of_birth=applicant.date_of_birth,
        residential_address=applicant.residential_address,
        state_of_residence=applicant.state_of_residence,
        local_government_residence=applicant.local_government_residence,
        additional_skills=applicant.additional_skills,
        nationality=applicant.nationality,
        country_of_residence=applicant.country_of_residence,
        state_of_origin=applicant.state_of_origin,
        local_government_origin=applicant.local_government_origin,
        religion=applicant.religion,
        place_of_birth=applicant.place_of_birth,
        marital_status=applicant.marital_status,
        bank_name=applicant.bank_name,
        account_number=applicant.account_number,
        category=applicant.category,
        other_name=applicant.other_name,
        do_you_smoke=applicant.do_you_smoke,
        passport=applicant.passport_photo
    )
    
    db.add(new_officer)
    db.commit()
    db.refresh(new_officer)
    
    # Clean up used OTP
    db.query(VerificationCode).filter(
        VerificationCode.email == data.email,
        VerificationCode.purpose == "officer_signup"
    ).delete()
    db.commit()

    return {
        "status": "success",
        "message": "Officer account created successfully!",
        "data": {
            "id": str(new_officer.id),
            "email": new_officer.email,
            "unique_id": new_officer.unique_id,
            "full_name": new_officer.full_name
        },
        "next_steps": "You can now login with your credentials to access your dashboard"
    }


@router.post("/login", response_model=Token)
def officer_login(data: OfficerLogin, db: Session = Depends(get_db)):
    officer = db.query(Officer).options(
        Load(Officer).undefer(Officer.passport)
    ).filter_by(unique_id=str(data.unique_id)).first()
    
    if not officer or not verify_password(data.password, officer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": officer.unique_id},
        expires_delta=access_token_expires
    )
    
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": officer.unique_id, "type": "refresh"},
        expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/validate-token")
async def validate_token(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        token = data.get("token")
        
        if not token:
            raise HTTPException(status_code=422, detail="Token is required")
            
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        unique_id = payload.get("sub")
        if not unique_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        officer = db.query(Officer).options(
            Load(Officer).undefer(Officer.passport)
        ).filter_by(unique_id=unique_id).first()
        if not officer:
            raise HTTPException(status_code=401, detail="Officer not found")
            
        return {"valid": True, "unique_id": unique_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/refresh-token", response_model=Token)
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(status_code=422, detail="Refresh token is required")
            
        payload = decode_access_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
            
        unique_id = payload.get("sub")
        if not unique_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        officer = db.query(Officer).options(
            Load(Officer).undefer(Officer.passport)
        ).filter_by(unique_id=unique_id).first()
        if not officer:
            raise HTTPException(status_code=401, detail="Officer not found")
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": officer.unique_id},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        # Don't reveal whether email exists for security
        # Generate a secure reset code
        reset_code = generate_reset_code()
        expires_at = datetime.utcnow() + timedelta(
            minutes=EMAIL_CONFIG["RESET_CODE_EXPIRE_MINUTES"]
        )
        
        # Create or update verification code
        existing_code = db.query(VerificationCode).filter_by(
            email=request.email,
            purpose="password_reset"
        ).first()
        
        if existing_code:
            existing_code.code = reset_code
            existing_code.expires_at = expires_at
        else:
            new_code = VerificationCode(
                email=request.email,
                code=reset_code,
                purpose="password_reset",
                expires_at=expires_at
            )
            db.add(new_code)
        db.commit()
        
        # Send email in background
        background_tasks.add_task(send_reset_email, request.email, reset_code)
        
        return {"message": "If the email exists, a reset code has been sent"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process password reset request"
        )

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        # Validate the reset code
        verification_code = db.query(VerificationCode).filter_by(
            email=request.email,
            code=request.code,
            purpose="password_reset"
        ).first()
        
        if not verification_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset code"
            )
        
        if verification_code.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired"
            )
        
        # Find the officer
        officer = db.query(Officer).filter_by(email=request.email).first()
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Update password
        officer.password_hash = hash_password(request.new_password)
        db.delete(verification_code)  # Remove used code
        db.commit()
        
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reset password"
        )

@router.get("/dashboard", response_model=OfficerResponse)
def get_dashboard(
    current_officer: Officer = Depends(get_current_officer),
    db: Session = Depends(get_db)
):
    # Explicitly refresh to ensure all fields are loaded
    db.refresh(current_officer)
    return current_officer