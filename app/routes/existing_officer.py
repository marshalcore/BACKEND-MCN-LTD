from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime  # ADDED THIS IMPORT

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.existing_officer import (
    ExistingOfficerVerify,
    ExistingOfficerRegister,
    ExistingOfficerResponse,
    ExistingOfficerDetailResponse,
    ExistingOfficerUpdate,
    VerifyResponse,
    RegisterResponse,
    ExistingOfficerLogin
)
from app.services.existing_officer_service import ExistingOfficerService
from app.utils.jwt_handler import create_access_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/existing-officers",
    tags=["Existing Officers"]
)


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify existing officer credentials",
    status_code=status.HTTP_200_OK
)
async def verify_officer_credentials(
    verify_data: ExistingOfficerVerify,
    db: Session = Depends(get_db)
):
    """
    Verify an existing officer's credentials against the legacy system.
    
    This endpoint checks if the officer ID and email exist in the legacy database
    and returns verification status.
    """
    try:
        result = ExistingOfficerService.verify_officer(db, verify_data)
        return VerifyResponse(**result)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error verifying officer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during verification"
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register an existing officer",
    status_code=status.HTTP_201_CREATED
)
async def register_existing_officer(
    register_data: ExistingOfficerRegister,
    db: Session = Depends(get_db)
):
    """
    Register an existing officer in the new system.
    
    This creates a new record in the existing_officers table without requiring payment.
    The officer must be verified first using the /verify endpoint.
    """
    try:
        officer = ExistingOfficerService.register_officer(db, register_data)
        
        return RegisterResponse(
            status="success",
            message="Officer registered successfully",
            officer_id=officer.officer_id,
            email=officer.email,
            next_steps=[
                "Upload required documents",
                "Wait for admin verification",
                "Login with your credentials"
            ]
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error registering officer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register officer"
        )


@router.post(
    "/upload-document",
    summary="Upload document for existing officer",
    status_code=status.HTTP_200_OK
)
async def upload_document(
    officer_id: str = Form(..., description="Officer ID"),
    document_type: str = Form(..., description="Type of document"),
    description: Optional[str] = Form(None, description="Document description"),
    file: UploadFile = File(..., description="Document file"),
    db: Session = Depends(get_db)
):
    """
    Upload a document for an existing officer.
    
    Allowed document types:
    - passport: Passport photo
    - nin_slip: NIN slip
    - ssce: SSCE certificate
    - birth_certificate: Birth certificate
    - appointment_letter: Letter of first appointment
    - promotion_letter: Promotion letters
    - service_certificate: Service certificate
    - medical_certificate: Medical certificate
    - guarantor_form: Guarantor form
    - other: Other documents
    """
    try:
        file_path = ExistingOfficerService.upload_document(
            db, officer_id, file, document_type, description
        )
        
        return {
            "status": "success",
            "message": "Document uploaded successfully",
            "file_path": file_path,
            "document_type": document_type,
            "officer_id": officer_id
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get(
    "/{officer_id}",
    response_model=ExistingOfficerDetailResponse,
    summary="Get existing officer details"
)
async def get_officer(
    officer_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about an existing officer.
    """
    officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    return officer


@router.get(
    "/",
    response_model=List[ExistingOfficerResponse],
    summary="Get all existing officers"
)
async def get_all_officers(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)  # Admin only
):
    """
    Get all existing officers (admin only).
    
    Optional query parameters:
    - status: Filter by status (pending, verified, approved, rejected)
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return
    """
    officers = ExistingOfficerService.get_all_officers(db, skip, limit, status)
    return officers


@router.patch(
    "/{officer_id}/status",
    response_model=ExistingOfficerResponse,
    summary="Update officer status (admin only)"
)
async def update_officer_status(
    officer_id: str,
    update_data: ExistingOfficerUpdate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Update the status of an existing officer (admin only).
    
    Can update:
    - status: pending, verified, approved, rejected
    - is_active: true/false
    - admin_notes: Administrative notes
    - rejection_reason: Reason for rejection
    """
    try:
        officer = ExistingOfficerService.update_officer_status(
            db, officer_id, update_data, admin.get("email", "admin")
        )
        return officer
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating officer status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update officer status"
        )


@router.post(
    "/login",
    summary="Login for existing officers",
    status_code=status.HTTP_200_OK
)
async def login_existing_officer(
    login_data: ExistingOfficerLogin,
    db: Session = Depends(get_db)
):
    """
    Login endpoint for existing officers.
    
    Returns JWT token for authenticated requests.
    """
    officer = ExistingOfficerService.authenticate_officer(
        db, login_data.officer_id, login_data.password
    )
    
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if officer is verified
    if not officer.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Officer account not yet verified by admin"
        )
    
    # Check if officer is active
    if not officer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Officer account is deactivated"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": officer.officer_id,
            "email": officer.email,
            "role": "existing_officer",
            "officer_id": str(officer.id)
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "officer_id": officer.officer_id,
        "email": officer.email,
        "full_name": officer.full_name,
        "role": "existing_officer"
    }


@router.post(
    "/{officer_id}/complete-registration",
    summary="Mark officer registration as complete",
    status_code=status.HTTP_200_OK
)
async def complete_registration(
    officer_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark an officer's registration as complete.
    
    This endpoint should be called when all required documents are uploaded.
    """
    officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    # Check if required documents are uploaded
    required_docs = ['passport_photo', 'nin_slip', 'ssce_certificate']
    missing_docs = []
    
    for doc in required_docs:
        if not getattr(officer, doc, None):
            missing_docs.append(doc)
    
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required documents: {', '.join(missing_docs)}"
        )
    
    # Update status
    officer.status = 'pending_verification'
    officer.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "success",
        "message": "Registration marked as complete. Awaiting admin verification.",
        "officer_id": officer_id
    }