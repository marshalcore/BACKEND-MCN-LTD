# app/routes/pdf_download.py - COMPLETE UPDATED VERSION
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import logging
from typing import Optional, Dict, Any
import os
from datetime import datetime

from app.database import get_db
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.services.pdf_service import PDFService  # ✅ CHANGED: Import unified PDFService
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
            # ✅ CHANGED: Use unified PDFService
            pdf_service = PDFService(db)
            
            if user_type == "applicant":
                applicant = db.query(Applicant).filter(Applicant.id == user_id).first()
                if applicant:
                    # Generate PDF using unified service
                    pdf_path = pdf_service.generate_terms_conditions(
                        user_id=user_id,
                        user_type="applicant",
                        tier=applicant.application_tier
                    )
                    
                    # Update database
                    applicant.terms_pdf_path = pdf_path
                    applicant.terms_generated_at = datetime.now()
                    db.commit()
            else:
                raise HTTPException(status_code=404, detail="PDF not found and cannot regenerate for this user type")
        
        # Serve the PDF file
        if pdf_path and Path(pdf_path).exists():
            return FileResponse(
                path=pdf_path,
                filename=f"Terms_Conditions_{user_id}.pdf",
                media_type="application/pdf",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        else:
            raise HTTPException(status_code=404, detail="PDF file not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download Terms & Conditions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )

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
            # ✅ CHANGED: Use unified PDFService
            pdf_service = PDFService(db)
            
            if user_type == "applicant":
                applicant = db.query(Applicant).filter(Applicant.id == user_id).first()
                if applicant:
                    # Prepare payment data if available
                    payment_data = None
                    if applicant.payment_reference and applicant.amount_paid:
                        payment_data = {
                            "reference": applicant.payment_reference,
                            "amount": applicant.amount_paid,
                            "date": applicant.created_at
                        }
                    
                    # Generate PDF using unified service
                    pdf_path = pdf_service.generate_application_form(
                        user_id=user_id,
                        user_type="applicant",
                        tier=applicant.application_tier,
                        payment_data=payment_data
                    )
                    
                    # Update database
                    applicant.application_pdf_path = pdf_path
                    applicant.application_generated_at = datetime.now()
                    db.commit()
            else:
                raise HTTPException(status_code=404, detail="PDF not found and cannot regenerate for this user type")
        
        # Serve the PDF file
        if pdf_path and Path(pdf_path).exists():
            return FileResponse(
                path=pdf_path,
                filename=f"Application_Form_{user_id}.pdf",
                media_type="application/pdf",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        else:
            raise HTTPException(status_code=404, detail="PDF file not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download Application Form: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )

@router.get("/applicant/{applicant_id}/all")
async def download_applicant_all_pdfs(
    applicant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download both PDFs for an applicant as a zip file
    """
    try:
        import zipfile
        import io
        
        # ✅ CHANGED: Use unified PDFService
        pdf_service = PDFService(db)
        
        # Find applicant
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            raise HTTPException(status_code=404, detail="Applicant not found")
        
        # Get PDF paths
        terms_path = applicant.terms_pdf_path
        app_path = applicant.application_pdf_path
        
        # Prepare payment data if available
        payment_data = None
        if applicant.payment_reference and applicant.amount_paid:
            payment_data = {
                "reference": applicant.payment_reference,
                "amount": applicant.amount_paid,
                "date": applicant.created_at
            }
        
        # Generate missing PDFs
        if not terms_path or not Path(terms_path).exists():
            # Generate Terms PDF
            terms_path = pdf_service.generate_terms_conditions(
                user_id=applicant_id,
                user_type="applicant",
                tier=applicant.application_tier
            )
            applicant.terms_pdf_path = terms_path
            applicant.terms_generated_at = datetime.now()
        
        if not app_path or not Path(app_path).exists():
            # Generate Application PDF
            app_path = pdf_service.generate_application_form(
                user_id=applicant_id,
                user_type="applicant",
                tier=applicant.application_tier,
                payment_data=payment_data
            )
            applicant.application_pdf_path = app_path
            applicant.application_generated_at = datetime.now()
        
        db.commit()
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add Terms & Conditions
            if terms_path and Path(terms_path).exists():
                zip_file.write(terms_path, f"Terms_Conditions_{applicant.full_name.replace(' ', '_')}.pdf")
            # Add Application Form
            if app_path and Path(app_path).exists():
                zip_file.write(app_path, f"Application_Form_{applicant.full_name.replace(' ', '_')}.pdf")
        
        zip_buffer.seek(0)
        
        # Return zip file
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=MarshalCore_Applicant_{applicant.full_name.replace(' ', '_')}_Documents.zip",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create PDF zip: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create zip file: {str(e)}"
        )

@router.get("/public/applicant/terms/{filename}")
async def download_public_applicant_terms(
    filename: str
):
    """
    Public endpoint to download Applicant Terms & Conditions PDF by filename
    """
    try:
        # Look for PDF in applicants directory
        pdf_path = f"static/pdfs/applicants/{filename}"
        
        if not Path(pdf_path).exists():
            # Try with .pdf extension if not provided
            if not filename.endswith('.pdf'):
                pdf_path = f"static/pdfs/applicants/{filename}.pdf"
            
            if not Path(pdf_path).exists():
                raise HTTPException(status_code=404, detail="PDF not found")
        
        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Disposition": f"inline; filename=\"{filename}\""
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download public applicant PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )

@router.get("/public/applicant/application/{filename}")
async def download_public_applicant_application(
    filename: str
):
    """
    Public endpoint to download Applicant Application Form PDF by filename
    """
    try:
        # Look for PDF in applicants directory
        pdf_path = f"static/pdfs/applicants/{filename}"
        
        if not Path(pdf_path).exists():
            # Try with .pdf extension if not provided
            if not filename.endswith('.pdf'):
                pdf_path = f"static/pdfs/applicants/{filename}.pdf"
            
            if not Path(pdf_path).exists():
                raise HTTPException(status_code=404, detail="PDF not found")
        
        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Disposition": f"inline; filename=\"{filename}\""
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download public applicant PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )

@router.get("/applicant/{applicant_id}/status")
async def get_applicant_pdf_status(
    applicant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get PDF generation status for an applicant
    """
    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            raise HTTPException(status_code=404, detail="Applicant not found")
        
        return {
            "applicant_id": str(applicant.id),
            "full_name": applicant.full_name,
            "email": applicant.email,
            "application_tier": applicant.application_tier,
            "pdfs": {
                "terms_and_conditions": {
                    "path": applicant.terms_pdf_path,
                    "generated_at": applicant.terms_generated_at.isoformat() if applicant.terms_generated_at else None,
                    "exists": applicant.terms_pdf_path and Path(applicant.terms_pdf_path).exists() if applicant.terms_pdf_path else False,
                    "download_url": f"/pdf/public/applicant/terms/{os.path.basename(applicant.terms_pdf_path)}" if applicant.terms_pdf_path else None
                },
                "application_form": {
                    "path": applicant.application_pdf_path,
                    "generated_at": applicant.application_generated_at.isoformat() if applicant.application_generated_at else None,
                    "exists": applicant.application_pdf_path and Path(applicant.application_pdf_path).exists() if applicant.application_pdf_path else False,
                    "download_url": f"/pdf/public/applicant/application/{os.path.basename(applicant.application_pdf_path)}" if applicant.application_pdf_path else None
                }
            },
            "guarantor_form": {
                "path": "static/guarantor-form.pdf",
                "download_url": "/static/guarantor-form.pdf"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get PDF status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )