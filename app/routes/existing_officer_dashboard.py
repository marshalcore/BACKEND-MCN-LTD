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


@router.get(
    "/documents",
    summary="Get document upload status - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def get_document_status(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get the status of uploaded documents - NEW 2-UPLOAD SYSTEM ONLY.
    
    ✅ UPDATED: Only shows 2 required documents:
    1. Passport Photo
    2. Consolidated PDF (all 10 documents in one)
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
        
        # ✅ UPDATED: Document status for 2-upload system
        document_status = {
            "passport_photo": {
                "uploaded": officer.passport_uploaded,
                "path": officer.passport_path,
                "required": True,
                "uploaded_at": officer.updated_at if officer.passport_path else None,
                "max_size": "2MB",
                "allowed_formats": ["JPG", "PNG"],
                "description": "Passport photograph for identification"
            },
            "consolidated_pdf": {
                "uploaded": officer.consolidated_pdf_uploaded,
                "path": officer.consolidated_pdf_path,
                "required": True,
                "uploaded_at": officer.updated_at if officer.consolidated_pdf_path else None,
                "max_size": "10MB",
                "allowed_formats": ["PDF"],
                "description": "Consolidated PDF containing all 10 required documents",
                "documents_included": [
                    "NIN slip",
                    "All school results",
                    "Birth certificates",
                    "Back and front ID card",
                    "All Gmail forms",
                    "All marshal certificates",
                    "Bio data enrollment/appointment letter",
                    "Promotion letter",
                    "Application form",
                    "Both affidavits of non-membership of cult groups"
                ]
            }
        }
        
        # ✅ UPDATED: Count statistics for 2-upload system
        total_uploaded = sum(1 for doc in document_status.values() if doc["uploaded"])
        required_uploaded = total_uploaded  # All are required in new system
        total_required = len(document_status)  # Only 2 required
        
        # Create download URLs
        base_url = "https://backend-mcn-ltd.onrender.com"
        for doc_name, doc_info in document_status.items():
            if doc_info["path"] and os.path.exists(doc_info["path"]):
                filename = os.path.basename(doc_info["path"])
                document_status[doc_name]["download_url"] = f"{base_url}/download/pdf/{filename}"
        
        return {
            "documents": document_status,
            "statistics": {
                "total_uploaded": total_uploaded,
                "required_uploaded": required_uploaded,
                "total_required": total_required,
                "all_required_uploaded": required_uploaded == total_required,
                "completion_percentage": int((required_uploaded / total_required) * 100) if total_required > 0 else 0,
                "system": "2-upload system (passport + consolidated PDF)"
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching document status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch document status"
        )


@router.get(
    "/pdfs",
    summary="Get PDF document status - UPDATED WITH DOWNLOAD URLs"
)
async def get_pdf_status(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get status of generated PDF documents with direct download URLs.
    
    ✅ UPDATED: Includes public download URLs for direct access
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
        
        pdf_status = {
            "terms_and_conditions": {
                "available": bool(officer.terms_pdf_path),
                "path": officer.terms_pdf_path,
                "generated_at": officer.terms_generated_at,
                "download_url": f"{base_url}/download/pdf/{os.path.basename(officer.terms_pdf_path)}" if officer.terms_pdf_path else None,
                "description": "Official terms and conditions for Marshal Core of Nigeria officers",
                "size": f"{os.path.getsize(officer.terms_pdf_path) / 1024:.1f} KB" if officer.terms_pdf_path and os.path.exists(officer.terms_pdf_path) else "N/A"
            },
            "registration_form": {
                "available": bool(officer.registration_pdf_path),
                "path": officer.registration_pdf_path,
                "generated_at": officer.registration_generated_at,
                "download_url": f"{base_url}/download/pdf/{os.path.basename(officer.registration_pdf_path)}" if officer.registration_pdf_path else None,
                "description": "Your completed officer registration form",
                "size": f"{os.path.getsize(officer.registration_pdf_path) / 1024:.1f} KB" if officer.registration_pdf_path and os.path.exists(officer.registration_pdf_path) else "N/A"
            }
        }
        
        return pdf_status
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching PDF status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch PDF status"
        )


@router.post(
    "/generate-pdfs",
    summary="Generate PDF documents - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def generate_pdfs(
    background_tasks: BackgroundTasks,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Generate Terms & Conditions and Registration Form PDFs.
    
    ✅ UPDATED: Checks new 2-upload system requirements
    PDFs will be sent to officer's email with direct download links.
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Generating PDFs for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # ✅ UPDATED: Check if all required documents are uploaded (2-upload system)
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
        
        # Add background task to generate PDFs
        background_tasks.add_task(
            generate_officer_pdfs_background,
            officer_id=officer_id,
            db=db
        )
        
        return {
            "status": "success",
            "message": "PDF generation started. You will receive an email with download links when completed.",
            "officer_id": officer_id,
            "email": officer.email,
            "documents_uploaded": True,
            "system": "2-upload system"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating PDFs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start PDF generation"
        )


@router.get(
    "/pdfs/download",
    summary="Get direct PDF download URLs"
)
async def get_pdf_download_urls(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get direct download URLs for all officer PDF documents.
    
    ✅ NEW ENDPOINT: Provides clickable download links for frontend
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Getting PDF download URLs for officer: {officer_id}")
        
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        base_url = "https://backend-mcn-ltd.onrender.com"
        response = {
            "officer_id": officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "pdfs": {},
            "documents": {},
            "dashboard_url": "https://marshalcoreofnigeria.ng/existing-officer-dashboard.html"
        }
        
        # Terms PDF
        if officer.terms_pdf_path and os.path.exists(officer.terms_pdf_path):
            terms_filename = os.path.basename(officer.terms_pdf_path)
            response["pdfs"]["terms"] = {
                "url": f"{base_url}/download/pdf/{terms_filename}",
                "filename": terms_filename,
                "generated_at": officer.terms_generated_at.isoformat() if officer.terms_generated_at else None,
                "size_kb": round(os.path.getsize(officer.terms_pdf_path) / 1024, 1),
                "description": "Terms & Conditions PDF"
            }
        
        # Registration PDF
        if officer.registration_pdf_path and os.path.exists(officer.registration_pdf_path):
            reg_filename = os.path.basename(officer.registration_pdf_path)
            response["pdfs"]["registration"] = {
                "url": f"{base_url}/download/pdf/{reg_filename}",
                "filename": reg_filename,
                "generated_at": officer.registration_generated_at.isoformat() if officer.registration_generated_at else None,
                "size_kb": round(os.path.getsize(officer.registration_pdf_path) / 1024, 1),
                "description": "Registration Form PDF"
            }
        
        # Passport Photo
        if officer.passport_path and os.path.exists(officer.passport_path):
            passport_filename = os.path.basename(officer.passport_path)
            response["documents"]["passport"] = {
                "url": f"{base_url}/download/pdf/{passport_filename}",
                "filename": passport_filename,
                "uploaded": officer.passport_uploaded,
                "type": "Passport Photo"
            }
        
        # Consolidated PDF
        if officer.consolidated_pdf_path and os.path.exists(officer.consolidated_pdf_path):
            consolidated_filename = os.path.basename(officer.consolidated_pdf_path)
            response["documents"]["consolidated_pdf"] = {
                "url": f"{base_url}/download/pdf/{consolidated_filename}",
                "filename": consolidated_filename,
                "uploaded": officer.consolidated_pdf_uploaded,
                "type": "Consolidated Documents PDF"
            }
        
        return response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting PDF download URLs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get PDF download URLs"
        )


@router.post(
    "/logout",
    summary="Logout existing officer"
)
async def logout_officer(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Logout the current officer and update last login timestamp.
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


@router.get(
    "/stats",
    summary="Get dashboard statistics - UPDATED FOR 2-UPLOAD SYSTEM"
)
async def get_dashboard_stats(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics and activity metrics.
    
    ✅ UPDATED: Statistics for 2-upload system
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching stats for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Calculate days since registration
        days_registered = (datetime.utcnow() - officer.created_at).days
        
        # ✅ UPDATED: Document completion for 2-upload system
        documents_uploaded = sum([
            1 if officer.passport_uploaded else 0,
            1 if officer.consolidated_pdf_uploaded else 0
        ])
        
        stats = {
            "days_registered": days_registered,
            "dashboard_access_count": officer.dashboard_access_count or 0,
            "last_dashboard_access": officer.last_dashboard_access,
            "last_login": officer.last_login,
            "verification_status": officer.status,
            "is_active": officer.is_active,
            "is_verified": officer.is_verified,
            "document_completion": {
                "passport_uploaded": officer.passport_uploaded,
                "consolidated_pdf_uploaded": officer.consolidated_pdf_uploaded,
                "total_uploaded": documents_uploaded,
                "total_required": 2,
                "completion_percentage": int((documents_uploaded / 2) * 100) if 2 > 0 else 0,
                "all_documents_uploaded": officer.passport_uploaded and officer.consolidated_pdf_uploaded,
                "system": "2-upload system"
            },
            "pdf_status": {
                "has_terms": bool(officer.terms_pdf_path),
                "has_registration": bool(officer.registration_pdf_path),
                "both_generated": bool(officer.terms_pdf_path and officer.registration_pdf_path),
                "terms_generated_at": officer.terms_generated_at,
                "registration_generated_at": officer.registration_generated_at
            }
        }
        
        return stats
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard statistics"
        )


# Background task function - UPDATED FOR 2-UPLOAD SYSTEM
async def generate_officer_pdfs_background(officer_id: str, db: Session):
    """
    Background task to generate PDFs for an officer.
    
    ✅ UPDATED: Creates public download URLs and sends email with links
    """
    try:
        logger.info(f"Background task: Generating PDFs for officer: {officer_id}")
        
        officer = ExistingOfficerService.get_officer_by_id(db, officer_id)
        if not officer:
            logger.error(f"Officer not found: {officer_id}")
            return
        
        # Generate PDFs using PDFService
        pdf_service = PDFService(db)
        
        try:
            # Generate Terms & Conditions PDF
            terms_pdf_path = pdf_service.generate_terms_conditions(
                str(officer.id),
                "existing_officer"
            )
            
            # Generate Existing Officer Registration Form PDF
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
            
            # ✅ Create public download URLs
            base_url = "https://backend-mcn-ltd.onrender.com"
            terms_filename = os.path.basename(terms_pdf_path)
            registration_filename = os.path.basename(registration_pdf_path)
            
            terms_pdf_url = f"{base_url}/download/pdf/{terms_filename}"
            registration_pdf_url = f"{base_url}/download/pdf/{registration_filename}"
            
            logger.info(f"✅ Generated download URLs:")
            logger.info(f"   Terms PDF: {terms_pdf_url}")
            logger.info(f"   Registration PDF: {registration_pdf_url}")
            
            # ✅ Send email with download links
            success = await send_existing_officer_pdfs_email(
                to_email=officer.email,
                name=officer.full_name,
                officer_id=officer.officer_id,
                terms_pdf_path=terms_pdf_path,
                registration_pdf_path=registration_pdf_path
            )
            
            if success:
                logger.info(f"✅ PDFs generated and email with download links sent to {officer.email}")
            else:
                logger.error(f"❌ Failed to send PDFs email to {officer.email}")
                
        except Exception as e:
            logger.error(f"❌ Error in PDF generation for {officer_id}: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ Error in background PDF generation task: {str(e)}")