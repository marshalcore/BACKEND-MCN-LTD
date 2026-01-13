# app/routes/form_submission.py
from fastapi import APIRouter, Depends, HTTPException, Form, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.services.email_service import send_guarantor_confirmation_email, send_pdfs_email
from app.services.pdf_service import PDFService
from pydantic import EmailStr
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/form",
    tags=["Form Submission"]
)

async def generate_and_send_pdfs(
    email: str,
    user_type: str = "applicant",
    db: Session = None
):
    """
    Background task to generate PDFs and send email
    """
    try:
        logger.info(f"Generating PDFs for {user_type}: {email}")
        
        # Get user based on type
        if user_type == "applicant":
            user = db.query(Applicant).filter(Applicant.email == email).first()
            if not user:
                logger.error(f"Applicant not found: {email}")
                return
            user_id = str(user.id)
            name = user.full_name
            
        elif user_type == "officer":
            user = db.query(Officer).filter(Officer.email == email).first()
            if not user:
                logger.error(f"Officer not found: {email}")
                return
            user_id = str(user.id)
            name = user.full_name or f"Officer {user.unique_id}"
            
        elif user_type == "existing_officer":
            user = db.query(ExistingOfficer).filter(ExistingOfficer.email == email).first()
            if not user:
                logger.error(f"Existing officer not found: {email}")
                return
            user_id = str(user.id)
            name = user.full_name
            
        else:
            logger.error(f"Invalid user type: {user_type}")
            return
        
        # Generate PDFs
        pdf_service = PDFService(db)
        pdf_paths = pdf_service.generate_both_pdfs(user_id, user_type)
        
        # Send email with PDF attachments
        admin_email = "admin@marshalcoreng.com"  # Could be from settings
        success = await send_pdfs_email(
            to_email=email,
            name=name,
            terms_pdf_path=pdf_paths["terms_pdf_path"],
            application_pdf_path=pdf_paths["application_pdf_path"],
            cc_email=admin_email
        )
        
        if success:
            logger.info(f"PDFs generated and emailed successfully to {email}")
        else:
            logger.error(f"Failed to send PDFs email to {email}")
            
    except Exception as e:
        logger.error(f"Error in generate_and_send_pdfs for {email}: {str(e)}")

@router.post("/submit")
async def submit_application(
    email: EmailStr = Form(...),
    full_name: str = Form(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    # Find applicant
    applicant = db.query(Applicant).filter(Applicant.email == email).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    if not applicant.is_verified:
        raise HTTPException(status_code=403, detail="Application not verified")

    name = full_name or applicant.full_name

    # Send guarantor confirmation email
    await send_guarantor_confirmation_email(applicant.email, name)
    
    # Add background task to generate and send PDFs
    if background_tasks:
        background_tasks.add_task(
            generate_and_send_pdfs,
            email=email,
            user_type="applicant",
            db=db
        )
        
        return {
            "message": "Application submitted successfully. Guarantor form sent to email. PDF documents will be generated and sent shortly.",
            "guarantor_form_url": "/static/guarantor-form.pdf",
            "pdfs_generation": "in_progress"
        }
    else:
        # Synchronous fallback
        await generate_and_send_pdfs(email, "applicant", db)
        
        return {
            "message": "Application submitted successfully. Guarantor form and application documents sent to email.",
            "guarantor_form_url": "/static/guarantor-form.pdf",
            "pdfs_generation": "completed"
        }

@router.post("/officer/submit")
async def submit_officer_application(
    email: EmailStr = Form(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Endpoint for officer form submission (after payment/verification)
    """
    officer = db.query(Officer).filter(Officer.email == email).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")

    name = officer.full_name or f"Officer {officer.unique_id}"
    
    # Add background task to generate and send PDFs
    if background_tasks:
        background_tasks.add_task(
            generate_and_send_pdfs,
            email=email,
            user_type="officer",
            db=db
        )
        
        return {
            "message": "Officer application submitted successfully. PDF documents will be generated and sent shortly.",
            "pdfs_generation": "in_progress"
        }
    else:
        await generate_and_send_pdfs(email, "officer", db)
        
        return {
            "message": "Officer application submitted successfully. PDF documents sent to email.",
            "pdfs_generation": "completed"
        }

@router.post("/existing-officer/submit")
async def submit_existing_officer_application(
    email: EmailStr = Form(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Endpoint for existing officer form submission (after verification)
    """
    officer = db.query(ExistingOfficer).filter(ExistingOfficer.email == email).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Existing officer not found")

    if not officer.is_verified:
        raise HTTPException(status_code=403, detail="Officer not verified")

    name = officer.full_name
    
    # Add background task to generate and send PDFs
    if background_tasks:
        background_tasks.add_task(
            generate_and_send_pdfs,
            email=email,
            user_type="existing_officer",
            db=db
        )
        
        return {
            "message": "Existing officer application submitted successfully. PDF documents will be generated and sent shortly.",
            "pdfs_generation": "in_progress"
        }
    else:
        await generate_and_send_pdfs(email, "existing_officer", db)
        
        return {
            "message": "Existing officer application submitted successfully. PDF documents sent to email.",
            "pdfs_generation": "completed"
        }