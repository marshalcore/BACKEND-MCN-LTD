# app/routes/admin_auth.py
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Body, Request, BackgroundTasks, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError
from enum import Enum
from pydantic import BaseModel, EmailStr
import logging
import uuid

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
from app.utils.jwt_handler import create_access_token as create_jwt_access_token, create_refresh_token
from app.utils.otp import normalize_purpose
from app.models.existing_officer import ExistingOfficer

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/admin",
    tags=["Admin Authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login", auto_error=False)

# ------------------ Pydantic Schemas ------------------

class OTPPurpose(str, Enum):
    login = "login"
    signup = "signup"
    password_reset = "password_reset"
    officer_signup = "officer_signup"
    admin_login = "admin_login"

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int

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

class StatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    admin_notes: Optional[str] = None

# ------------------ Authentication Dependencies ------------------

async def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current admin from JWT token with proper validation
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Check token type
        token_type = payload.get("type", "access")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        admin_email = payload.get("sub")
        if admin_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        admin = db.query(Admin).filter(Admin.email == admin_email).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive"
            )
        
        return admin
        
    except JWTError as e:
        if "expired" in str(e).lower():
            logger.error("JWT Error: Signature has expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please login again or use refresh token."
            )
        else:
            logger.error(f"JWT Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except Exception as e:
        logger.error(f"JWT Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

# ------------------ Authentication Endpoints ------------------

@router.post("/signup", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def admin_signup(
    admin_data: AdminSignup,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Create a new admin account
    """
    try:
        # Check if admin already exists
        existing_admin = db.query(Admin).filter(func.lower(Admin.email) == func.lower(admin_data.email)).first()
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin with this email already exists"
            )
        
        # Hash password and store in hashed_password field
        hashed_password = hash_password(admin_data.password)
        
        # Create new admin
        new_admin = Admin(
            email=admin_data.email.lower(),
            hashed_password=hashed_password,
            full_name=admin_data.full_name,
            is_active=True,
            is_superuser=False,
            is_verified=False
        )
        
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        
        # Send welcome email if background tasks available
        if background_tasks:
            background_tasks.add_task(
                send_otp_email,
                new_admin.email,
                new_admin.full_name,
                "000000",
                "admin_welcome"
            )
        
        logger.info(f"New admin created: {new_admin.email}")
        
        return AdminResponse(
            id=str(new_admin.id),
            email=new_admin.email,
            full_name=new_admin.full_name,
            is_superuser=new_admin.is_superuser,
            is_verified=new_admin.is_verified,
            is_active=new_admin.is_active
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating admin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create admin account"
        )

@router.post("/login", status_code=status.HTTP_200_OK)
async def admin_login(
    login_data: AdminLogin,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Admin login - Sends OTP to admin email for verification
    """
    try:
        # Case-insensitive email lookup
        admin = db.query(Admin).filter(func.lower(Admin.email) == func.lower(login_data.email)).first()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive"
            )
        
        # Verify password
        if not verify_password(login_data.password, admin.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Generate 6-digit OTP
        import random
        otp = str(random.randint(100000, 999999))
        
        # Store OTP in database - FIXED PARAMETER NAME
        store_verification_code(
            db=db,
            email=admin.email.lower(),
            code=otp,  # CHANGE FROM otp_code to code
            purpose="admin_login"
        )
        
        # Send OTP via email
        background_tasks.add_task(
            send_otp_email,
            admin.email,
            admin.full_name,
            otp,
            "admin_login"
        )
        
        logger.info(f"OTP sent successfully to {admin.email}")
        
        return {
            "status": "success",
            "message": "OTP sent to email",
            "email": admin.email,
            "requires_otp": True
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in admin login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp_login(
    otp_data: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verify OTP and return JWT tokens
    """
    try:
        normalized_email = otp_data.email.strip().lower()
        logger.info(f"OTP verification for: {normalized_email} | Purpose: {otp_data.purpose}")
        
        # Verify OTP - FIXED: using otp_data.code
        is_valid = verify_otp(
            db=db,
            email=normalized_email,
            code=otp_data.code,  # USE code NOT otp or otp_code
            purpose=otp_data.purpose
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
        
        # Get admin
        admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        # Create access token (24 hours)
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_jwt_access_token(
            data={
                "sub": admin.email,
                "role": "admin",
                "admin_id": str(admin.id),
                "type": "access"
            },
            expires_delta=access_token_expires
        )
        
        # Create refresh token (30 days)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            data={
                "sub": admin.email,
                "role": "admin",
                "type": "refresh"
            },
            expires_delta=refresh_token_expires
        )
        
        # Update last login - SAFE ACCESS (handle missing column)
        if hasattr(admin, 'last_login'):
            admin.last_login = datetime.utcnow()
            db.commit()
        
        logger.info(f"Admin logged in: {admin.email}")
        
        # Return admin data without password - SAFE ACCESS to last_login
        last_login_value = None
        if hasattr(admin, 'last_login') and admin.last_login:
            last_login_value = admin.last_login.isoformat()
        
        admin_response = {
            "id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "is_superuser": admin.is_superuser,
            "is_verified": admin.is_verified,
            "is_active": admin.is_active,
            "last_login": last_login_value,
        }
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            "admin": admin_response,
            "message": "Login successful"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in OTP verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/refresh-token", status_code=status.HTTP_200_OK)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Refresh expired JWT token using refresh token
    """
    try:
        # Get refresh token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required"
            )
        
        refresh_token = auth_header.split(" ")[1]
        
        # Verify refresh token
        try:
            payload = jwt.decode(
                refresh_token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            
            # Check if token is a refresh token
            token_type = payload.get("type")
            if token_type != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            # Get admin from database
            admin_email = payload.get("sub")
            admin = db.query(Admin).filter(Admin.email == admin_email).first()
            
            if not admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Admin not found"
                )
            
            if not admin.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin account is inactive"
                )
            
            # Create new access token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_jwt_access_token(
                data={
                    "sub": admin.email,
                    "role": "admin",
                    "admin_id": str(admin.id),
                    "type": "access"
                },
                expires_delta=access_token_expires
            )
            
            logger.info(f"Token refreshed for admin: {admin.email}")
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "admin_email": admin.email
            }
            
        except JWTError as e:
            if "expired" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has expired. Please login again."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/dashboard", status_code=status.HTTP_200_OK)
async def admin_dashboard(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin dashboard with statistics
    """
    try:
        # Get counts
        total_officers = db.query(func.count(Officer.id)).scalar() or 0
        total_applicants = db.query(func.count(Applicant.id)).scalar() or 0
        total_existing_officers = db.query(func.count(ExistingOfficer.id)).scalar() or 0
        total_admins = db.query(func.count(Admin.id)).scalar() or 0
        
        # Get pending verifications - FIXED: Check both statuses
        pending_existing_officers = db.query(func.count(ExistingOfficer.id)).filter(
            ExistingOfficer.status.in_(['pending_verification', 'pending'])
        ).scalar() or 0
        
        # Get pending existing officers for approval queue
        pending_approvals = db.query(func.count(ExistingOfficer.id)).filter(
            ExistingOfficer.status == 'pending'
        ).scalar() or 0
        
        # Get recent activity (last 10)
        recent_officers = db.query(ExistingOfficer).order_by(ExistingOfficer.created_at.desc()).limit(10).all()
        
        recent_activity = []
        for officer in recent_officers:
            recent_activity.append({
                "officer_id": officer.officer_id,
                "full_name": officer.full_name,
                "status": officer.status,
                "created_at": officer.created_at.isoformat() if officer.created_at else None
            })
        
        logger.info(f"Admin dashboard accessed by: {current_admin.email}")
        
        # SAFE ACCESS to last_login (handle missing database column)
        last_login_value = None
        if hasattr(current_admin, 'last_login') and current_admin.last_login:
            last_login_value = current_admin.last_login.isoformat()
        
        return {
            "status": "success",
            "message": "Welcome to Admin Dashboard",
            "admin": {
                "id": str(current_admin.id),
                "email": current_admin.email,
                "full_name": current_admin.full_name,
                "is_superuser": current_admin.is_superuser,
                "last_login": last_login_value
            },
            "dashboard": {
                "total_officers": total_officers,
                "total_applicants": total_applicants,
                "total_existing_officers": total_existing_officers,
                "total_admins": total_admins,
                "pending_verifications": pending_existing_officers,
                "pending_approvals": pending_approvals,
                "recent_activity": recent_activity
            }
        }
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard"
        )

@router.post("/reset-password/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    email: str = Body(..., embed=True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Request password reset - sends OTP to email
    """
    try:
        normalized_email = email.strip().lower()
        admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        # Generate OTP
        import random
        otp = str(random.randint(100000, 999999))
        
        # Store OTP - FIXED PARAMETER NAME
        store_verification_code(
            db=db,
            email=normalized_email,
            code=otp,
            purpose="password_reset"
        )
        
        # Send OTP via email
        if background_tasks:
            background_tasks.add_task(
                send_password_reset_email,
                normalized_email,
                admin.full_name,
                otp
            )
        
        logger.info(f"Password reset OTP sent to: {normalized_email}")
        
        return {
            "status": "success",
            "message": "Password reset OTP sent to email",
            "email": normalized_email
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error requesting password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request password reset"
        )

@router.post("/reset-password/verify", status_code=status.HTTP_200_OK)
async def verify_password_reset(
    email: str = Body(..., embed=True),
    otp: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Verify OTP and reset password
    """
    try:
        normalized_email = email.strip().lower()
        
        # Verify OTP - FIXED PARAMETER NAME
        is_valid = verify_otp(
            db=db,
            email=normalized_email,
            code=otp,
            purpose="password_reset"
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
        
        # Get admin
        admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        # Update password
        admin.hashed_password = hash_password(new_password)
        db.commit()
        
        logger.info(f"Password reset successful for: {normalized_email}")
        
        return {
            "status": "success",
            "message": "Password reset successful",
            "email": normalized_email
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.get("/profile", status_code=status.HTTP_200_OK)
async def get_admin_profile(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get current admin profile
    """
    return AdminResponse(
        id=str(current_admin.id),
        email=current_admin.email,
        full_name=current_admin.full_name,
        is_superuser=current_admin.is_superuser,
        is_verified=current_admin.is_verified,
        is_active=current_admin.is_active
    )

@router.put("/profile", status_code=status.HTTP_200_OK)
async def update_admin_profile(
    update_data: AdminUpdateUser,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update admin profile
    """
    try:
        # Update fields
        if update_data.email:
            current_admin.email = update_data.email
        if update_data.full_name:
            current_admin.full_name = update_data.full_name
        
        db.commit()
        db.refresh(current_admin)
        
        logger.info(f"Admin profile updated: {current_admin.email}")
        
        return AdminResponse(
            id=str(current_admin.id),
            email=current_admin.email,
            full_name=current_admin.full_name,
            is_superuser=current_admin.is_superuser,
            is_verified=current_admin.is_verified,
            is_active=current_admin.is_active
        )
        
    except Exception as e:
        logger.error(f"Error updating admin profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/logout", status_code=status.HTTP_200_OK)
async def admin_logout(
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Admin logout endpoint
    """
    logger.info(f"Admin logged out: {current_admin.email}")
    
    return {
        "status": "success",
        "message": "Logged out successfully"
    }

# ------------------ Existing Officers Management ------------------

@router.get("/existing-officers", status_code=status.HTTP_200_OK)
async def get_all_existing_officers(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all existing officers (admin only)
    """
    try:
        query = db.query(ExistingOfficer)
        
        if status:
            query = query.filter(ExistingOfficer.status == status)
        
        officers = query.order_by(ExistingOfficer.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(officer.id),
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "category": officer.category,
            "rank": officer.rank,
            "position": officer.position,
            "date_of_enlistment": officer.date_of_enlistment.isoformat() if officer.date_of_enlistment else None,
            "date_of_promotion": officer.date_of_promotion.isoformat() if officer.date_of_promotion else None,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "nin_number": officer.nin_number,
            "years_of_service": officer.years_of_service,
            "service_number": officer.service_number,
            "bank_name": officer.bank_name,
            "account_number": officer.account_number,
            "residential_address": officer.residential_address,
            "state_of_origin": officer.state_of_origin,
            "state_of_residence": officer.state_of_residence,
            "admin_notes": officer.admin_notes,
            "rejection_reason": officer.rejection_reason,
            "created_at": officer.created_at.isoformat() if officer.created_at else None,
            "updated_at": officer.updated_at.isoformat() if officer.updated_at else None
        } for officer in officers]
        
    except Exception as e:
        logger.error(f"Error getting existing officers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load existing officers"
        )

@router.get("/existing-officers/{officer_id:path}", status_code=status.HTTP_200_OK)
async def get_existing_officer(
    officer_id: str = Path(..., description="Officer ID (may contain slashes like MCN/001B/001)"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get a specific existing officer by officer_id
    """
    try:
        logger.info(f"🔍 Looking for officer with ID: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.officer_id == officer_id).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Officer not found with ID: {officer_id}"
            )
        
        logger.info(f"✅ Found officer: {officer.full_name} ({officer_id})")
        
        return {
            "id": str(officer.id),
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "category": officer.category,
            "rank": officer.rank,
            "position": officer.position,
            "date_of_enlistment": officer.date_of_enlistment.isoformat() if officer.date_of_enlistment else None,
            "date_of_promotion": officer.date_of_promotion.isoformat() if officer.date_of_promotion else None,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "nin_number": officer.nin_number,
            "gender": officer.gender,
            "date_of_birth": officer.date_of_birth.isoformat() if officer.date_of_birth else None,
            "place_of_birth": officer.place_of_birth,
            "nationality": officer.nationality,
            "marital_status": officer.marital_status,
            "residential_address": officer.residential_address,
            "state_of_residence": officer.state_of_residence,
            "local_government_residence": officer.local_government_residence,
            "country_of_residence": officer.country_of_residence,
            "state_of_origin": officer.state_of_origin,
            "local_government_origin": officer.local_government_origin,
            "years_of_service": officer.years_of_service,
            "service_number": officer.service_number,
            "religion": officer.religion,
            "additional_skills": officer.additional_skills,
            "bank_name": officer.bank_name,
            "account_number": officer.account_number,
            "passport_photo": officer.passport_photo,
            "nin_slip": officer.nin_slip,
            "ssce_certificate": officer.ssce_certificate,
            "birth_certificate": officer.birth_certificate,
            "letter_of_first_appointment": officer.letter_of_first_appointment,
            "promotion_letters": officer.promotion_letters,
            "admin_notes": officer.admin_notes,
            "rejection_reason": officer.rejection_reason,
            "created_at": officer.created_at.isoformat() if officer.created_at else None,
            "updated_at": officer.updated_at.isoformat() if officer.updated_at else None,
            "verification_date": officer.verification_date.isoformat() if officer.verification_date else None,
            "verified_by": officer.verified_by,
            "last_login": officer.last_login.isoformat() if officer.last_login else None,
            "dashboard_access_count": officer.dashboard_access_count,
            "last_dashboard_access": officer.last_dashboard_access.isoformat() if officer.last_dashboard_access else None
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting existing officer {officer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load officer details for {officer_id}"
        )

@router.put("/existing-officers/{officer_id:path}/approve", status_code=status.HTTP_200_OK)
async def approve_existing_officer(
    officer_id: str = Path(..., description="Officer ID (may contain slashes like MCN/001B/001)"),
    update_data: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Approve an existing officer
    """
    try:
        logger.info(f"✅ Approving officer: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.officer_id == officer_id).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Officer not found with ID: {officer_id}"
            )
        
        # Update officer status
        officer.status = "approved"
        officer.is_verified = True
        officer.verification_date = datetime.utcnow()
        officer.verified_by = current_admin.email
        officer.is_active = True
        
        if update_data.reason:
            officer.admin_notes = f"Approved by {current_admin.email}: {update_data.reason}"
        
        if update_data.admin_notes:
            officer.admin_notes = update_data.admin_notes
        
        db.commit()
        db.refresh(officer)
        
        logger.info(f"Officer {officer_id} approved by admin: {current_admin.email}")
        
        return {
            "status": "success",
            "message": "Officer approved successfully",
            "officer_id": officer.officer_id,
            "status": officer.status,
            "verified_by": officer.verified_by,
            "verification_date": officer.verification_date.isoformat() if officer.verification_date else None
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error approving officer {officer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve officer {officer_id}"
        )

@router.put("/existing-officers/{officer_id:path}/reject", status_code=status.HTTP_200_OK)
async def reject_existing_officer(
    officer_id: str = Path(..., description="Officer ID (may contain slashes like MCN/001B/001)"),
    update_data: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Reject an existing officer
    """
    try:
        logger.info(f"❌ Rejecting officer: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.officer_id == officer_id).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Officer not found with ID: {officer_id}"
            )
        
        # Update officer status
        officer.status = "rejected"
        officer.is_verified = False
        officer.is_active = False
        
        if update_data.reason:
            officer.rejection_reason = update_data.reason
        
        if update_data.admin_notes:
            officer.admin_notes = update_data.admin_notes
        
        db.commit()
        db.refresh(officer)
        
        logger.info(f"Officer {officer_id} rejected by admin: {current_admin.email}")
        
        return {
            "status": "success",
            "message": "Officer rejected successfully",
            "officer_id": officer.officer_id,
            "status": officer.status,
            "rejection_reason": officer.rejection_reason
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error rejecting officer {officer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject officer {officer_id}"
        )

@router.put("/existing-officers/{officer_id:path}/verify", status_code=status.HTTP_200_OK)
async def verify_existing_officer(
    officer_id: str = Path(..., description="Officer ID (may contain slashes like MCN/001B/001)"),
    update_data: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Verify an existing officer (manual verification)
    """
    try:
        logger.info(f"🔍 Verifying officer: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.officer_id == officer_id).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Officer not found with ID: {officer_id}"
            )
        
        # Update officer verification status
        officer.status = "verified"
        officer.is_verified = True
        officer.verification_date = datetime.utcnow()
        officer.verified_by = current_admin.email
        officer.is_active = True
        
        if update_data.reason:
            officer.admin_notes = f"Verified by {current_admin.email}: {update_data.reason}"
        
        if update_data.admin_notes:
            officer.admin_notes = update_data.admin_notes
        
        db.commit()
        db.refresh(officer)
        
        logger.info(f"Officer {officer_id} verified by admin: {current_admin.email}")
        
        return {
            "status": "success",
            "message": "Officer verified successfully",
            "officer_id": officer.officer_id,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "verified_by": officer.verified_by,
            "verification_date": officer.verification_date.isoformat() if officer.verification_date else None
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error verifying officer {officer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify officer {officer_id}"
        )

@router.put("/existing-officers/{officer_id:path}/status", status_code=status.HTTP_200_OK)
async def update_officer_status(
    officer_id: str = Path(..., description="Officer ID (may contain slashes like MCN/001B/001)"),
    update_data: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Update officer status (general endpoint)
    """
    try:
        logger.info(f"✏️ Updating status for officer: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.officer_id == officer_id).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Officer not found with ID: {officer_id}"
            )
        
        # Validate status
        valid_statuses = ["pending", "verified", "approved", "rejected"]
        if update_data.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update status
        old_status = officer.status
        officer.status = update_data.status
        
        # Set verification flags based on status
        if update_data.status in ["verified", "approved"]:
            officer.is_verified = True
            officer.verification_date = datetime.utcnow()
            officer.verified_by = current_admin.email
            officer.is_active = True
        elif update_data.status == "rejected":
            officer.is_verified = False
            officer.is_active = False
            if update_data.reason:
                officer.rejection_reason = update_data.reason
        
        # Update admin notes
        notes = f"Status changed from {old_status} to {update_data.status} by {current_admin.email}"
        if update_data.reason:
            notes += f". Reason: {update_data.reason}"
        if update_data.admin_notes:
            officer.admin_notes = update_data.admin_notes
        else:
            officer.admin_notes = notes
        
        db.commit()
        db.refresh(officer)
        
        logger.info(f"Officer {officer_id} status updated from {old_status} to {update_data.status} by admin: {current_admin.email}")
        
        return {
            "status": "success",
            "message": "Officer status updated successfully",
            "officer_id": officer.officer_id,
            "old_status": old_status,
            "new_status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "admin_notes": officer.admin_notes
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating officer {officer_id} status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update officer {officer_id} status"
        )

@router.get("/existing-officers/pending", status_code=status.HTTP_200_OK)
async def get_pending_existing_officers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get pending existing officers for approval queue
    """
    try:
        officers = db.query(ExistingOfficer).filter(
            ExistingOfficer.status == 'pending'
        ).order_by(ExistingOfficer.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(officer.id),
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "rank": officer.rank,
            "position": officer.position,
            "date_of_enlistment": officer.date_of_enlistment.isoformat() if officer.date_of_enlistment else None,
            "status": officer.status,
            "created_at": officer.created_at.isoformat() if officer.created_at else None
        } for officer in officers]
        
    except Exception as e:
        logger.error(f"Error getting pending officers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load pending officers"
        )

# ------------------ Officer Management ------------------

@router.get("/officers", status_code=status.HTTP_200_OK)
async def get_all_officers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all officers
    """
    try:
        officers = db.query(Officer).order_by(Officer.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(officer.id),
            "unique_id": officer.unique_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "rank": officer.rank,
            "position": officer.position,
            "is_active": officer.is_active,
            "created_at": officer.created_at.isoformat() if officer.created_at else None
        } for officer in officers]
        
    except Exception as e:
        logger.error(f"Error getting officers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load officers"
        )

# ------------------ Applicant Management ------------------

@router.get("/applicants", status_code=status.HTTP_200_OK)
async def get_all_applicants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all applicants
    """
    try:
        applicants = db.query(Applicant).order_by(Applicant.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(applicant.id),
            "unique_id": applicant.unique_id,
            "full_name": applicant.full_name,
            "email": applicant.email,
            "phone_number": applicant.phone_number,
            "is_verified": applicant.is_verified,
            "created_at": applicant.created_at.isoformat() if applicant.created_at else None
        } for applicant in applicants]
        
    except Exception as e:
        logger.error(f"Error getting applicants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load applicants"
        )

# ------------------ Admin Management ------------------

@router.get("/admins", status_code=status.HTTP_200_OK)
async def get_all_admins(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all admins (super admin only)
    """
    if not current_admin.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can list all admins"
        )
    
    try:
        admins = db.query(Admin).all()
        
        return [AdminResponse(
            id=str(admin.id),
            email=admin.email,
            full_name=admin.full_name,
            is_superuser=admin.is_superuser,
            is_verified=admin.is_verified,
            is_active=admin.is_active
        ) for admin in admins]
        
    except Exception as e:
        logger.error(f"Error getting admins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admins"
        )

# ------------------ Additional Admin Endpoints for Frontend Compatibility ------------------

@router.get("/all-applicants", status_code=status.HTTP_200_OK)
async def get_all_applicants_admin(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all applicants (frontend compatibility endpoint)
    """
    try:
        applicants = db.query(Applicant).order_by(Applicant.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(applicant.id),
            "unique_id": applicant.unique_id,
            "full_name": applicant.full_name,
            "email": applicant.email,
            "phone_number": applicant.phone_number,
            "is_verified": applicant.is_verified,
            "created_at": applicant.created_at.isoformat() if applicant.created_at else None
        } for applicant in applicants]
        
    except Exception as e:
        logger.error(f"Error getting applicants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load applicants"
        )

@router.get("/all-officers", status_code=status.HTTP_200_OK)
async def get_all_officers_admin(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all officers (frontend compatibility endpoint)
    """
    try:
        officers = db.query(Officer).order_by(Officer.created_at.desc()).offset(skip).limit(limit).all()
        
        return [{
            "id": str(officer.id),
            "unique_id": officer.unique_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "rank": officer.rank,
            "position": officer.position,
            "is_active": officer.is_active,
            "created_at": officer.created_at.isoformat() if officer.created_at else None
        } for officer in officers]
        
    except Exception as e:
        logger.error(f"Error getting officers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load officers"
        )

@router.get("/all-admins", status_code=status.HTTP_200_OK)
async def get_all_admins_admin(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Get all admins (frontend compatibility endpoint) - FIXED: Safe access to created_at
    """
    try:
        admins = db.query(Admin).all()
        
        result = []
        for admin in admins:
            # SAFE ACCESS to created_at (handle missing database column)
            created_at_value = None
            if hasattr(admin, 'created_at') and admin.created_at:
                created_at_value = admin.created_at.isoformat()
            elif not hasattr(admin, 'created_at'):
                # If column doesn't exist, use current time as default
                created_at_value = datetime.utcnow().isoformat()
            
            result.append({
                "id": str(admin.id),
                "email": admin.email,
                "full_name": admin.full_name,
                "is_superuser": admin.is_superuser,
                "is_active": admin.is_active,
                "created_at": created_at_value
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting admins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admins"
        )

@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_admin_otp(
    email: str = Body(..., embed=True),
    purpose: str = Body(..., embed=True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Resend OTP to admin email
    """
    try:
        normalized_email = email.strip().lower()
        
        # Check if admin exists
        admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        # Generate new OTP
        import random
        otp = str(random.randint(100000, 999999))
        
        # Store OTP - FIXED PARAMETER NAME
        store_verification_code(
            db=db,
            email=normalized_email,
            code=otp,
            purpose=purpose
        )
        
        # Send OTP via email
        if background_tasks:
            background_tasks.add_task(
                send_otp_email,
                normalized_email,
                admin.full_name,
                otp,
                purpose
            )
        
        logger.info(f"OTP resent to: {normalized_email}")
        
        return {
            "status": "success",
            "message": "OTP resent to your email",
            "email": normalized_email
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error resending OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend OTP"
        )