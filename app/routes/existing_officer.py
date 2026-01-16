# app/routes/existing_officer.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import logging

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_current_existing_officer_dict
from app.schemas.existing_officer import (
    ExistingOfficerVerify,
    ExistingOfficerRegister,
    ExistingOfficerResponse,
    ExistingOfficerDetailResponse,
    ExistingOfficerUpdate,
    ExistingOfficerDashboard,
    VerifyResponse,
    RegisterResponse,
    ExistingOfficerLogin
)
from app.services.existing_officer_service import ExistingOfficerService
from app.services.pdf_service import PDFService
from app.services.email_service import send_existing_officer_pdfs_email
from app.utils.jwt_handler import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/existing-officers",
    tags=["Existing Officers"]
)


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify existing officer credentials - UPDATED FORMAT",
    status_code=status.HTTP_200_OK
)
async def verify_officer_credentials(
    verify_data: ExistingOfficerVerify,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Verify an existing officer's credentials against the legacy system.
    
    NEW Officer ID Format: PREFIX/ALPHANUMERIC/INTAKE (e.g., MCN/001B/031)
    
    This endpoint checks if the officer ID and email exist in the legacy database
    and returns verification status.
    """
    try:
        logger.info(f"Verifying officer with NEW format: {verify_data.officer_id} with email: {verify_data.email}")
        
        # Log request origin for debugging
        origin = request.headers.get("origin")
        logger.info(f"Request from origin: {origin}")
        
        result = ExistingOfficerService.verify_officer(db, verify_data)
        
        # Log successful verification
        logger.info(f"Officer verification successful (NEW FORMAT): {verify_data.officer_id}")
        
        return VerifyResponse(**result)
        
    except HTTPException as he:
        logger.warning(f"HTTP Exception in verify: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Error verifying officer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during verification"
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register an existing officer - WITH NEW FIELDS",
    status_code=status.HTTP_201_CREATED
)
async def register_existing_officer(
    register_data: ExistingOfficerRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register an existing officer in the new system WITH NEW FIELDS:
    
    1. Date of Enlistment (Required)
    2. Date of Promotion (Optional)
    
    This creates a new record in the existing_officers table without requiring payment.
    The officer must be verified first using the /verify endpoint.
    """
    try:
        logger.info(f"Registering officer with NEW fields: {register_data.officer_id}")
        
        # Log request origin
        origin = request.headers.get("origin")
        logger.info(f"Registration request from origin: {origin}")
        
        officer = ExistingOfficerService.register_officer(db, register_data)
        
        logger.info(f"Officer registered successfully with enlistment date: {register_data.date_of_enlistment}")
        
        return RegisterResponse(
            status="success",
            message="Officer registered successfully",
            officer_id=officer.officer_id,
            email=officer.email,
            date_of_enlistment=officer.date_of_enlistment,
            date_of_promotion=officer.date_of_promotion,
            category=officer.category,
            registration_id=str(officer.id),
            next_steps=[
                "Upload required documents (Passport, NIN Slip, SSCE Certificate)",
                "Upload optional documents if available",
                "Wait for admin verification",
                "Login with your Officer ID and password"
            ]
        )
        
    except HTTPException as he:
        logger.warning(f"HTTP Exception in register: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Error registering officer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register officer"
        )


@router.post(
    "/upload-document",
    summary="Upload document for existing officer - WITH FILE VALIDATION",
    status_code=status.HTTP_200_OK
)
async def upload_document(
    officer_id: str = Form(..., description="Officer ID in NEW format"),
    document_type: str = Form(..., description="Type of document"),
    description: Optional[str] = Form(None, description="Document description"),
    file: UploadFile = File(..., description="Document file (max 10MB)"),
    db: Session = Depends(get_db)
):
    """
    Upload a document for an existing officer.
    
    REQUIRED Documents:
    - passport: Passport photo
    - nin_slip: NIN slip  
    - ssce: SSCE certificate
    
    OPTIONAL Documents:
    - birth_certificate: Birth certificate
    - appointment_letter: Letter of first appointment
    - promotion_letter: Promotion letters
    
    File Limits: Max 10MB, Allowed: PDF, JPG, JPEG, PNG
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
            "officer_id": officer_id,
            "is_required": document_type in ['passport', 'nin_slip', 'ssce']
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
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_existing_officer_dict)
):
    """
    Get detailed information about an existing officer.
    
    Includes NEW fields: date_of_enlistment, date_of_promotion
    """
    # Verify the officer is accessing their own data
    if current_officer.get("officer_id") != officer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this officer's data"
        )
    
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
    summary="Login for existing officers - OFFICER ID ONLY",
    status_code=status.HTTP_200_OK
)
async def login_existing_officer(
    login_data: ExistingOfficerLogin,
    db: Session = Depends(get_db)
):
    """
    Login endpoint for existing officers.
    
    NOTE: Uses Officer ID ONLY (no email option) as per master prompt.
    
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
            "officer_id": str(officer.id),
            "category": officer.category,
            "full_name": officer.full_name
        }
    )
    
    # Update last login timestamp
    officer.last_login = datetime.utcnow()
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "officer_id": officer.officer_id,
        "email": officer.email,
        "full_name": officer.full_name,
        "role": "existing_officer",
        "category": officer.category
    }


@router.post(
    "/{officer_id}/complete-registration",
    summary="Mark officer registration as complete",
    status_code=status.HTTP_200_OK
)
async def complete_registration(
    officer_id: str,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Mark an officer's registration as complete.
    
    This endpoint should be called when all required documents are uploaded.
    Automatically generates PDFs and sends email.
    """
    # Verify the officer is accessing their own data
    if current_officer.get("officer_id") != officer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to complete registration for this officer"
        )
    
    officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    # Check if required documents are uploaded (from master prompt)
    required_docs = ['passport_photo', 'nin_slip', 'ssce_certificate']
    missing_docs = []
    
    for doc in required_docs:
        if not getattr(officer, doc, None):
            missing_docs.append(doc.replace('_', ' ').title())
    
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required documents: {', '.join(missing_docs)}"
        )
    
    # Update status
    officer.status = 'pending_verification'
    officer.updated_at = datetime.utcnow()
    db.commit()
    
    # Generate PDFs in background if background_tasks is provided
    if background_tasks:
        background_tasks.add_task(
            generate_existing_officer_pdfs,
            officer_id=officer_id,
            db=db
        )
        
        return {
            "status": "success",
            "message": "Registration marked as complete. PDFs will be generated and emailed shortly.",
            "officer_id": officer_id,
            "missing_documents": False,
            "pdf_generation": "started"
        }
    else:
        # Generate PDFs synchronously
        await generate_existing_officer_pdfs(officer_id, db)
        
        return {
            "status": "success",
            "message": "Registration marked as complete. PDFs have been generated and emailed.",
            "officer_id": officer_id,
            "missing_documents": False,
            "pdf_generation": "completed"
        }


@router.get(
    "/{officer_id}/dashboard",
    response_model=ExistingOfficerDashboard,
    summary="Get existing officer dashboard data - NEW ENDPOINT"
)
async def get_existing_officer_dashboard(
    officer_id: str,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for existing officers - NEW ENDPOINT
    
    Returns all information needed for the existing officer dashboard:
    - Officer details with new fields
    - Document upload status
    - PDF availability
    - Dashboard access statistics
    """
    # Verify the officer is accessing their own dashboard
    if current_officer.get("officer_id") != officer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this dashboard"
        )
    
    try:
        dashboard_data = ExistingOfficerService.get_dashboard_data(db, officer_id)
        return dashboard_data
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data"
        )


@router.post(
    "/{officer_id}/generate-pdfs",
    summary="Generate PDFs for existing officer - NEW ENDPOINT"
)
async def generate_pdfs_for_officer(
    officer_id: str,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Manually trigger PDF generation for existing officer.
    
    Generates:
    1. Terms & Conditions PDF
    2. Existing Officer Registration Form PDF (NEW template)
    
    Sends both via email.
    """
    # Verify the officer is accessing their own data
    if current_officer.get("officer_id") != officer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to generate PDFs for this officer"
        )
    
    officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    # Check if all required documents are uploaded
    required_docs = ['passport_photo', 'nin_slip', 'ssce_certificate']
    missing_docs = []
    
    for doc in required_docs:
        if not getattr(officer, doc, None):
            missing_docs.append(doc.replace('_', ' ').title())
    
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate PDFs. Missing required documents: {', '.join(missing_docs)}"
        )
    
    # Add background task if available, otherwise generate synchronously
    if background_tasks:
        background_tasks.add_task(
            generate_existing_officer_pdfs,
            officer_id=officer_id,
            db=db
        )
        
        return {
            "status": "success",
            "message": "PDF generation started. You will receive an email when completed.",
            "officer_id": officer_id
        }
    else:
        await generate_existing_officer_pdfs(officer_id, db)
        
        return {
            "status": "success",
            "message": "PDFs generated and emailed successfully.",
            "officer_id": officer_id
        }


@router.post(
    "/logout",
    summary="Logout existing officer - NEW ENDPOINT"
)
async def logout_existing_officer(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Logout endpoint for existing officers.
    
    This endpoint updates last login timestamp and clears any session data.
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Logging out officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Update last login timestamp
        officer.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"Officer {officer_id} logged out successfully")
        
        return {
            "status": "success",
            "message": "Logged out successfully",
            "officer_id": officer_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout"
        )


# Background task function for PDF generation
async def generate_existing_officer_pdfs(officer_id: str, db: Session):
    """
    Background task to generate PDFs for existing officers
    """
    try:
        logger.info(f"Generating PDFs for existing officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            logger.error(f"Officer not found: {officer_id}")
            return
        
        # Generate PDFs using PDFService
        pdf_service = PDFService(db)
        
        # Generate Terms & Conditions PDF
        terms_pdf_path = pdf_service.generate_terms_conditions(
            str(officer.id),
            "existing_officer"
        )
        
        # Generate Existing Officer Registration Form PDF (NEW template)
        registration_pdf_path = pdf_service.generate_existing_officer_registration_form(
            str(officer.id)
        )
        
        # Update PDF paths in database
        ExistingOfficerService.update_pdf_paths(
            db,
            officer_id,
            terms_pdf_path,
            registration_pdf_path
        )
        
        # Send email with PDFs
        success = await send_existing_officer_pdfs_email(
            to_email=officer.email,
            name=officer.full_name,
            officer_id=officer.officer_id,
            terms_pdf_path=terms_pdf_path,
            registration_pdf_path=registration_pdf_path
        )
        
        if success:
            logger.info(f"PDFs generated and emailed successfully to {officer.email}")
        else:
            logger.error(f"Failed to send PDFs email to {officer.email}")
            
    except Exception as e:
        logger.error(f"Error generating PDFs for {officer_id}: {str(e)}")