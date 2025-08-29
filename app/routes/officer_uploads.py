from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.officer import Officer
from app.auth.dependencies import get_current_officer
import shutil, os
from uuid import uuid4

router = APIRouter(
    prefix="/officer/uploads",
    tags=["Officer Uploads"]
)

UPLOAD_DIR = "uploads/officers"

def save_upload(file: UploadFile, subdir: str) -> str:
    os.makedirs(os.path.join(UPLOAD_DIR, subdir), exist_ok=True)
    filename = f"{uuid4().hex}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, subdir, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return path.replace("\\", "/")  # Normalize Windows path

@router.post("/documents")
def upload_documents(
    passport: UploadFile = File(None),
    nin_slip: UploadFile = File(None),
    ssce: UploadFile = File(None),
    degree: UploadFile = File(None),
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer)
):
    updated = False

    if passport:
        officer.passport_photo = save_upload(passport, "passport")
        updated = True
    if nin_slip:
        officer.nin_slip = save_upload(nin_slip, "nin")
        updated = True
    if ssce:
        officer.ssce_certificate = save_upload(ssce, "ssce")
        updated = True
    if degree:
        officer.higher_education_degree = save_upload(degree, "degree")
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No files uploaded")

    db.commit()
    return {"message": "Documents uploaded successfully"}
