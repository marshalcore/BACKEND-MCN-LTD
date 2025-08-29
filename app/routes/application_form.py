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

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/apply", response_model=ApplicantResponse)
async def apply(
    # SECTION A: Personal Information
    category: str = Form(...),
    marital_status: str = Form(...),
    nin_number: str = Form(...),
    full_name: str = Form(...),
    first_name: str = Form(...),
    surname: str = Form(...),
    other_name: Optional[str] = Form(None),
    email: str = Form(...),
    mobile_number: str = Form(...),
    phone_number: str = Form(...),
    gender: str = Form(...),
    nationality: str = Form(...),
    country_of_residence: str = Form(...),
    state_of_origin: str = Form(...),
    state_of_residence: str = Form(...),
    residential_address: str = Form(...),
    local_government_residence: str = Form(...),
    local_government_origin: str = Form(...),
    date_of_birth: str = Form(...),
    religion: str = Form(...),
    place_of_birth: str = Form(...),
    
    # SECTION B: Documents
    passport_photo: UploadFile = File(...),
    nin_slip: UploadFile = File(...),
    ssce_certificate: UploadFile = File(...),
    higher_education_degree: Optional[UploadFile] = File(None),
    
    # SECTION C: Additional Information
    do_you_smoke: bool = Form(False),
    agree_to_join: bool = Form(...),
    agree_to_abide_rules: bool = Form(...),
    agree_to_return_properties: bool = Form(...),
    additional_skills: Optional[str] = Form(None),
    design_rating: Optional[int] = Form(None),
    
    # SECTION D: Financial Information
    bank_name: str = Form(...),
    account_number: str = Form(...),
    
    db: Session = Depends(get_db)
):
    try:
        # Validate date format
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD."
            )

        # Save uploaded files
        passport_path = save_upload(passport_photo, "passports")
        nin_path = save_upload(nin_slip, "nin_slips")
        ssce_path = save_upload(ssce_certificate, "ssce")
        degree_path = save_upload(higher_education_degree, "degrees") if higher_education_degree else None

        # Verify pre-applicant status
        pre_applicant = db.query(PreApplicant).filter(
            PreApplicant.email == email
        ).first()
        
        if not pre_applicant or not pre_applicant.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pre-applicant is not verified"
            )

        # Create new applicant
        applicant = Applicant(
            # SECTION A: Personal Information
            category=category,
            marital_status=marital_status,
            nin_number=nin_number,
            full_name=full_name,
            first_name=first_name,
            surname=surname,
            other_name=other_name,
            email=email,
            mobile_number=mobile_number,
            phone_number=phone_number,
            gender=gender,
            nationality=nationality,
            country_of_residence=country_of_residence,
            state_of_origin=state_of_origin,
            state_of_residence=state_of_residence,
            residential_address=residential_address,
            local_government_residence=local_government_residence,
            local_government_origin=local_government_origin,
            date_of_birth=dob,
            religion=religion,
            place_of_birth=place_of_birth,
            
            # SECTION B: Documents
            passport_photo=passport_path,
            nin_slip=nin_path,
            ssce_certificate=ssce_path,
            higher_education_degree=degree_path,
            
            # SECTION C: Additional Information
            do_you_smoke=do_you_smoke,
            agree_to_join=agree_to_join,
            agree_to_abide_rules=agree_to_abide_rules,
            agree_to_return_properties=agree_to_return_properties,
            additional_skills=additional_skills,
            design_rating=design_rating,
            
            # SECTION D: Financial Information
            bank_name=bank_name,
            account_number=account_number,
            
            # SECTION E: Meta Information
            is_verified=True,
            has_paid=pre_applicant.has_paid if pre_applicant else False
        )

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