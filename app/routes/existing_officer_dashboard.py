# app/routes/existing_officer_dashboard.py
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.database import get_db
from app.auth.dependencies import get_current_existing_officer_dict
from app.schemas.existing_officer import ExistingOfficerDashboard
from app.services.existing_officer_service import ExistingOfficerService
from app.services.pdf_service import PDFService
from app.services.email_service import send_existing_officer_pdfs_email

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/existing-officers/dashboard",
    tags=["Existing Officer Dashboard"]
)


@router.get(
    "/",
    response_model=ExistingOfficerDashboard,
    summary="Get existing officer dashboard data"
)
async def get_dashboard_data(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard data for the logged-in existing officer.
    
    Includes:
    - Officer profile information
    - Document upload status
    - PDF availability
    - Verification status
    - Dashboard statistics
    """
    try:
        officer_id = current_officer.get("officer_id")
        logger.info(f"Fetching dashboard data for officer: {officer_id}")
        
        # Get dashboard data from service
        dashboard_data = ExistingOfficerService.get_dashboard_data(db, officer_id)
        
        logger.info(f"Dashboard data retrieved for officer: {officer_id}")
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
    summary="Get detailed officer profile"
)
async def get_officer_profile(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get detailed profile information for the existing officer.
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
        
        # Return profile data
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
    summary="Get document upload status"
)
async def get_document_status(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get the status of uploaded documents.
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
        
        # Document status
        document_status = {
            "passport_photo": {
                "uploaded": bool(officer.passport_photo),
                "path": officer.passport_photo,
                "required": True,
                "uploaded_at": officer.updated_at if officer.passport_photo else None
            },
            "nin_slip": {
                "uploaded": bool(officer.nin_slip),
                "path": officer.nin_slip,
                "required": True,
                "uploaded_at": officer.updated_at if officer.nin_slip else None
            },
            "ssce_certificate": {
                "uploaded": bool(officer.ssce_certificate),
                "path": officer.ssce_certificate,
                "required": True,
                "uploaded_at": officer.updated_at if officer.ssce_certificate else None
            },
            "birth_certificate": {
                "uploaded": bool(officer.birth_certificate),
                "path": officer.birth_certificate,
                "required": False,
                "uploaded_at": officer.updated_at if officer.birth_certificate else None
            },
            "appointment_letter": {
                "uploaded": bool(officer.letter_of_first_appointment),
                "path": officer.letter_of_first_appointment,
                "required": False,
                "uploaded_at": officer.updated_at if officer.letter_of_first_appointment else None
            },
            "promotion_letters": {
                "uploaded": bool(officer.promotion_letters),
                "path": officer.promotion_letters,
                "required": False,
                "uploaded_at": officer.updated_at if officer.promotion_letters else None
            }
        }
        
        # Count statistics
        total_uploaded = sum(1 for doc in document_status.values() if doc["uploaded"])
        required_uploaded = sum(1 for doc in document_status.values() 
                              if doc["required"] and doc["uploaded"])
        total_required = sum(1 for doc in document_status.values() if doc["required"])
        
        return {
            "documents": document_status,
            "statistics": {
                "total_uploaded": total_uploaded,
                "required_uploaded": required_uploaded,
                "total_required": total_required,
                "all_required_uploaded": required_uploaded == total_required,
                "completion_percentage": int((required_uploaded / total_required) * 100) if total_required > 0 else 0
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
    summary="Get PDF document status"
)
async def get_pdf_status(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get status of generated PDF documents.
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
        
        pdf_status = {
            "terms_and_conditions": {
                "available": bool(officer.terms_pdf_path),
                "path": officer.terms_pdf_path,
                "generated_at": officer.terms_generated_at,
                "download_url": f"/download/pdf/{officer.terms_pdf_path.split('/')[-1]}" if officer.terms_pdf_path else None
            },
            "registration_form": {
                "available": bool(officer.registration_pdf_path),
                "path": officer.registration_pdf_path,
                "generated_at": officer.registration_generated_at,
                "download_url": f"/download/pdf/{officer.registration_pdf_path.split('/')[-1]}" if officer.registration_pdf_path else None
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
    summary="Generate PDF documents"
)
async def generate_pdfs(
    background_tasks: BackgroundTasks,
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Generate Terms & Conditions and Registration Form PDFs.
    PDFs will be sent to officer's email.
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
        
        # Add background task to generate PDFs
        background_tasks.add_task(
            generate_officer_pdfs_background,
            officer_id=officer_id,
            db=db
        )
        
        return {
            "status": "success",
            "message": "PDF generation started. You will receive an email when completed.",
            "officer_id": officer_id,
            "email": officer.email
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating PDFs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start PDF generation"
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
    summary="Get dashboard statistics"
)
async def get_dashboard_stats(
    current_officer: dict = Depends(get_current_existing_officer_dict),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics and activity metrics.
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
        
        stats = {
            "days_registered": days_registered,
            "dashboard_access_count": officer.dashboard_access_count or 0,
            "last_dashboard_access": officer.last_dashboard_access,
            "last_login": officer.last_login,
            "verification_status": officer.status,
            "is_active": officer.is_active,
            "is_verified": officer.is_verified,
            "document_completion": {
                "passport": bool(officer.passport_photo),
                "nin": bool(officer.nin_slip),
                "ssce": bool(officer.ssce_certificate),
                "total_uploaded": sum([
                    bool(officer.passport_photo),
                    bool(officer.nin_slip),
                    bool(officer.ssce_certificate),
                    bool(officer.birth_certificate),
                    bool(officer.letter_of_first_appointment),
                    bool(officer.promotion_letters)
                ])
            },
            "pdf_status": {
                "has_terms": bool(officer.terms_pdf_path),
                "has_registration": bool(officer.registration_pdf_path),
                "both_generated": bool(officer.terms_pdf_path and officer.registration_pdf_path)
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


# Background task function
async def generate_officer_pdfs_background(officer_id: str, db: Session):
    """
    Background task to generate PDFs for an officer.
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
            logger.error(f"Error in PDF generation for {officer_id}: {str(e)}")
            # Send error notification email (implement if needed)
            
    except Exception as e:
        logger.error(f"Error in background PDF generation task: {str(e)}")