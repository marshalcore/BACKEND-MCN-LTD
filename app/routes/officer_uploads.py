from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.officer import Officer
from app.auth.dependencies import get_current_officer
import shutil
import os
from uuid import uuid4
import logging
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/officer/uploads",
    tags=["Officer Uploads"]
)

UPLOAD_DIR = "static/uploads/officers"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def save_upload(file: UploadFile, subdir: str) -> str:
    """Save uploaded file to the appropriate directory"""
    # Create directory if it doesn't exist
    target_dir = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Generate unique filename
    filename = f"{uuid4().hex}_{file.filename}"
    path = os.path.join(target_dir, filename)

    # Save file
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Return relative path for database storage
    relative_path = os.path.join("officers", subdir, filename).replace("\\", "/")
    return relative_path


@router.post("/documents", summary="Upload officer documents")
async def upload_documents(
    passport: Optional[UploadFile] = File(None),
    nin_slip: Optional[UploadFile] = File(None),
    ssce: Optional[UploadFile] = File(None),
    degree: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer)
):
    """
    Upload documents for an officer.
    
    Allowed file types: JPG, JPEG, PNG, PDF
    Max file size: 5MB
    """
    updated = False
    uploaded_files = []

    try:
        if passport:
            officer.passport_photo = save_upload(passport, "passport")
            uploaded_files.append("passport")
            updated = True
        
        if nin_slip:
            officer.nin_slip = save_upload(nin_slip, "nin")
            uploaded_files.append("nin_slip")
            updated = True
        
        if ssce:
            officer.ssce_certificate = save_upload(ssce, "ssce")
            uploaded_files.append("ssce")
            updated = True
        
        if degree:
            officer.higher_education_degree = save_upload(degree, "degree")
            uploaded_files.append("degree")
            updated = True

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files uploaded"
            )

        db.commit()
        logger.info(f"Officer {officer.id} uploaded documents: {uploaded_files}")
        
        return {
            "message": "Documents uploaded successfully",
            "uploaded_files": uploaded_files,
            "officer_id": str(officer.id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading documents for officer {officer.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload documents"
        )