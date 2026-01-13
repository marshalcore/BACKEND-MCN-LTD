# app/routes/pdf_download.py
from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import logging
from typing import Optional, Dict, Any

from app.database import get_db
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.services.pdf_service import PDFService
from app.schemas.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pdf",
    tags=["PDF Documents"]
)

# Create a simple authentication dependency for development
async def get_current_user() -> User:
    """
    Simplified authentication for development
    In production, use proper JWT authentication
    """
    return User(
        id="development_user",
        role="user",
        authenticated=True
    )

async def get_current_admin() -> User:
    """
    Simplified admin authentication for development
    In production, use proper JWT authentication with role check
    """
    return User(
        id="development_admin",
        role="admin",
        authenticated=True,
        is_admin=True
    )

@router.get("/terms/{user_id}")
async def download_terms_conditions(
    user_id: str,
    user_type: str = "applicant",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download Terms & Conditions PDF for a user
    
    user_type: applicant, officer, or existing_officer
    """
    try:
        logger.info(f"Downloading Terms & Conditions for user: {user_id}, type: {user_type}")
        
        # Get PDF path from database
        pdf_path = None
        
        if user_type == "applicant":
            applicant = db.query(Applicant).filter(Applicant.id == user_id).first()
            if applicant:
                pdf_path = applicant.terms_pdf_path
        elif user_type == "officer":
            officer = db.query(Officer).filter(Officer.id == user_id).first()
            if officer:
                pdf_path = officer.terms_pdf_path
        elif user_type == "existing_officer":
            officer = db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
            if officer:
                pdf_path = officer.terms_pdf_path
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        # Check if PDF exists
        if not pdf_path or not Path(pdf_path).exists():
            # Generate on-the-fly if not exists
            logger.info(f"PDF not found, generating new Terms & Conditions for {user_id}")
            pdf_service = PDFService(db)
            pdf_path = pdf_service.generate_terms_conditions(user_id, user_type)
        
        # Serve the PDF file
        if Path(pdf_path).exists():
            return FileResponse(
                path=pdf_path,
                filename=f"Terms_Conditions_{user_id}.pdf",
                media_type="application/pdf"
            )
        else:
            raise HTTPException(status_code=404, detail="PDF file not found after generation")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download Terms & Conditions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@router.get("/application/{user_id}")
async def download_application_form(
    user_id: str,
    user_type: str = "applicant",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download Application Form PDF for a user
    
    user_type: applicant, officer, or existing_officer
    """
    try:
        logger.info(f"Downloading Application Form for user: {user_id}, type: {user_type}")
        
        # Get PDF path from database
        pdf_path = None
        
        if user_type == "applicant":
            applicant = db.query(Applicant).filter(Applicant.id == user_id).first()
            if applicant:
                pdf_path = applicant.application_pdf_path
        elif user_type == "officer":
            officer = db.query(Officer).filter(Officer.id == user_id).first()
            if officer:
                pdf_path = officer.application_pdf_path
        elif user_type == "existing_officer":
            officer = db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
            if officer:
                pdf_path = officer.application_pdf_path
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        # Check if PDF exists
        if not pdf_path or not Path(pdf_path).exists():
            # Generate on-the-fly if not exists
            logger.info(f"PDF not found, generating new Application Form for {user_id}")
            pdf_service = PDFService(db)
            pdf_path = pdf_service.generate_application_form(user_id, user_type)
        
        # Serve the PDF file
        if Path(pdf_path).exists():
            return FileResponse(
                path=pdf_path,
                filename=f"Application_Form_{user_id}.pdf",
                media_type="application/pdf"
            )
        else:
            raise HTTPException(status_code=404, detail="PDF file not found after generation")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download Application Form: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@router.get("/regenerate/{user_id}")
async def regenerate_pdfs(
    user_id: str,
    user_type: str = "applicant",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Regenerate PDFs for a user (Admin only)
    
    This endpoint forces regeneration of both PDFs and sends them via email
    """
    try:
        # Get user email based on type
        email = None
        name = None
        
        if user_type == "applicant":
            applicant = db.query(Applicant).filter(Applicant.id == user_id).first()
            if applicant:
                email = applicant.email
                name = applicant.full_name
        elif user_type == "officer":
            officer = db.query(Officer).filter(Officer.id == user_id).first()
            if officer:
                email = officer.email
                name = officer.full_name or f"Officer {officer.unique_id}"
        elif user_type == "existing_officer":
            officer = db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
            if officer:
                email = officer.email
                name = officer.full_name
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        if not email:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Regenerate PDFs in background
        if background_tasks:
            # Import here to avoid circular imports
            from app.routes.form_submission import generate_and_send_pdfs
            
            background_tasks.add_task(
                generate_and_send_pdfs,
                email=email,
                user_type=user_type,
                db=db
            )
            
            return {
                "message": f"PDF regeneration started for {name}. Documents will be sent to {email}.",
                "status": "in_progress",
                "user_email": email
            }
        else:
            # Synchronous regeneration
            from app.routes.form_submission import generate_and_send_pdfs
            await generate_and_send_pdfs(email, user_type, db)
            
            return {
                "message": f"PDFs regenerated and sent to {email}",
                "status": "completed",
                "user_email": email
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate PDFs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@router.get("/status/{user_id}")
async def get_pdf_status(
    user_id: str,
    user_type: str = "applicant",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get PDF generation status for a user
    """
    try:
        pdf_service = PDFService(db)
        pdf_status = pdf_service.get_existing_pdfs(user_id, user_type)
        
        return {
            "user_id": user_id,
            "user_type": user_type,
            "pdfs": {
                "terms_and_conditions": {
                    "path": pdf_status["terms_pdf_path"],
                    "generated_at": pdf_status["terms_generated_at"],
                    "exists": pdf_status["terms_pdf_path"] and Path(pdf_status["terms_pdf_path"]).exists() if pdf_status["terms_pdf_path"] else False
                },
                "application_form": {
                    "path": pdf_status["application_pdf_path"],
                    "generated_at": pdf_status["application_generated_at"],
                    "exists": pdf_status["application_pdf_path"] and Path(pdf_status["application_pdf_path"]).exists() if pdf_status["application_pdf_path"] else False
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get PDF status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@router.get("/all/{user_id}")
async def download_all_pdfs(
    user_id: str,
    user_type: str = "applicant",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download both PDFs as a zip file
    """
    try:
        import zipfile
        import io
        from pathlib import Path
        
        # Get PDF paths
        pdf_service = PDFService(db)
        pdf_status = pdf_service.get_existing_pdfs(user_id, user_type)
        
        # Generate missing PDFs
        terms_path = pdf_status["terms_pdf_path"]
        app_path = pdf_status["application_pdf_path"]
        
        if not terms_path or not Path(terms_path).exists():
            terms_path = pdf_service.generate_terms_conditions(user_id, user_type)
        
        if not app_path or not Path(app_path).exists():
            app_path = pdf_service.generate_application_form(user_id, user_type)
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add Terms & Conditions
            if terms_path and Path(terms_path).exists():
                zip_file.write(terms_path, "Terms_and_Conditions.pdf")
            # Add Application Form
            if app_path and Path(app_path).exists():
                zip_file.write(app_path, "Application_Form.pdf")
        
        zip_buffer.seek(0)
        
        # Return zip file
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=MarshalCore_Documents_{user_id}.zip"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create PDF zip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")

@router.get("/public/terms/{filename}")
async def download_public_terms(
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to download Terms & Conditions PDF by filename
    Useful for email links
    """
    try:
        # Extract user_id from filename (filename format: user_id_terms_timestamp_uuid.pdf)
        parts = filename.split('_')
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid filename format")
        
        # Look for PDF in terms directory
        pdf_path = f"static/pdfs/terms/{filename}"
        
        if not Path(pdf_path).exists():
            # Try with .pdf extension if not provided
            if not filename.endswith('.pdf'):
                pdf_path = f"static/pdfs/terms/{filename}.pdf"
            
            if not Path(pdf_path).exists():
                raise HTTPException(status_code=404, detail="PDF not found")
        
        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download public PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@router.get("/public/application/{filename}")
async def download_public_application(
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to download Application Form PDF by filename
    Useful for email links
    """
    try:
        # Look for PDF in applications directory
        pdf_path = f"static/pdfs/applications/{filename}"
        
        if not Path(pdf_path).exists():
            # Try with .pdf extension if not provided
            if not filename.endswith('.pdf'):
                pdf_path = f"static/pdfs/applications/{filename}.pdf"
            
            if not Path(pdf_path).exists():
                raise HTTPException(status_code=404, detail="PDF not found")
        
        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download public PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")