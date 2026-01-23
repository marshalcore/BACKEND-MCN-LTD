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
from app.models.existing_officer import ExistingOfficer  # ✅ ADD IMPORT

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