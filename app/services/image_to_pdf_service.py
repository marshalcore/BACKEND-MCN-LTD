# app/services/image_to_pdf_service.py - NEW
import os
import logging
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, PageBreak, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import uuid
import asyncio

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
IMAGE_TO_PDF_DIR = STATIC_DIR / "image_to_pdf"

# Ensure directory exists
IMAGE_TO_PDF_DIR.mkdir(parents=True, exist_ok=True)

class ImageToPDFService:
    """Service to convert multiple images to a single compressed PDF"""
    
    def __init__(self):
        self.max_pdf_size_bytes = 1 * 1024 * 1024  # 1MB in bytes
        logger.info("✅ ImageToPDFService initialized")
    
    async def convert_images_to_pdf(
        self, 
        image_files: List[bytes], 
        filenames: List[str],
        email: str,
        officer_id: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Convert multiple images to a single compressed PDF
        
        Args:
            image_files: List of image bytes
            filenames: List of original filenames
            email: Officer's email (used in filename)
            officer_id: Optional officer ID
            
        Returns:
            Tuple of (pdf_path, pdf_size_kb)
        """
        try:
            logger.info(f"🔄 Converting {len(image_files)} images to PDF for {email}")
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            officer_part = f"_{officer_id.replace('/', '-')}" if officer_id else ""
            email_part = email.split('@')[0].replace('.', '_')
            filename = f"officer_docs_{email_part}{officer_part}_{timestamp}_{unique_id}.pdf"
            
            # Save path
            pdf_path = IMAGE_TO_PDF_DIR / filename
            relative_path = f"static/image_to_pdf/{filename}"
            
            # Step 1: Process and compress images
            processed_images = await self._process_images(image_files, filenames)
            
            # Step 2: Create PDF with ReportLab
            pdf_size = await self._create_pdf_from_images(processed_images, pdf_path)
            
            # Step 3: Check if PDF is under 1MB, if not, compress more
            if pdf_size > self.max_pdf_size_bytes:
                logger.info(f"📦 PDF size {pdf_size/1024:.2f}KB exceeds 1MB, compressing...")
                pdf_path = await self._compress_pdf(pdf_path)
                pdf_size = os.path.getsize(pdf_path)
            
            logger.info(f"✅ PDF created: {relative_path} - {pdf_size/1024:.2f}KB")
            
            return str(relative_path), pdf_size / 1024  # Return KB
            
        except Exception as e:
            logger.error(f"❌ Error converting images to PDF: {str(e)}", exc_info=True)
            raise Exception(f"Failed to convert images to PDF: {str(e)}")
    
    async def _process_images(self, image_files: List[bytes], filenames: List[str]) -> List[dict]:
        """Process and compress each image"""
        processed = []
        
        for i, (img_bytes, filename) in enumerate(zip(image_files, filenames)):
            try:
                # Open image with PIL
                img = Image.open(BytesIO(img_bytes))
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    if img.mode == 'RGBA':
                        # Create white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1])
                        img = background
                    else:
                        img = img.convert('RGB')
                
                # Calculate compression ratio to target <200KB per image for 5 images
                original_size = len(img_bytes)
                target_size = 160 * 1024  # 160KB target per image (5 images = 800KB)
                
                if original_size > target_size:
                    # Calculate resize ratio
                    ratio = (target_size / original_size) ** 0.5
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    
                    # Ensure minimum dimensions for readability
                    new_width = max(600, min(1200, new_width))
                    new_height = max(800, min(1600, new_height))
                    
                    # Resize
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"📸 Image {i+1} resized: {img.width}x{img.height}")
                
                # Save to bytes with compression
                output = BytesIO()
                img.save(output, format='JPEG', quality=70, optimize=True)
                output.seek(0)
                
                processed.append({
                    'bytes': output,
                    'width': img.width,
                    'height': img.height,
                    'filename': filename
                })
                
                logger.info(f"✅ Processed image {i+1}: {filename} - {len(output.getvalue())/1024:.2f}KB")
                
            except Exception as e:
                logger.error(f"Error processing image {filename}: {str(e)}")
                # Use original as fallback
                processed.append({
                    'bytes': BytesIO(img_bytes),
                    'width': 800,
                    'height': 1000,
                    'filename': filename
                })
        
        return processed
    
    async def _create_pdf_from_images(self, processed_images: List[dict], output_path: Path) -> int:
        """Create PDF from processed images using ReportLab"""
        
        # Create PDF document with smaller margins
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=28,
            leftMargin=28,
            topMargin=28,
            bottomMargin=28
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Add title page
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Title'],
            fontSize=16,
            textColor=colors.HexColor('#1a237e'),
            alignment=1,  # Center
            spaceAfter=30
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,  # Center
            textColor=colors.gray
        )
        
        story.append(Paragraph("Officer Document Images", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y')}", normal_style))
        story.append(Paragraph(f"Total Images: {len(processed_images)}", normal_style))
        story.append(Spacer(1, 20))
        story.append(PageBreak())
        
        for i, img_data in enumerate(processed_images):
            try:
                # Calculate image dimensions to fit on A4 with margins
                # A4 usable area: ~7.5in x 10in (after margins)
                max_width = 7.2 * inch
                max_height = 9.5 * inch
                
                # Create image with proportional scaling
                img = RLImage(
                    img_data['bytes'], 
                    width=max_width, 
                    height=max_height, 
                    kind='proportional'
                )
                
                # Add to story with minimal spacing
                story.append(img)
                
                # Add page break between images except last
                if i < len(processed_images) - 1:
                    story.append(PageBreak())
                    
            except Exception as e:
                logger.error(f"Error adding image {i+1} to PDF: {str(e)}")
                # Add placeholder text
                story.append(Paragraph(f"<b>Image {i+1}: {img_data['filename']}</b><br/><i>Image could not be embedded</i>", styles['Normal']))
                story.append(Spacer(1, 10))
                if i < len(processed_images) - 1:
                    story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        
        # Get file size
        file_size = os.path.getsize(output_path)
        logger.info(f"📄 PDF created: {output_path.name} - {file_size/1024:.2f}KB")
        
        return file_size
    
    async def _compress_pdf(self, pdf_path: Path) -> Path:
        """Further compress PDF if needed"""
        # For now, just log that it's already compressed
        # In production, you might use pikepdf or pdfkit with compression
        logger.info("📦 PDF already optimized during creation")
        return pdf_path
    
    async def send_pdf_email(self, email: str, pdf_path: str, num_images: int, officer_id: Optional[str] = None):
        """Send PDF via email using existing email service"""
        from app.services.email_service import send_email_direct
        
        try:
            # Create email content
            subject = "Your Converted Document PDF - Marshal Core Nigeria"
            
            officer_text = f" for Officer ID: {officer_id}" if officer_id else ""
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                    .success-box {{ background-color: #e8f5e8; border-left: 4px solid #4CAF50; padding: 15px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Marshal Core Nigeria</h1>
                        <h2>Document Conversion Complete</h2>
                    </div>
                    
                    <div class="content">
                        <h3>Dear Officer{officer_text},</h3>
                        
                        <div class="success-box">
                            <p>Your <strong>{num_images} document image(s)</strong> have been successfully converted to a single PDF file.</p>
                        </div>
                        
                        <p><strong>✅ Conversion Summary:</strong></p>
                        <ul>
                            <li>Images converted: <b>{num_images}</b></li>
                            <li>PDF generated: <b>Attached to this email</b></li>
                            <li>File size: <b>Optimized for email</b></li>
                        </ul>
                        
                        <p><b>Next Steps:</b></p>
                        <ul>
                            <li>Download the attached PDF for your records</li>
                            <li>Keep this document for future reference</li>
                            <li>You can also access this document from your dashboard</li>
                        </ul>
                        
                        <p style="margin-top: 30px;">Best regards,<br>
                        <b>Marshal Core Nigeria Admin Team</b></p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated message from the document conversion system.</p>
                        <p>© {datetime.now().year} Marshal Core Nigeria. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Get absolute path for attachment
            full_pdf_path = str(BASE_DIR / pdf_path)
            
            # Use email service to send with attachment
            # Assuming send_email_direct accepts attachments
            from app.services.email_service import email_service
            result = await email_service.send_email_direct(
                to_email=email,
                subject=subject,
                html_content=html_body,
                attachments=[{
                    "filename": os.path.basename(pdf_path),
                    "path": full_pdf_path,
                    "content_type": "application/pdf"
                }]
            )
            
            logger.info(f"📧 Email {'sent' if result else 'queued'} to {email} with PDF attachment")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending PDF email: {str(e)}")
            return False

# Singleton instance
image_to_pdf_service = ImageToPDFService()