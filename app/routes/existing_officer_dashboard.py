# app/routes/existing_officer_dashboard.py
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import os

from app.database import get_db
from app.auth.dependencies import get_current_existing_officer_dict
from app.schemas.existing_officer import ExistingOfficerDashboard
from app.services.existing_officer_service import ExistingOfficerService
from app.services.pdf_service import PDFService
from app.services.email_service import send_existing_officer_pdfs_email
from app.models.existing_officer import ExistingOfficer
from app.utils.pdf import PDFGenerator
from app.utils.upload import normalize_officer_id

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/existing-officers/dashboard",
    tags=["Existing Officer Dashboard"]
)


@router.get(
    "/",
    response_model=ExistingOfficerDashboard,
    summary="Get existing officer dashboard data - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def get_dashboard_data(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard data for the logged-in existing officer.
    
    ✅ UPDATED FOR 2-UPLOAD SYSTEM:
    - Only 2 document uploads required (passport + consolidated PDF)
    - Includes PDF download URLs for direct access
    - Updated document status for new system
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching dashboard data for officer: {officer_id}")
        
        # Get dashboard data from service
        dashboard_data = ExistingOfficerService.get_dashboard_data(db, officer_id)
        
        # ✅ ADD PDF DOWNLOAD URLs
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if officer:
            base_url = "https://backend-mcn-ltd.onrender.com"
            
            # Add PDF download URLs
            if officer.terms_pdf_path and os.path.exists(officer.terms_pdf_path):
                terms_filename = os.path.basename(officer.terms_pdf_path)
                dashboard_data["pdf_download_urls"] = {
                    "terms": f"{base_url}/download/pdf/{terms_filename}"
                }
            
            if officer.registration_pdf_path and os.path.exists(officer.registration_pdf_path):
                reg_filename = os.path.basename(officer.registration_pdf_path)
                dashboard_data["pdf_download_urls"] = {
                    **dashboard_data.get("pdf_download_urls", {}),
                    "registration": f"{base_url}/download/pdf/{reg_filename}"
                }
            
            # Add passport URL
            if officer.passport_path:
                passport_filename = os.path.basename(officer.passport_path)
                normalized_officer_id = normalize_officer_id(officer_id)
                passport_url = f"{base_url}/static/uploads/existing_officers/{normalized_officer_id}/passport/{passport_filename}"
                dashboard_data["passport_url"] = passport_url
        
        logger.info(f"✅ Dashboard data retrieved for officer: {officer_id}")
        return dashboard_data
        
    except HTTPException as he:
        logger.warning(f"HTTP Exception in dashboard: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard data"
        )


@router.get(
    "/profile",
    summary="Get detailed officer profile - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def get_officer_profile(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get detailed profile information for the existing officer.
    
    ✅ UPDATED: Includes new 2-upload document status
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching profile for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Return profile data with new fields
        profile_data = {
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "rank": officer.rank,
            "position": officer.position,
            "date_of_birth": officer.date_of_birth,
            "gender": officer.gender,
            "marital_status": officer.marital_status,
            "nationality": officer.nationality,
            "date_of_enlistment": officer.date_of_enlistment,
            "date_of_promotion": officer.date_of_promotion,
            "category": officer.category,
            "nin_number": officer.nin_number,
            "residential_address": officer.residential_address,
            "state_of_residence": officer.state_of_residence,
            "local_government_residence": officer.local_government_residence,
            "state_of_origin": officer.state_of_origin,
            "local_government_origin": officer.local_government_origin,
            "years_of_service": officer.years_of_service,
            "service_number": officer.service_number,
            "religion": officer.religion,
            "additional_skills": officer.additional_skills,
            "bank_name": officer.bank_name,
            "account_number": officer.account_number,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "created_at": officer.created_at,
            "last_login": officer.last_login,
            # ✅ NEW: 2-upload document status
            "passport_uploaded": officer.passport_uploaded,
            "consolidated_pdf_uploaded": officer.consolidated_pdf_uploaded,
            "all_documents_uploaded": officer.passport_uploaded and officer.consolidated_pdf_uploaded,
        }
        
        return profile_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching officer profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch officer profile"
        )


@router.get(
    "/documents",
    summary="Get officer document status - NEW 2-UPLOAD SYSTEM"
)
async def get_officer_documents(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get document upload status for the existing officer.
    
    ✅ UPDATED: Only 2 documents required in new system:
    1. Passport photo
    2. Consolidated PDF (all 10 documents combined)
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching document status for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Return document status for 2-upload system
        document_data = {
            "officer_id": officer.officer_id,
            "passport_uploaded": officer.passport_uploaded,
            "consolidated_pdf_uploaded": officer.consolidated_pdf_uploaded,
            "all_documents_uploaded": officer.passport_uploaded and officer.consolidated_pdf_uploaded,
            "required_documents": [
                {
                    "document_type": "passport",
                    "display_name": "Passport Photo",
                    "uploaded": officer.passport_uploaded,
                    "required": True,
                    "max_size_mb": 2,
                    "allowed_formats": ["jpg", "jpeg", "png"]
                },
                {
                    "document_type": "consolidated_pdf",
                    "display_name": "Consolidated PDF (All Documents)",
                    "uploaded": officer.consolidated_pdf_uploaded,
                    "required": True,
                    "max_size_mb": 10,
                    "allowed_formats": ["pdf"]
                }
            ],
            "upload_progress": f"{int(officer.passport_uploaded) + int(officer.consolidated_pdf_uploaded)}/2"
        }
        
        return document_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching officer documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch officer documents"
        )


@router.get(
    "/pdfs",
    summary="Get officer PDF documents status"
)
async def get_officer_pdfs(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get PDF documents status for the existing officer.
    
    Returns:
    - Terms & Conditions PDF status
    - Registration Form PDF status
    - Download URLs for both
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching PDF status for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        base_url = "https://backend-mcn-ltd.onrender.com"
        
        # Check if PDFs exist and create download URLs
        pdf_data = {
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "pdf_paths": {},
            "pdf_status": {
                "terms_and_conditions": {
                    "generated": bool(officer.terms_pdf_path),
                    "file_path": officer.terms_pdf_path,
                    "last_generated": officer.terms_generated_at
                },
                "registration_form": {
                    "generated": bool(officer.registration_pdf_path),
                    "file_path": officer.registration_pdf_path,
                    "last_generated": officer.registration_generated_at
                }
            }
        }
        
        # Add download URLs if PDFs exist
        if officer.terms_pdf_path:
            terms_filename = os.path.basename(officer.terms_pdf_path)
            pdf_data["pdf_paths"]["terms"] = f"{base_url}/download/pdf/{terms_filename}"
            pdf_data["pdf_download_urls"] = {
                "terms": f"{base_url}/download/pdf/{terms_filename}"
            }
        
        if officer.registration_pdf_path:
            reg_filename = os.path.basename(officer.registration_pdf_path)
            pdf_data["pdf_paths"]["registration"] = f"{base_url}/download/pdf/{reg_filename}"
            pdf_data["pdf_download_urls"] = {
                **pdf_data.get("pdf_download_urls", {}),
                "registration": f"{base_url}/download/pdf/{reg_filename}"
            }
        
        return pdf_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching officer PDFs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch officer PDFs"
        )


@router.post(
    "/generate-pdfs",
    summary="Generate PDFs from dashboard",
    response_model=dict
)
async def generate_pdfs_from_dashboard(
    background_tasks: BackgroundTasks,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    ✅ FIXED: Generate PDFs for the logged-in officer from dashboard.
    This endpoint has no URL parameter, only uses JWT token for authorization.
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"📄 Generating PDFs from dashboard for officer: {officer_id}")
        
        if not officer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        # Get officer using officer_id from token
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # ✅ IMPORTANT: The JWT token already validates this is the correct officer
        # No additional authorization check needed
        
        # Check if all required documents are uploaded
        if not officer.passport_uploaded:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload passport photo before generating PDFs"
            )
        
        if not officer.consolidated_pdf_uploaded:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload consolidated PDF before generating PDFs"
            )
        
        # Import and run PDF generation
        from app.utils.pdf import generate_existing_officer_pdfs_and_email
        
        # Generate PDFs in background
        background_tasks.add_task(
            generate_existing_officer_pdfs_and_email,
            officer_id=officer_id,
            email=officer.email,
            full_name=officer.full_name,
            db=db
        )
        
        return {
            "status": "success",
            "message": "PDF generation started. You will receive an email with the documents.",
            "officer_id": officer_id,
            "email": officer.email,
            "generation_started": True
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating PDFs from dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDFs: {str(e)}"
        )


# ==================== ✅ ADD PASSPORT ENDPOINT HERE ====================

@router.get(
    "/passport",
    summary="Get passport photo URL for logged-in officer",
    response_model=dict
)
async def get_dashboard_passport_photo(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    ✅ NEW ENDPOINT: Get passport photo URL for the logged-in officer
    This endpoint is called by the dashboard frontend
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching passport photo for dashboard: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Check if passport exists
        if not officer.passport_path:
            return {
                "passport_url": None,
                "has_passport": False,
                "message": "Passport photo not uploaded",
                "officer_id": officer_id
            }
        
        # Get normalized officer ID for URL
        normalized_officer_id = normalize_officer_id(officer_id)
        
        # Get the filename from the path
        passport_filename = os.path.basename(officer.passport_path)
        
        # ✅ Construct URL with normalized officer ID
        base_url = "https://backend-mcn-ltd.onrender.com"
        passport_url = f"{base_url}/static/uploads/existing_officers/{normalized_officer_id}/passport/{passport_filename}"
        
        # Also check if file exists physically
        file_exists = False
        file_size = 0
        
        # Check multiple possible locations
        possible_paths = [
            officer.passport_path,  # Original path from database
            f"static/uploads/existing_officers/{normalized_officer_id}/passport/{passport_filename}",
            f"static/uploads/existing_officers/{officer_id}/passport/{passport_filename}".replace('/', '-'),  # Original with hyphens
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                file_exists = True
                file_size = os.path.getsize(path)
                break
        
        return {
            "passport_url": passport_url,
            "relative_path": officer.passport_path,
            "filename": passport_filename,
            "has_passport": file_exists,
            "upload_date": officer.updated_at,
            "file_size": file_size,
            "officer_id": officer_id,
            "normalized_officer_id": normalized_officer_id,
            "passport_uploaded": officer.passport_uploaded
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting dashboard passport photo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get passport photo"
        )
    