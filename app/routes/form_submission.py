# app/routes/form_submission.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, UploadFile, Form, Depends, File, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.applicant import Applicant
from app.models.pre_applicant import PreApplicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.utils.upload import save_upload
from app.schemas.applicant import ApplicantResponse
from app.services.email_service import send_guarantor_confirmation_email, send_pdfs_email
from app.services.pdf_service import PDFService
from pydantic import EmailStr
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import func
import json
from zoneinfo import ZoneInfo
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def generate_and_send_pdfs(
    email: str,
    user_type: str = "applicant",
    db: Session = None
):
    """
    Background task to generate PDFs and send email
    """
    try:
        logger.info(f"📄 Generating PDFs for {user_type}: {email}")
        
        # Get user based on type
        user = None
        user_id = None
        name = ""
        
        if user_type == "applicant":
            user = db.query(Applicant).filter(Applicant.email == email).first()
            if user:
                user_id = str(user.id)
                name = user.full_name
                
        elif user_type == "officer":
            user = db.query(Officer).filter(Officer.email == email).first()
            if user:
                user_id = str(user.id)
                name = user.full_name or f"Officer {user.unique_id}"
                
        elif user_type == "existing_officer":
            user = db.query(ExistingOfficer).filter(ExistingOfficer.email == email).first()
            if user:
                user_id = str(user.id)
                name = user.full_name
                
        else:
            logger.error(f"Invalid user type: {user_type}")
            return
        
        if not user or not user_id:
            logger.error(f"User not found: {email}")
            return
        
        # Generate PDFs with PDFService
        pdf_service = PDFService(db)
        pdf_paths = pdf_service.generate_both_pdfs(user_id, user_type)
        
        # Update database with PDF paths
        current_time = datetime.now(ZoneInfo("UTC"))
        
        if user_type == "applicant":
            user.terms_pdf_path = pdf_paths.get("terms_pdf_path")
            user.application_pdf_path = pdf_paths.get("application_pdf_path")
            user.terms_generated_at = current_time
            user.application_generated_at = current_time
        elif user_type == "officer":
            user.terms_pdf_path = pdf_paths.get("terms_pdf_path")
            user.application_pdf_path = pdf_paths.get("application_pdf_path")
            user.terms_generated_at = current_time
            user.application_generated_at = current_time
        elif user_type == "existing_officer":
            user.terms_pdf_path = pdf_paths.get("terms_pdf_path")
            user.registration_pdf_path = pdf_paths.get("application_pdf_path")
            user.terms_generated_at = current_time
            user.registration_generated_at = current_time
        
        db.commit()
        
        # Send email with PDF attachments
        admin_email = "admin@marshalcoreng.com"
        success = await send_pdfs_email(
            to_email=email,
            name=name,
            terms_pdf_path=pdf_paths.get("terms_pdf_path"),
            application_pdf_path=pdf_paths.get("application_pdf_path"),
            cc_email=admin_email
        )
        
        if success:
            logger.info(f"✅ PDFs generated and emailed to {email}")
        else:
            logger.error(f"❌ Failed to send PDFs email to {email}")
            
    except Exception as e:
        logger.error(f"❌ Error in generate_and_send_pdfs for {email}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

@router.post("/apply", response_model=ApplicantResponse)
async def apply(
    # SECTION A: Basic Information (8 fields)
    phone_number: str = Form(...),
    nin_number: str = Form(...),
    date_of_birth: str = Form(...),
    state_of_residence: str = Form(...),
    lga: str = Form(...),
    address: str = Form(...),
    
    # SECTION B: Document Uploads (2 uploads only) - INCLUDES PASSPORT
    passport_photo: UploadFile = File(...),
    nin_slip: UploadFile = File(...),
    
    # SECTION C: Application Details
    selected_reasons: str = Form(...),  # JSON string of selected reasons
    additional_details: Optional[str] = Form(None),
    application_tier: str = Form(...),  # 'regular' or 'vip'
    
    # SECTION D: Verification
    application_password: str = Form(...),
    
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    try:
        normalized_email = None
        
        # Validate application tier
        if application_tier not in ["regular", "vip"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid application tier. Must be 'regular' or 'vip'."
            )
        
        # Parse and validate reasons
        try:
            reasons_list = json.loads(selected_reasons)
            if not isinstance(reasons_list, list):
                raise ValueError("Reasons must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reasons format: {str(e)}"
            )
        
        # Validate reasons based on tier
        if application_tier == "regular":
            if len(reasons_list) < 1 or len(reasons_list) > 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Regular applicants must select 1-3 reasons"
                )
        elif application_tier == "vip":
            if len(reasons_list) < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="VIP applicants must select at least 1 reason"
                )
        
        # Validate date format
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD."
            )

        # Verify pre-applicant exists via application password
        pre_applicant = db.query(PreApplicant).filter(
            PreApplicant.application_password == application_password
        ).first()
        
        if not pre_applicant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid application password"
            )
            
        # Set normalized email from pre_applicant
        normalized_email = pre_applicant.email.strip().lower()
        
        # Verify payment completion
        if not pre_applicant.has_paid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment not completed"
            )
            
        # Verify application password validity
        current_time = datetime.now(ZoneInfo("UTC"))
        
        # FIX: Handle datetime comparison with timezone awareness
        if pre_applicant.application_password != application_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid application password"
            )
        
        if pre_applicant.password_used:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Application password has already been used"
            )
            
        if not pre_applicant.password_expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Application password not properly generated"
            )
        
        # FIXED DATETIME COMPARISON: Handle timezone-aware vs naive datetimes
        expires_at = pre_applicant.password_expires_at
        if expires_at.tzinfo is None:
            # If datetime is naive, make it aware with UTC
            expires_at_aware = expires_at.replace(tzinfo=ZoneInfo("UTC"))
        else:
            expires_at_aware = expires_at
        
        # Now compare safely with timezone-aware datetime
        if expires_at_aware <= current_time:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Application password has expired. Please request a new one."
            )

        # Check if privacy was accepted
        if not pre_applicant.privacy_accepted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Privacy notice must be accepted before submitting application"
            )

        # Check if application already submitted
        if pre_applicant.application_submitted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application already submitted with this email"
            )

        # ✅ Save uploaded files - PASSPORT IS SAVED HERE
        passport_path = save_upload(passport_photo, "passports")
        nin_path = save_upload(nin_slip, "nin_slips")

        # Create new applicant with simplified fields
        applicant = Applicant(
            # SECTION A: Basic Information
            phone_number=phone_number,
            nin_number=nin_number,
            date_of_birth=dob,
            state_of_residence=state_of_residence,
            lga=lga,
            address=address,
            
            # SECTION B: Documents - INCLUDES PASSPORT PATH
            passport_photo=passport_path,
            nin_slip=nin_path,
            
            # SECTION C: Application Details
            application_tier=application_tier,
            selected_reasons=reasons_list,
            additional_details=additional_details,
            
            # SECTION D: Pre-filled from pre-applicant
            full_name=pre_applicant.full_name,
            email=pre_applicant.email,
            
            # SECTION E: Meta Information
            is_verified=True,
            has_paid=True,
            payment_type=application_tier
        )

        # Mark password as used and application as submitted
        pre_applicant.password_used = True
        pre_applicant.application_submitted = True
        pre_applicant.submitted_at = current_time
        pre_applicant.status = "submitted"

        db.add(applicant)
        db.commit()
        db.refresh(applicant)
        
        # Send guarantor confirmation email
        try:
            await send_guarantor_confirmation_email(applicant.email, applicant.full_name)
        except Exception as email_error:
            logger.error(f"Failed to send guarantor email: {email_error}")
        
        # Add background task to generate and send PDFs
        if background_tasks:
            background_tasks.add_task(
                generate_and_send_pdfs,
                email=applicant.email,
                user_type="applicant",
                db=db
            )
            
            # Return proper response matching ApplicantResponse schema
            return ApplicantResponse(
                id=applicant.id,
                full_name=applicant.full_name,
                email=applicant.email,
                phone_number=applicant.phone_number,
                nin_number=applicant.nin_number,
                date_of_birth=applicant.date_of_birth,
                state_of_residence=applicant.state_of_residence,
                lga=applicant.lga,
                address=applicant.address,
                passport_photo=applicant.passport_photo,
                nin_slip=applicant.nin_slip,
                application_tier=applicant.application_tier,
                selected_reasons=applicant.selected_reasons,
                additional_details=applicant.additional_details,
                is_verified=applicant.is_verified,
                has_paid=applicant.has_paid,
                payment_type=applicant.payment_type,
                created_at=applicant.created_at
            )
        else:
            # Synchronous fallback
            await generate_and_send_pdfs(applicant.email, "applicant", db)
            
            # Return proper response matching ApplicantResponse schema
            return ApplicantResponse(
                id=applicant.id,
                full_name=applicant.full_name,
                email=applicant.email,
                phone_number=applicant.phone_number,
                nin_number=applicant.nin_number,
                date_of_birth=applicant.date_of_birth,
                state_of_residence=applicant.state_of_residence,
                lga=applicant.lga,
                address=applicant.address,
                passport_photo=applicant.passport_photo,
                nin_slip=applicant.nin_slip,
                application_tier=applicant.application_tier,
                selected_reasons=applicant.selected_reasons,
                additional_details=applicant.additional_details,
                is_verified=applicant.is_verified,
                has_paid=applicant.has_paid,
                payment_type=applicant.payment_type,
                created_at=applicant.created_at
            )

    except HTTPException as he:
        logger.error(f"HTTP Exception in apply: {he.detail}")
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating application: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating application: {str(e)}"
        )

@router.post("/submit")
async def submit_application(
    email: EmailStr = Form(...),
    full_name: str = Form(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Submit applicant application and generate PDFs"""
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
    """Submit officer application and generate PDFs"""
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
    """Submit existing officer application and generate PDFs"""
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