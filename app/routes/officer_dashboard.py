# app/routes/officer_dashboard.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.officer import Officer
from app.models.applicant import Applicant
from app.schemas.officer import OfficerUpdate, OfficerProfile, OfficerResponse
from app.utils.token import get_current_officer
import shutil
import os
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid

router = APIRouter(
    prefix="/officer",
    tags=["Officer Dashboard"]
)

UPLOAD_DIR = "static/uploads/officers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/dashboard", response_model=OfficerProfile)
def get_officer_dashboard(
    current_officer: Officer = Depends(get_current_officer),
    db: Session = Depends(get_db)
):
    """
    Get officer dashboard data including assigned applicant information
    """
    try:
        profile_data = OfficerResponse.from_orm(current_officer).dict()
        
        if current_officer.applicant_id:
            applicant = db.query(Applicant).filter(
                Applicant.id == current_officer.applicant_id
            ).first()
            
            if applicant:
                profile_data["applicant_data"] = {
                    "full_name": applicant.full_name,
                    "email": applicant.email,
                    "phone_number": applicant.phone_number,
                    "nin_number": applicant.nin_number,
                    "gender": applicant.gender,
                    "date_of_birth": applicant.date_of_birth,
                    "residential_address": applicant.residential_address,
                    "state_of_residence": applicant.state_of_residence,
                    "local_government_residence": applicant.local_government_residence,
                    "local_government_origin": applicant.local_government_origin,
                    "additional_skills": applicant.additional_skills
                }
        
        return profile_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard data: {str(e)}"
        )

@router.get("/profile", response_model=OfficerResponse)
def get_officer_profile(
    current_officer: Officer = Depends(get_current_officer)
):
    """
    Get officer profile information
    """
    return OfficerResponse.from_orm(current_officer)

@router.put("/profile", response_model=OfficerResponse)
def update_officer_profile(
    data: OfficerUpdate,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    """
    Update officer profile information
    """
    try:
        update_data = data.dict(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(current_officer, key, value)

        current_officer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_officer)
        
        return OfficerResponse.from_orm(current_officer)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating profile: {str(e)}"
        )

@router.post("/upload")
def upload_officer_document(
    file: UploadFile = File(...),
    file_type: str = "passport",
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    """
    Upload officer profile picture (passport photo only)
    """
    try:
        if file_type != "passport":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only passport photos are allowed"
            )

        allowed_types = ["image/jpeg", "image/png", "image/avif"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPEG, PNG or AVIF images are allowed"
            )

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_ext = os.path.splitext(file.filename)[1]
        unique_id = uuid.uuid4().hex
        filename = f"passport_{current_officer.id}_{unique_id}{file_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if current_officer.passport and os.path.exists(current_officer.passport):
            try:
                os.remove(current_officer.passport)
            except OSError:
                pass

        current_officer.passport = filepath
        current_officer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_officer)

        return {
            "status": "success",
            "message": "Profile picture updated successfully",
            "filepath": filepath
        }

    except HTTPException:
        raise
    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )