# app/routes/admin_auth.py
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Body, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError
from enum import Enum
from pydantic import BaseModel, EmailStr
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
        
        # Hash password
        hashed_password = hash_password(admin_data.password)
        
        # Create new admin
        new_admin = Admin(
            email=admin_data.email.lower(),
            password=hashed_password,
            full_name=admin_data.full_name,
            phone=admin_data.phone,
            role=admin_data.role,
            is_active=True,
            is_super_admin=False
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
                "000000",  # Dummy OTP for welcome
                "admin_welcome"
            )
        
        logger.info(f"New admin created: {new_admin.email}")
        
        return AdminResponse(
            id=str(new_admin.id),
            email=new_admin.email,
            full_name=new_admin.full_name,
            phone=new_admin.phone,
            role=new_admin.role,
            is_active=new_admin.is_active,
            is_super_admin=new_admin.is_super_admin,
            created_at=new_admin.created_at
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
        if not verify_password(login_data.password, admin.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Generate 6-digit OTP
        import random
        otp = str(random.randint(100000, 999999))
        
        # Store OTP in database
        store_verification_code(
            db=db,
            email=admin.email.lower(),
            otp_code=otp,
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
        
        # Verify OTP
        is_valid = verify_otp(
            db=db,
            email=normalized_email,
            otp_code=otp_data.otp,
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
        
        # Update last login
        admin.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"Admin logged in: {admin.email}")
        
        # Return admin data without password
        admin_response = {
            "id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "phone": admin.phone,
            "role": admin.role,
            "is_active": admin.is_active,
            "is_super_admin": admin.is_super_admin,
            "last_login": admin.last_login.isoformat() if admin.last_login else None,
            "created_at": admin.created_at.isoformat() if admin.created_at else None
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
        
        # Get pending verifications
        pending_existing_officers = db.query(func.count(ExistingOfficer.id)).filter(
            ExistingOfficer.status == 'pending_verification'
        ).scalar() or 0
        
        logger.info(f"Admin dashboard accessed by: {current_admin.email}")
        
        return {
            "status": "success",
            "message": "Welcome to Admin Dashboard",
            "admin": {
                "id": str(current_admin.id),
                "email": current_admin.email,
                "full_name": current_admin.full_name,
                "role": current_admin.role,
                "is_super_admin": current_admin.is_super_admin,
                "last_login": current_admin.last_login.isoformat() if current_admin.last_login else None
            },
            "dashboard": {
                "total_officers": total_officers,
                "total_applicants": total_applicants,
                "total_existing_officers": total_existing_officers,
                "total_admins": total_admins,
                "pending_verifications": pending_existing_officers,
                "recent_activity": []
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
        
        # Store OTP
        store_verification_code(
            db=db,
            email=normalized_email,
            otp_code=otp,
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
        
        # Verify OTP
        is_valid = verify_otp(
            db=db,
            email=normalized_email,
            otp_code=otp,
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
        admin.password = hash_password(new_password)
        admin.updated_at = datetime.utcnow()
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
        phone=current_admin.phone,
        role=current_admin.role,
        is_active=current_admin.is_active,
        is_super_admin=current_admin.is_super_admin,
        created_at=current_admin.created_at,
        last_login=current_admin.last_login
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
        if update_data.full_name:
            current_admin.full_name = update_data.full_name
        if update_data.phone:
            current_admin.phone = update_data.phone
        
        current_admin.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_admin)
        
        logger.info(f"Admin profile updated: {current_admin.email}")
        
        return AdminResponse(
            id=str(current_admin.id),
            email=current_admin.email,
            full_name=current_admin.full_name,
            phone=current_admin.phone,
            role=current_admin.role,
            is_active=current_admin.is_active,
            is_super_admin=current_admin.is_super_admin,
            created_at=current_admin.created_at,
            last_login=current_admin.last_login
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
            "category": officer.category,
            "rank": officer.rank,
            "position": officer.position,
            "date_of_enlistment": officer.date_of_enlistment.isoformat() if officer.date_of_enlistment else None,
            "date_of_promotion": officer.date_of_promotion.isoformat() if officer.date_of_promotion else None,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "created_at": officer.created_at.isoformat() if officer.created_at else None,
            "updated_at": officer.updated_at.isoformat() if officer.updated_at else None
        } for officer in officers]
        
    except Exception as e:
        logger.error(f"Error getting existing officers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load existing officers"
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
    if not current_admin.is_super_admin:
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
            phone=admin.phone,
            role=admin.role,
            is_active=admin.is_active,
            is_super_admin=admin.is_super_admin,
            created_at=admin.created_at,
            last_login=admin.last_login
        ) for admin in admins]
        
    except Exception as e:
        logger.error(f"Error getting admins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admins"
        )