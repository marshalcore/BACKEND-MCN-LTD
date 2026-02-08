# app/routes/form_submission.py - COMPLETE UPDATED VERSION WITH AUTHENTICATION FIX
from fastapi import APIRouter, UploadFile, Form, Depends, File, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.applicant import Applicant
from app.models.pre_applicant import PreApplicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
from app.utils.upload import save_upload
from app.schemas.applicant import ApplicantResponse
from app.services.email_service import send_guarantor_confirmation_email
from app.services.pdf.applicant_pdf_service import applicant_pdf_service
from app.services.email_service import send_applicant_documents_email, send_applicant_payment_receipt
from pydantic import EmailStr
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import func
import json
from zoneinfo import ZoneInfo
import logging
import os
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FIXED: Main application submission endpoint - WITH AUTHENTICATION FIX
@router.post("/apply")
async def submit_full_application(
    background_tasks: BackgroundTasks,
    application_password: str = Form(...),
    email: str = Form(...),
    application_tier: str = Form(...),
    pre_applicant_id: str = Form(...),
    full_name: str = Form(...),
    phone_number: str = Form(...),
    nin_number: Optional[str] = Form(None),
    date_of_birth: str = Form(...),
    state_of_residence: str = Form(...),
    lga: str = Form(...),
    address: str = Form(...),
    selected_reasons: str = Form(...),
    additional_details: Optional[str] = Form(None),
    passport_photo: UploadFile = File(...),
    nin_slip: Optional[UploadFile] = File(None),
    payment_reference: Optional[str] = Form(None),
    amount_paid: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """
    ✅ SUBMIT COMPLETE APPLICATION for NEW APPLICANTS (Regular/VIP)
    - Handles all applicant data submission
    - Generates PDFs using ApplicantPDFService
    - Sends tier-specific emails with PDF attachments
    - Returns application details with PDF paths
    """
    try:
        logger.info(f"📝 Starting application submission for: {email} (Tier: {application_tier})")
        
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

        # ✅ FIXED: Validate and fix pre_applicant_id
        try:
            # Check if it's 'undefined' string
            if pre_applicant_id == "undefined" or pre_applicant_id is None or pre_applicant_id == "":
                logger.error(f"❌ Invalid pre_applicant_id: '{pre_applicant_id}' for email: {email}")
                
                # Try to find pre-applicant by email only
                pre_applicant = db.query(PreApplicant).filter(
                    func.lower(PreApplicant.email) == email.lower()
                ).first()
                
                if pre_applicant and pre_applicant.id:
                    pre_applicant_id = str(pre_applicant.id)
                    logger.info(f"✅ Found pre-applicant ID by email: {pre_applicant_id}")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid pre-applicant ID. Please start a new application or contact support."
                    )
            
            # Validate UUID format
            try:
                uuid_obj = uuid.UUID(pre_applicant_id, version=4)
                logger.info(f"✅ Valid UUID format: {pre_applicant_id}")
            except ValueError:
                # Not a valid UUID, but might be a different identifier
                logger.warning(f"⚠️ Not a standard UUID: {pre_applicant_id}, but continuing...")
                
        except ValueError as e:
            logger.error(f"❌ Invalid UUID format for pre_applicant_id: {pre_applicant_id} - {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pre-applicant ID format. Please contact support with reference: {email}"
            )
        except Exception as e:
            logger.error(f"❌ Error processing pre_applicant_id: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error processing application credentials"
            )
        
        # FIXED: Find pre-applicant by ID and email only (password verified separately)
        pre_applicant = db.query(PreApplicant).filter(
            func.lower(PreApplicant.email) == email.lower()
        ).first()
        
        if not pre_applicant:
            logger.error(f"❌ No pre-applicant found for email: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid application credentials - pre-applicant not found"
            )
        
        logger.info(f"🔍 Found pre-applicant: ID={pre_applicant.id}, Email={pre_applicant.email}, HasPassword={bool(pre_applicant.application_password)}")
        
        # FIXED: Verify application password against stored password
        if not pre_applicant.application_password:
            logger.error(f"❌ No application password set for: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Application password not generated. Please generate password first."
            )
        
        # Debug password comparison
        logger.info(f"🔐 Password comparison - Provided: '{application_password}' (len={len(application_password)}), Stored: '{pre_applicant.application_password}' (len={len(pre_applicant.application_password)})")
        
        if pre_applicant.application_password != application_password:
            logger.error(f"❌ Password mismatch for: {email}")
            logger.error(f"   Provided: '{application_password}'")
            logger.error(f"   Stored: '{pre_applicant.application_password}'")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid application password"
            )
        
        logger.info(f"✅ Password verified successfully for: {email}")
        
        # Verify payment completion
        if not pre_applicant.has_paid:
            logger.error(f"❌ Payment not completed for: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment not completed"
            )
            
        # Verify application password validity
        current_time = datetime.now(ZoneInfo("UTC"))
        
        if pre_applicant.password_used:
            logger.error(f"❌ Password already used for: {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Application password has already been used"
            )
        
        # Check if privacy was accepted
        if not pre_applicant.privacy_accepted:
            logger.error(f"❌ Privacy not accepted for: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Privacy notice must be accepted before submitting application"
            )

        # Check if application already submitted
        if pre_applicant.application_submitted:
            logger.error(f"❌ Application already submitted for: {email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application already submitted with this email"
            )
        
        # Check if pre-applicant is verified
        if not pre_applicant.is_verified:
            logger.error(f"❌ Pre-applicant not verified: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your password before submitting application"
            )

        logger.info(f"✅ All validations passed for: {email}")
        
        # ✅ Save uploaded files
        passport_path = save_upload(passport_photo, "passports")
        
        # Handle optional NIN slip
        nin_path = None
        if nin_slip and nin_slip.filename:
            nin_path = save_upload(nin_slip, "nin_slips")

        # ✅ Create new applicant
        applicant = Applicant(
            # SECTION A: Basic Information
            phone_number=phone_number,
            nin_number=nin_number,
            date_of_birth=dob,
            state_of_residence=state_of_residence,
            lga=lga,
            address=address,
            
            # SECTION B: Documents
            passport_photo=passport_path,
            nin_slip=nin_path,
            
            # SECTION C: Application Details
            application_tier=application_tier,
            selected_reasons=reasons_list,
            additional_details=additional_details,
            
            # SECTION D: Pre-filled from pre-applicant
            full_name=full_name,
            email=email,
            
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
        
        logger.info(f"✅ Applicant created with ID: {applicant.id}")

        # ✅ Prepare data for PDF generation
        applicant_data = {
            "id": str(applicant.id),
            "unique_id": applicant.unique_id or f"APP-{applicant.id}",
            "full_name": full_name,
            "email": email,
            "phone_number": phone_number,
            "nin_number": nin_number,
            "date_of_birth": dob,
            "state_of_residence": state_of_residence,
            "lga": lga,
            "address": address,
            "passport_photo": passport_path,
            "selected_reasons": reasons_list,
            "additional_details": additional_details,
            "application_tier": application_tier
        }
        
        # ✅ Prepare payment data for PDF
        payment_data = None
        if payment_reference and amount_paid:
            payment_data = {
                "reference": payment_reference,
                "amount": float(amount_paid),
                "date": current_time
            }
        
        # ✅ Generate PDFs using NEW Applicant PDF Service
        pdf_results = None
        try:
            logger.info(f"📄 Generating PDFs for applicant: {applicant.id}")
            
            pdf_results = applicant_pdf_service.generate_applicant_pdfs(
                applicant_data=applicant_data,
                applicant_id=str(applicant.id),
                tier=application_tier,
                payment_data=payment_data
            )
            
            logger.info(f"✅ PDFs generated successfully")
            
            # Update applicant with PDF paths
            applicant.terms_pdf_path = pdf_results["terms_pdf_path"]
            applicant.application_pdf_path = pdf_results["application_pdf_path"]
            applicant.terms_generated_at = current_time
            applicant.application_generated_at = current_time
            
            db.commit()
            
        except Exception as pdf_error:
            logger.error(f"❌ PDF generation failed: {str(pdf_error)}")
            pdf_results = {
                "terms_pdf_path": None,
                "application_pdf_path": None,
                "guarantor_pdf_path": "static/guarantor-form.pdf"
            }
        
        # ✅ Send applicant documents email with tier-specific template
        try:
            background_tasks.add_task(
                send_applicant_documents_email,
                to_email=email,
                name=full_name,
                applicant_id=str(applicant.id),
                tier=application_tier,
                terms_pdf_path=pdf_results["terms_pdf_path"] if pdf_results else None,
                application_pdf_path=pdf_results["application_pdf_path"] if pdf_results else None,
                payment_amount=float(amount_paid) if amount_paid else None,
                payment_reference=payment_reference
            )
            logger.info(f"✅ Applicant documents email queued for {email}")
        except Exception as email_error:
            logger.error(f"❌ Failed to queue applicant documents email: {email_error}")
        
        # ✅ Send payment receipt if applicable
        if payment_reference and amount_paid:
            try:
                background_tasks.add_task(
                    send_applicant_payment_receipt,
                    to_email=email,
                    name=full_name,
                    payment_reference=payment_reference,
                    amount=float(amount_paid),
                    tier=application_tier
                )
                logger.info(f"✅ Payment receipt email queued for {email}")
            except Exception as receipt_error:
                logger.error(f"❌ Failed to queue payment receipt email: {receipt_error}")
        
        # ✅ Send guarantor confirmation email
        try:
            await send_guarantor_confirmation_email(email, full_name)
            logger.info(f"✅ Guarantor email sent to {email}")
        except Exception as email_error:
            logger.error(f"❌ Failed to send guarantor email: {email_error}")
            
        # ✅ Return response with PDF paths
        response_data = {
            "id": str(applicant.id),
            "applicant_id": applicant.unique_id or str(applicant.id),
            "full_name": full_name,
            "email": email,
            "phone_number": phone_number,
            "application_tier": application_tier,
            "is_verified": True,
            "has_paid": True,
            "created_at": current_time.isoformat(),
            "message": "Application submitted successfully. Documents are being processed and will be emailed to you."
        }
        
        # Add PDF paths if available
        if pdf_results:
            response_data.update({
                "terms_pdf_path": pdf_results.get("terms_pdf_path"),
                "application_pdf_path": pdf_results.get("application_pdf_path"),
                "guarantor_pdf_path": pdf_results.get("guarantor_pdf_path", "static/guarantor-form.pdf")
            })
        
        return response_data

    except HTTPException as he:
        logger.error(f"❌ HTTP Exception in apply: {he.detail}")
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating application: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating application: {str(e)}"
        )

# FIXED: Simple submit endpoint (for already created applicants)
@router.post("/submit")
async def submit_application(
    email: EmailStr = Form(...),
    full_name: str = Form(None),
    application_tier: str = Form("regular"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Submit applicant application and generate PDFs - UPDATED"""
    try:
        # Find applicant
        applicant = db.query(Applicant).filter(Applicant.email == email).first()
        if not applicant:
            raise HTTPException(status_code=404, detail="Applicant not found")

        if not applicant.is_verified:
            raise HTTPException(status_code=403, detail="Application not verified")

        name = full_name or applicant.full_name

        # Prepare applicant data for PDF
        applicant_data = {
            "id": str(applicant.id),
            "unique_id": applicant.unique_id or f"APP-{applicant.id}",
            "full_name": applicant.full_name,
            "email": applicant.email,
            "phone_number": applicant.phone_number,
            "nin_number": applicant.nin_number,
            "date_of_birth": applicant.date_of_birth,
            "state_of_residence": applicant.state_of_residence,
            "lga": applicant.lga,
            "address": applicant.address,
            "passport_photo": applicant.passport_photo,
            "selected_reasons": applicant.selected_reasons,
            "additional_details": applicant.additional_details,
            "application_tier": applicant.application_tier or application_tier
        }
        
        # Generate PDFs
        pdf_results = None
        try:
            pdf_results = applicant_pdf_service.generate_applicant_pdfs(
                applicant_data=applicant_data,
                applicant_id=str(applicant.id),
                tier=applicant.application_tier or application_tier
            )
            
            # Update database
            applicant.terms_pdf_path = pdf_results["terms_pdf_path"]
            applicant.application_pdf_path = pdf_results["application_pdf_path"]
            applicant.terms_generated_at = datetime.now(ZoneInfo("UTC"))
            applicant.application_generated_at = datetime.now(ZoneInfo("UTC"))
            
            db.commit()
            logger.info(f"✅ PDFs generated for {email}")
            
        except Exception as pdf_error:
            logger.error(f"❌ PDF generation failed for {email}: {str(pdf_error)}")
            pdf_results = {
                "terms_pdf_path": None,
                "application_pdf_path": None,
                "guarantor_pdf_path": "static/guarantor-form.pdf"
            }
        
        # Send emails
        email_success = False
        try:
            await send_applicant_documents_email(
                to_email=email,
                name=name,
                applicant_id=str(applicant.id),
                tier=applicant.application_tier or application_tier,
                terms_pdf_path=pdf_results["terms_pdf_path"] if pdf_results else None,
                application_pdf_path=pdf_results["application_pdf_path"] if pdf_results else None
            )
            
            await send_guarantor_confirmation_email(email, name)
            email_success = True
            logger.info(f"✅ Emails sent to {email}")
            
        except Exception as email_error:
            logger.error(f"❌ Email sending failed for {email}: {str(email_error)}")
        
        response_data = {
            "message": "Application submitted successfully.",
            "guarantor_form_url": "/static/guarantor-form.pdf",
            "emails_sent": email_success
        }
        
        if pdf_results and pdf_results.get("terms_pdf_path"):
            response_data.update({
                "terms_pdf_path": pdf_results["terms_pdf_path"],
                "application_pdf_path": pdf_results["application_pdf_path"],
                "pdfs_generated": True
            })
        else:
            response_data["pdfs_generated"] = False
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in submit endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting application: {str(e)}"
        )

# NEW: Save progress endpoint
@router.post("/save-progress")
async def save_application_progress(
    email: str = Form(...),
    form_data: str = Form(...),
    is_draft: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Save application progress as draft"""
    try:
        # Parse form data
        try:
            data = json.loads(form_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid form data format"
            )
        
        # Find or create pre-applicant
        pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()
        if not pre_applicant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pre-applicant not found"
            )
        
        # Save draft data
        pre_applicant.draft_data = data
        pre_applicant.draft_saved_at = datetime.now(ZoneInfo("UTC"))
        pre_applicant.is_draft = is_draft
        
        db.commit()
        
        return {
            "message": "Application progress saved successfully",
            "saved_at": pre_applicant.draft_saved_at.isoformat(),
            "is_draft": pre_applicant.is_draft
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving progress: {str(e)}"
        )

# NEW: Get saved progress
@router.get("/get-progress/{email}")
async def get_saved_progress(
    email: str,
    db: Session = Depends(get_db)
):
    """Get saved application progress"""
    pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()
    if not pre_applicant or not pre_applicant.draft_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved progress found"
        )
    
    return {
        "draft_data": pre_applicant.draft_data,
        "saved_at": pre_applicant.draft_saved_at.isoformat() if pre_applicant.draft_saved_at else None,
        "is_draft": pre_applicant.is_draft
    }

@router.post("/officer/submit")
async def submit_officer_application(
    email: EmailStr = Form(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Submit officer application and generate PDFs"""
    try:
        officer = db.query(Officer).filter(Officer.email == email).first()
        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found")

        name = officer.full_name or f"Officer {officer.unique_id}"
        
        # Note: Officer submissions use different PDF service
        # For now, just acknowledge the submission
        logger.info(f"Officer application submitted: {email}")
        
        return {
            "message": "Officer application submitted successfully.",
            "officer_id": officer.unique_id,
            "name": name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting officer application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting officer application: {str(e)}"
        )

@router.post("/existing-officer/submit")
async def submit_existing_officer_application(
    email: EmailStr = Form(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Submit existing officer application and generate PDFs"""
    try:
        officer = db.query(ExistingOfficer).filter(ExistingOfficer.email == email).first()
        if not officer:
            raise HTTPException(status_code=404, detail="Existing officer not found")

        if not officer.is_verified:
            raise HTTPException(status_code=403, detail="Officer not verified")

        name = officer.full_name
        
        # Note: Existing officer submissions use different system
        # For now, just acknowledge the submission
        logger.info(f"Existing officer application submitted: {email}")
        
        return {
            "message": "Existing officer application submitted successfully.",
            "officer_id": officer.officer_id,
            "name": name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting existing officer application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting existing officer application: {str(e)}"
        )

@router.get("/status/{email}")
async def get_application_status(
    email: str,
    db: Session = Depends(get_db)
):
    """Check application status"""
    try:
        normalized_email = email.strip().lower()
        
        # Check applicant
        applicant = db.query(Applicant).filter(
            Applicant.email == normalized_email
        ).first()
        
        if applicant:
            return {
                "status": "submitted",
                "applicant_id": str(applicant.id),
                "full_name": applicant.full_name,
                "email": applicant.email,
                "application_tier": applicant.application_tier,
                "has_pdf": bool(applicant.terms_pdf_path and applicant.application_pdf_path),
                "submitted_at": applicant.created_at.isoformat() if applicant.created_at else None
            }
        
        # Check pre-applicant
        pre_applicant = db.query(PreApplicant).filter(
            PreApplicant.email == normalized_email
        ).first()
        
        if pre_applicant:
            return {
                "status": pre_applicant.status,
                "has_paid": pre_applicant.has_paid,
                "privacy_accepted": pre_applicant.privacy_accepted,
                "application_submitted": pre_applicant.application_submitted,
                "password_generated": pre_applicant.password_generated,
                "password_used": pre_applicant.password_used
            }
        
        raise HTTPException(
            status_code=404,
            detail="No application found for this email"
        )
        
    except Exception as e:
        logger.error(f"Error getting application status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting application status: {str(e)}"
        )