# This route handles the application form submission for the event. It processes the applicant's information, validates their application password, checks their payment status, and saves their application details along with uploaded documents. The route ensures that only valid and complete applications are accepted, and it provides appropriate error responses for various failure scenarios.
from fastapi import APIRouter, UploadFile, Form, Depends, File, HTTPException, status
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.applicant import Applicant
from app.models.pre_applicant import PreApplicant
from app.utils.upload import save_upload
from app.schemas.applicant import ApplicantResponse
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import func
import json
from zoneinfo import ZoneInfo

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        if (pre_applicant.application_password != application_password or
            pre_applicant.password_used or
            not pre_applicant.password_expires_at or
            pre_applicant.password_expires_at <= current_time):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired application password"
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
            has_paid=True
        )

        # Mark password as used and application as submitted
        pre_applicant.password_used = True
        pre_applicant.application_submitted = True
        pre_applicant.submitted_at = current_time
        pre_applicant.status = "submitted"

        db.add(applicant)
        db.commit()
        db.refresh(applicant)

        return applicant

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating application: {str(e)}"
        )