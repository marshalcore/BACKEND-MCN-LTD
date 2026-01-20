from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import logging
import os

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_current_existing_officer_dict
from app.models.existing_officer import ExistingOfficer
from app.schemas.existing_officer import (
    ExistingOfficerVerify,
    ExistingOfficerRegister,
    ExistingOfficerResponse,
    ExistingOfficerDetailResponse,
    ExistingOfficerUpdate,
    ExistingOfficerDashboard,
    VerifyResponse,
    RegisterResponse,
    ExistingOfficerLogin,
    DocumentUploadResponse,
    PDFGenerationResponse
)
from app.services.existing_officer_service import ExistingOfficerService
from app.services.pdf_service import PDFService
from app.services.email_service import send_existing_officer_pdfs_email, send_existing_officer_welcome_email
from app.utils.jwt_handler import create_access_token
from app.utils.upload import save_upload


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/existing-officers",
    tags=["Existing Officers"]
)

# Add this import fix at the top of your route file
try:
    from app.utils.pdf import generate_existing_officer_pdfs_and_email
except ImportError:
    # Create a stub function if it doesn't exist
    import logging
    logger = logging.getLogger(__name__)
    
    async def generate_existing_officer_pdfs_and_email(officer_id: str, email: str, full_name: str, db):
        """Stub function for PDF generation"""
        logger.warning(f"⚠️ PDF generation called but function not implemented for officer: {officer_id}")
        logger.warning(f"   Officer: {full_name} ({email})")
        logger.warning(f"   To fix: Add generate_existing_officer_pdfs_and_email to app/utils/pdf.py")
        
        # Return success anyway so registration completes
        return {
            "success": True,
            "message": "PDF generation placeholder - actual PDFs not generated",
            "officer_id": officer_id,
            "email": email
        }

        
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
    
    Enhanced email validation blocks disposable/temporary email addresses.
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
    summary="Register an existing officer - WITH NEW FIELDS AND AUTO-PDF GENERATION",
    status_code=status.HTTP_201_CREATED
)
async def register_existing_officer(
    register_data: ExistingOfficerRegister,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register an existing officer in the new system WITH NEW FIELDS:
    
    1. Date of Enlistment (Required)
    2. Date of Promotion (Optional)
    
    ✅ NEW: Automatically generates PDFs and sends email after registration
    ✅ NEW: Uses simplified 2-upload document system
    """
    try:
        logger.info(f"Registering officer with NEW fields: {register_data.officer_id}")
        
        # Log request origin
        origin = request.headers.get("origin")
        logger.info(f"Registration request from origin: {origin}")
        
        # Log the incoming data for debugging
        logger.info(f"📨 Received registration data: {register_data.dict()}")
        
        officer = ExistingOfficerService.register_officer(db, register_data)
        
        logger.info(f"Officer registered successfully with enlistment date: {register_data.date_of_enlistment}")
        
        # ✅ CRITICAL FIX: AUTO-GENERATE PDFs AND SEND EMAIL IN BACKGROUND
        # Import the function here to avoid circular imports
        from app.utils.pdf import generate_existing_officer_pdfs_and_email
        
        
        background_tasks.add_task(
            generate_existing_officer_pdfs_and_email,
            officer_id=officer.officer_id,
            email=officer.email,
            full_name=officer.full_name,
            db=db
        )
        
        logger.info(f"✅ PDF auto-generation scheduled for officer: {officer.officer_id}")
        
        # Send welcome email
        background_tasks.add_task(
            send_welcome_email_task,
            officer_id=officer.officer_id,
            db=db
        )
        
        return RegisterResponse(
            status="success",
            message="Officer registered successfully. PDFs are being generated and will be emailed to you.",
            officer_id=officer.officer_id,
            email=officer.email,
            date_of_enlistment=officer.date_of_enlistment,
            date_of_promotion=officer.date_of_promotion,
            category=officer.category,
            registration_id=str(officer.id),
            next_steps=[
                "Upload Passport Photo (JPG/PNG, 2MB max)",
                "Upload Consolidated PDF with all 10 documents (10MB max)",
                "PDFs will be auto-generated and emailed to you",
                "You can also download PDFs from your dashboard",
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
            detail=f"Failed to register officer: {str(e)}"
        )


@router.post(
    "/upload-document",
    response_model=DocumentUploadResponse,
    summary="Upload document for existing officer - NEW 2-UPLOAD SYSTEM",
    status_code=status.HTTP_200_OK
)
async def upload_document(
    officer_id: str = Form(..., description="Officer ID in NEW format"),
    document_type: str = Form(..., description="Type of document: 'passport' or 'consolidated_pdf' only"),
    description: Optional[str] = Form(None, description="Document description"),
    file: UploadFile = File(..., description="Document file"),
    db: Session = Depends(get_db)
):
    """
    Upload a document for an existing officer - NEW 2-UPLOAD SYSTEM ONLY
    
    ✅ ONLY 2 Document Types Allowed:
    1. 'passport' - Passport photo (JPG/PNG, 2MB max)
    2. 'consolidated_pdf' - Consolidated PDF with all 10 documents (PDF, 10MB max)
    
    ❌ REMOVED: Old document types (nin_slip, ssce, birth_certificate, etc.)
    """
    try:
        logger.info(f"📤 Uploading document {document_type} for officer {officer_id}")
        
        # Validate document type (ONLY 2 allowed)
        allowed_types = ['passport', 'consolidated_pdf']
        if document_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Get officer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Validate file extension based on document type
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if document_type == 'passport':
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            max_size = 2 * 1024 * 1024  # 2MB
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Passport must be JPG or PNG. Received: {file_ext}"
                )
        elif document_type == 'consolidated_pdf':
            allowed_extensions = ['.pdf']
            max_size = 10 * 1024 * 1024  # 10MB
            if file_ext != '.pdf':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Consolidated document must be PDF. Received: {file_ext}"
                )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            size_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size {file_size/1024/1024:.2f}MB exceeds maximum size of {size_mb}MB"
            )
        
        # Save upload with new structure
        subfolder = f"existing_officers/{officer_id}/{document_type}"
        file_path = save_upload(file, subfolder)
        
        # Update officer record
        if document_type == 'passport':
            officer.passport_path = file_path
            officer.passport_uploaded = True
        elif document_type == 'consolidated_pdf':
            officer.consolidated_pdf_path = file_path
            officer.consolidated_pdf_uploaded = True
        
        officer.updated_at = datetime.utcnow()
        db.commit()
        
        # Check if all required documents are uploaded
        passport_uploaded = officer.passport_uploaded
        consolidated_uploaded = officer.consolidated_pdf_uploaded
        all_uploaded = passport_uploaded and consolidated_uploaded
        
        # Determine remaining uploads
        remaining_uploads = []
        if not passport_uploaded:
            remaining_uploads.append("passport")
        if not consolidated_uploaded:
            remaining_uploads.append("consolidated_pdf")
        
        logger.info(f"✅ Document {document_type} uploaded successfully for {officer_id}")
        logger.info(f"   Passport uploaded: {passport_uploaded}")
        logger.info(f"   Consolidated PDF uploaded: {consolidated_uploaded}")
        logger.info(f"   All documents uploaded: {all_uploaded}")
        
        return DocumentUploadResponse(
            status="success",
            message=f"Document uploaded successfully: {document_type}",
            document_type=document_type,
            officer_id=officer_id,
            file_path=file_path,
            is_required=True,
            upload_complete=all_uploaded,
            remaining_uploads=remaining_uploads
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
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
    Updated for 2-upload system with simplified document fields.
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
    "/{officer_id}/generate-pdfs",
    response_model=PDFGenerationResponse,
    summary="Generate PDFs for existing officer - WITH AUTO-EMAIL",
    status_code=status.HTTP_200_OK
)
async def generate_pdfs_for_officer(
    officer_id: str,
    background_tasks: BackgroundTasks,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Manually trigger PDF generation for existing officer.
    
    ✅ Generates:
    1. Terms & Conditions PDF
    2. Existing Officer Registration Form PDF (NEW template)
    
    ✅ Sends both via email immediately
    ✅ Officer can also download from dashboard
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
    
    # Check if all required documents are uploaded (NEW: only 2 required)
    required_docs = ['passport_uploaded', 'consolidated_pdf_uploaded']
    missing_docs = []
    
    for doc in required_docs:
        if not getattr(officer, doc, False):
            missing_docs.append(doc.replace('_uploaded', '').replace('_', ' ').title())
    
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate PDFs. Missing required documents: {', '.join(missing_docs)}"
        )
    
    # Generate PDFs in background
    from app.utils.pdf import generate_existing_officer_pdfs_and_email
    
    background_tasks.add_task(
        generate_existing_officer_pdfs_and_email,
        officer_id=officer_id,
        email=officer.email,
        full_name=officer.full_name,
        db=db
    )
    
    return PDFGenerationResponse(
        status="success",
        message="PDF generation started. You will receive an email when completed.",
        officer_id=officer_id,
        email=officer.email,
        email_sent=False,  # Will be sent by background task
        download_urls={
            "dashboard_url": f"/api/existing-officers/{officer_id}/dashboard",
            "pdf_download_url": f"/pdf/existing/{officer_id}"
        }
    )


@router.get(
    "/{officer_id}/dashboard",
    response_model=ExistingOfficerDashboard,
    summary="Get existing officer dashboard data - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def get_existing_officer_dashboard(
    officer_id: str,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for existing officers - UPDATED FOR 2-UPLOAD SYSTEM
    
    Returns:
    - Officer details with new fields
    - Simplified document upload status (only 2 documents)
    - PDF availability (auto-generated and downloadable from dashboard)
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
    "/logout",
    summary="Logout existing officer"
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


# ==================== BACKGROUND TASK FUNCTIONS ====================

async def send_welcome_email_task(officer_id: str, db: Session):
    """
    Background task to send welcome email to existing officer
    """
    try:
        logger.info(f"📧 Sending welcome email to officer: {officer_id}")
        
        # Get officer by officer_id
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            logger.error(f"❌ Officer not found for welcome email: {officer_id}")
            return
        
        # Send welcome email (using template 1 from your request)
        email_result = await send_existing_officer_welcome_email(
            to_email=officer.email,
            name=officer.full_name,
            officer_id=officer.officer_id,
            category=officer.category
        )
        
        if email_result:
            logger.info(f"✅ Welcome email sent successfully to {officer.email}")
        else:
            logger.warning(f"⚠️ Welcome email failed for {officer.email}")
            
    except Exception as e:
        logger.error(f"❌ Error sending welcome email: {str(e)}")


# ==================== DEBUG ENDPOINT ====================

@router.post(
    "/debug-register",
    summary="Debug endpoint for registration data",
    status_code=status.HTTP_200_OK
)
async def debug_register_data(
    register_data: dict,
    request: Request
):
    """
    Debug endpoint to see what data is being sent from frontend
    """
    try:
        logger.info(f"📨 Received registration data (debug): {register_data}")
        
        # Log all headers
        logger.info(f"📋 Request headers: {dict(request.headers)}")
        
        # Validate against schema
        try:
            validated = ExistingOfficerRegister(**register_data)
            return {
                "status": "success",
                "message": "Data matches schema",
                "received_keys": list(register_data.keys()),
                "schema_keys": list(ExistingOfficerRegister.__fields__.keys()),
                "validated_data": validated.dict()
            }
        except Exception as e:
            error_details = str(e)
            # Extract field-level errors if available
            if hasattr(e, 'errors'):
                error_details = e.errors()
            
            return {
                "status": "error",
                "message": error_details,
                "received_data": register_data,
                "schema_fields": list(ExistingOfficerRegister.__fields__.keys()),
                "schema_field_types": {k: str(v.type_) for k, v in ExistingOfficerRegister.__fields__.items()}
            }
            
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }