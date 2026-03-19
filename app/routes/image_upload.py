# app/routes/image_upload.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import os

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.image_upload import ImageUploadResponse
from app.models.image_upload import ImageUploadRecord
from app.services.image_to_pdf_service import image_to_pdf_service
from app.services.email_service import send_image_to_pdf_email
from app.utils.image_processing import (
    validate_image_file,
    validate_image_count,
    read_image_file,
    normalize_filename
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/image-to-pdf",
    tags=["Admin - Image to PDF Conversion"]
)

@router.post(
    "/upload",
    response_model=ImageUploadResponse,
    summary="Upload images and convert to PDF (Admin only)",
    status_code=status.HTTP_201_CREATED
)
async def upload_images_to_pdf(
    background_tasks: BackgroundTasks,
    email: str = Form(..., description="Officer's email where PDF will be sent"),
    officer_id: str = Form(None, description="Optional officer ID for reference"),
    name: str = Form(None, description="Officer's name (for email greeting)"),
    notes: str = Form(None, description="Optional notes about this upload"),
    files: List[UploadFile] = File(..., description="4-5 image files (JPG, PNG)"),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)  # Admin only
):
    """
    📤 Upload 4-5 images, convert to single PDF (<1MB), and email to officer
    
    ✅ Admin only endpoint
    ✅ Accepts 4-5 image files (JPG, PNG)
    ✅ Auto-converts to single PDF
    ✅ PDF size < 1MB (compressed)
    ✅ Emails PDF to officer
    ✅ Saves record in database
    """
    try:
        # Validate number of files
        is_valid_count, count_error = validate_image_count(files)
        if not is_valid_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=count_error
            )
        
        # Validate email
        if not email or "@" not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid email is required"
            )
        
        # Process each file
        image_bytes_list = []
        filenames = []
        
        for file in files:
            # Validate file type
            is_valid, error = validate_image_file(file)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename}: {error}"
                )
            
            # Read file content
            content, error = await read_image_file(file)
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename}: {error}"
                )
            
            image_bytes_list.append(content)
            filenames.append(normalize_filename(file.filename))
            
            logger.info(f"📸 Received {file.filename}: {len(content)/1024:.2f}KB")
        
        # Convert images to PDF
        try:
            pdf_path, pdf_size_kb = await image_to_pdf_service.convert_images_to_pdf(
                image_files=image_bytes_list,
                filenames=filenames,
                email=email,
                officer_id=officer_id
            )
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF conversion failed: {str(e)}"
            )
        
        # Save record in database
        upload_record = ImageUploadRecord(
            email=email,
            officer_id=officer_id,
            pdf_path=pdf_path,
            pdf_size_kb=pdf_size_kb,
            num_images=len(files),
            notes=notes,
            uploaded_by=admin.get("email", "admin"),
            status="completed",
            email_sent=False
        )
        
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        
        # Send email with PDF in background
        background_tasks.add_task(
            send_pdf_email_task,
            email=email,
            name=name or email.split('@')[0],
            pdf_path=pdf_path,
            num_images=len(files),
            officer_id=officer_id,
            record_id=str(upload_record.id)
        )
        
        logger.info(f"✅ Images converted to PDF and queued for email to {email}")
        
        return ImageUploadResponse(
            status="success",
            message=f"Successfully converted {len(files)} images to PDF and queued for email",
            pdf_path=pdf_path,
            pdf_size_kb=pdf_size_kb,
            num_images=len(files),
            email_sent=False,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in image upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process images: {str(e)}"
        )


@router.get(
    "/history",
    response_model=List[dict],
    summary="Get upload history (Admin only)"
)
async def get_upload_history(
    skip: int = 0,
    limit: int = 50,
    email: str = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    📋 Get history of all image-to-PDF uploads
    Optional filter by email
    """
    try:
        query = db.query(ImageUploadRecord)
        
        if email:
            query = query.filter(ImageUploadRecord.email.ilike(f"%{email}%"))
        
        records = query.order_by(
            ImageUploadRecord.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return [
            {
                "id": str(r.id),
                "email": r.email,
                "officer_id": r.officer_id,
                "pdf_path": r.pdf_path,
                "pdf_size_kb": r.pdf_size_kb,
                "num_images": r.num_images,
                "created_at": r.created_at,
                "status": r.status,
                "email_sent": r.email_sent,
                "uploaded_by": r.uploaded_by,
                "notes": r.notes
            }
            for r in records
        ]
        
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch upload history"
        )


@router.get(
    "/stats",
    summary="Get upload statistics (Admin only)"
)
async def get_upload_stats(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    📊 Get statistics about image-to-PDF uploads
    """
    try:
        total = db.query(ImageUploadRecord).count()
        successful = db.query(ImageUploadRecord).filter(
            ImageUploadRecord.status == "completed"
        ).count()
        emails_sent = db.query(ImageUploadRecord).filter(
            ImageUploadRecord.email_sent == True
        ).count()
        
        # Get total images converted
        from sqlalchemy import func
        total_images = db.query(func.sum(ImageUploadRecord.num_images)).scalar() or 0
        
        # Get total PDF size
        total_size = db.query(func.sum(ImageUploadRecord.pdf_size_kb)).scalar() or 0
        
        return {
            "total_uploads": total,
            "successful_uploads": successful,
            "failed_uploads": total - successful,
            "emails_sent": emails_sent,
            "total_images_converted": total_images,
            "total_pdf_size_mb": total_size / 1024,
            "average_images_per_upload": total_images / total if total > 0 else 0,
            "success_rate": (successful / total * 100) if total > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.get(
    "/download/{record_id}",
    summary="Download PDF by record ID"
)
async def download_pdf(
    record_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    📥 Download a previously generated PDF
    """
    from fastapi.responses import FileResponse
    from uuid import UUID
    
    try:
        record = db.query(ImageUploadRecord).filter(
            ImageUploadRecord.id == UUID(record_id)
        ).first()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found"
            )
        
        # Get absolute path
        from pathlib import Path
        base_dir = Path(__file__).parent.parent.parent
        file_path = base_dir / record.pdf_path
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF file not found on server"
            )
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(record.pdf_path),
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error(f"Error downloading PDF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download PDF"
        )


# ==================== BACKGROUND TASK ====================

async def send_pdf_email_task(email: str, name: str, pdf_path: str, num_images: int, officer_id: str, record_id: str):
    """Background task to send PDF email"""
    try:
        from app.services.image_to_pdf_service import image_to_pdf_service
        from app.database import SessionLocal
        from app.models.image_upload import ImageUploadRecord
        from uuid import UUID
        
        # Send email using the email service function
        result = await send_image_to_pdf_email(
            to_email=email,
            name=name,
            pdf_path=pdf_path,
            num_images=num_images,
            officer_id=officer_id
        )
        
        # Update record
        db = SessionLocal()
        try:
            record = db.query(ImageUploadRecord).filter(
                ImageUploadRecord.id == UUID(record_id)
            ).first()
            if record:
                record.email_sent = result
                db.commit()
                logger.info(f"✅ Email status updated for record {record_id}: {result}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Background email task failed: {str(e)}")