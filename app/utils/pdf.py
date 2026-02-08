# app/utils/pdf.py - COMPLETE UPDATED VERSION WITH APPLICANT SUPPORT
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid
import requests
from io import BytesIO

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Frame
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
PDFS_DIR = STATIC_DIR / "pdfs"
TERMS_DIR = PDFS_DIR / "terms"
APPLICATIONS_DIR = PDFS_DIR / "applications"
APPLICANTS_DIR = PDFS_DIR / "applicants"  # NEW: For applicant PDFs
LOGO_DIR = STATIC_DIR / "images"
UPLOADS_DIR = STATIC_DIR / "uploads"

# Ensure directories exist
for directory in [PDFS_DIR, TERMS_DIR, APPLICATIONS_DIR, APPLICANTS_DIR, LOGO_DIR, UPLOADS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Company information - Updated with correct details
COMPANY_INFO = {
    "name": "Marshal Core of Nigeria",  # Changed from "Marshal Core Nigeria"
    "certificate_number": "YA/CLB/10100",
    "rc_number": "8405988",
    "address_line1": "KM. 3, MARSHAL CORE OF NIGERIA NATIONAL HEADQUARTERS",
    "address_line2": "ABUMWENRENRE COMMUNITY, EKIADOLOR/AGEKPANU ROAD",
    "address_line3": "BENIN CITY, EDO STATE, NIGERIA",
    "phone": "+234 9137 428 031",
    "email": "info@marshalcoreofnigeria.ng",
    "website": "www.marshalcoreofnigeria.ng",
    "logo_path": str(LOGO_DIR / "logo.png")  # Local logo path
}

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

# Keep this function exactly as it was
async def generate_existing_officer_pdfs_and_email(officer_id: str, email: str, full_name: str, db: Session):
    """
    ✅ Generate PDFs and send email with DIRECT DOWNLOAD LINKS
    This function is called by the route handler
    """
    from app.models.existing_officer import ExistingOfficer
    from app.services.email_service import send_existing_officer_pdfs_email
    from app.services.existing_officer_service import ExistingOfficerService
    
    try:
        logger.info(f"🔄 Starting PDF auto-generation for existing officer: {officer_id}")
        
        # Get officer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            logger.error(f"❌ Officer not found: {officer_id}")
            return {"success": False, "error": "Officer not found"}
        
        logger.info(f"✅ Found officer: {full_name} ({email})")
        
        # Generate PDFs using the PDFGenerator class
        pdf_gen = PDFGenerator()
        
        # Prepare officer data for PDF generation
        officer_data = {
            "full_name": full_name,
            "nin_number": officer.nin_number,
            "residential_address": officer.residential_address,
            "rank": officer.rank,
            "position": officer.position,
            "unique_id": officer_id,
            "email": email,
            "phone": officer.phone,
            "gender": officer.gender,
            "marital_status": officer.marital_status,
            "nationality": officer.nationality,
            "religion": officer.religion,
            "place_of_birth": officer.place_of_birth,
            "date_of_birth": officer.date_of_birth,
            "state_of_residence": officer.state_of_residence,
            "local_government_residence": officer.local_government_residence,
            "country_of_residence": officer.country_of_residence,
            "state_of_origin": officer.state_of_origin,
            "local_government_origin": officer.local_government_origin,
            "years_of_service": officer.years_of_service,
            "service_number": officer.service_number,
            "additional_skills": officer.additional_skills,
            "bank_name": officer.bank_name,
            "account_number": officer.account_number,
            "date_of_enlistment": officer.date_of_enlistment,
            "date_of_promotion": officer.date_of_promotion,
            "category": officer.category,
            "passport_path": officer.passport_path,  # ✅ FIXED: Use passport_path instead of passport_photo
        }
        
        logger.info(f"📄 Generating Terms & Conditions PDF for {officer_id}")
        terms_pdf_path = pdf_gen.generate_terms_conditions(officer_data, str(officer.id))
        
        logger.info(f"📄 Generating Application Form PDF for {officer_id}")
        app_pdf_path = pdf_gen.generate_application_form(officer_data, str(officer.id))
        
        # ✅ CREATE PUBLIC DOWNLOAD URLs
        base_url = "https://backend-mcn-ltd.onrender.com"
        terms_filename = os.path.basename(terms_pdf_path)
        registration_filename = os.path.basename(app_pdf_path)
        
        terms_pdf_url = f"{base_url}/download/pdf/{terms_filename}"
        registration_pdf_url = f"{base_url}/download/pdf/{registration_filename}"
        
        logger.info(f"✅ Generated download URLs:")
        logger.info(f"   Terms: {terms_pdf_url}")
        logger.info(f"   Registration: {registration_pdf_url}")
        
        # Update PDF paths in database
        ExistingOfficerService.update_pdf_paths(
            db,
            officer_id,
            terms_pdf_path,
            app_pdf_path  # This should be registration_pdf_path
        )
        
        # ✅ Send email with DIRECT DOWNLOAD LINKS
        email_result = await send_existing_officer_pdfs_email(
            to_email=email,
            name=full_name,
            officer_id=officer_id,
            terms_pdf_path=terms_pdf_path,
            registration_pdf_path=app_pdf_path
        )
        
        if email_result:
            logger.info(f"📧 Email with download links queued for {email}")
        else:
            logger.warning(f"⚠️ Email queuing failed for {email}")
        
        logger.info(f"✅ PDF generation and email queuing COMPLETE for {officer_id}")
        
        return {
            "success": True,
            "officer_id": officer_id,
            "email": email,
            "terms_pdf_path": terms_pdf_path,
            "registration_pdf_path": app_pdf_path,
            "terms_pdf_url": terms_pdf_url,
            "registration_pdf_url": registration_pdf_url,
            "email_queued": email_result
        }
            
    except Exception as e:
        logger.error(f"❌ Error generating PDFs for {officer_id}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

# NEW: Applicant PDF generation function
async def generate_applicant_pdfs_and_email(applicant_data: Dict[str, Any], applicant_id: str, 
                                          email: str, full_name: str, tier: str, 
                                          payment_data: Optional[Dict] = None):
    """
    ✅ Generate PDFs for NEW APPLICANT and send email
    """
    try:
        logger.info(f"🔄 Starting PDF generation for applicant: {applicant_id} (Tier: {tier})")
        
        # Generate PDFs using the PDFGenerator class
        pdf_gen = PDFGenerator()
        
        # Generate all PDFs for applicant
        pdf_results = pdf_gen.generate_applicant_pdfs(
            applicant_data=applicant_data,
            applicant_id=applicant_id,
            tier=tier,
            payment_data=payment_data
        )
        
        logger.info(f"✅ PDFs generated for applicant {applicant_id}")
        
        return {
            "success": True,
            "applicant_id": applicant_id,
            "email": email,
            "tier": tier,
            "terms_pdf_path": pdf_results["terms_pdf_path"],
            "application_pdf_path": pdf_results["application_pdf_path"],
            "guarantor_pdf_path": pdf_results["guarantor_pdf_path"],
            "generated_at": pdf_results["generated_at"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating PDFs for applicant {applicant_id}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

class PDFGenerator:
    """PDF generation utility using ReportLab - NOW SUPPORTS BOTH OFFICERS AND APPLICANTS"""
    
    def __init__(self):
        """Initialize PDF generator"""
        logger.info("Initializing ReportLab PDF Generator")
        self.logo_image = None
        self.logo_bytes = None
        self._try_load_logo()
    
    def _try_load_logo(self):
        """Try to load logo from local file with enhanced fallback"""
        try:
            # Try local file from static/images/logo.png
            logo_path = Path(COMPANY_INFO['logo_path'])
            
            if logo_path.exists():
                with open(logo_path, 'rb') as f:
                    self.logo_bytes = f.read()
                    self.logo_image = BytesIO(self.logo_bytes)
                logger.info("✅ Logo loaded successfully from local file")
                return True
            else:
                # Try to find logo in different locations
                possible_paths = [
                    LOGO_DIR / "logo.png",
                    STATIC_DIR / "logo.png",
                    BASE_DIR / "static" / "images" / "logo.png",
                    BASE_DIR / "static" / "logo.png",
                    Path("/app/static/images/logo.png"),  # For Render deployment
                    Path("/app/static/logo.png"),  # For Render deployment
                ]
                
                for path in possible_paths:
                    if path.exists():
                        with open(path, 'rb') as f:
                            self.logo_bytes = f.read()
                            self.logo_image = BytesIO(self.logo_bytes)
                        logger.info(f"✅ Logo loaded from {path}")
                        return True
                
                # Try to create a placeholder logo
                logger.warning("❌ Logo file not found in any expected location, creating placeholder")
                self._create_placeholder_logo()
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ Could not load logo: {e}")
            self._create_placeholder_logo()
            return True
    
    def _create_placeholder_logo(self):
        """Create a placeholder logo if real logo is not found"""
        try:
            from reportlab.lib.utils import ImageReader
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Create a simple image with text
            img = Image.new('RGB', (200, 100), color=(26, 35, 126))  # Dark blue background
            draw = ImageDraw.Draw(img)
            
            # Try to use a font
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                font = ImageFont.load_default()
            
            # Draw text
            draw.text((10, 10), "MCN", fill=(255, 255, 255), font=font)
            draw.text((10, 50), "Marshal Core", fill=(255, 255, 255), font=font)
            
            # Convert to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            self.logo_image = img_bytes
            self.logo_bytes = img_bytes.getvalue()
            logger.info("✅ Created placeholder logo")
            
        except Exception as e:
            logger.error(f"Failed to create placeholder logo: {e}")
            self.logo_image = None
            self.logo_bytes = None
    
    def _generate_filename(self, user_id: str, document_type: str, tier: str = "") -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        tier_prefix = f"{tier}_" if tier else ""
        return f"{tier_prefix}{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, category: str, filename: str) -> Tuple[str, str]:
        """Get filepath for saving PDF"""
        category_dir = PDFS_DIR / category
        category_dir.mkdir(exist_ok=True)
        
        file_path = category_dir / filename
        
        # Return relative path for web access
        relative_path = f"static/pdfs/{category}/{filename}"
        logger.info(f"PDF will be saved to: {relative_path}")
        return str(file_path), relative_path
    
    def _resolve_passport_path(self, passport_path: str) -> Optional[Path]:
        """Resolve absolute path for passport photo"""
        if not passport_path:
            return None
        
        try:
            # Check if it's already an absolute path
            if os.path.isabs(passport_path):
                path = Path(passport_path)
                if path.exists():
                    logger.info(f"✅ Found absolute passport path: {path}")
                    return path
            
            # Try different path patterns
            possible_paths = [
                UPLOADS_DIR / passport_path,
                BASE_DIR / "static" / passport_path,
                BASE_DIR / passport_path,
                Path("/app/static/uploads") / passport_path,
            ]
            
            # Also try just the filename
            if "/" in passport_path:
                filename = passport_path.split("/")[-1]
                possible_paths.extend([
                    UPLOADS_DIR / "passports" / filename,
                    BASE_DIR / "static" / "uploads" / "passports" / filename,
                    Path("/app/static/uploads/passports") / filename,
                ])
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"✅ Found passport photo at: {path}")
                    return path
            
            logger.warning(f"Passport photo not found for: {passport_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving passport path: {e}")
            return None
    
    def _prepare_passport_image(self, passport_path: str, width=1.5*inch, height=2*inch) -> Optional[Image]:
        """Prepare passport image for PDF embedding"""
        try:
            absolute_path = self._resolve_passport_path(passport_path)
            if not absolute_path:
                logger.warning(f"Passport path could not be resolved: {passport_path}")
                return None
            
            # Open and validate image
            pil_img = PILImage.open(absolute_path)
            
            # Convert RGBA to RGB if necessary
            if pil_img.mode in ('RGBA', 'LA', 'P'):
                if pil_img.mode == 'P':
                    pil_img = pil_img.convert('RGB')
                else:
                    # Create white background for transparent images
                    background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                    if pil_img.mode == 'RGBA':
                        background.paste(pil_img, mask=pil_img.split()[-1])
                    else:
                        background.paste(pil_img, mask=pil_img)
                    pil_img = background
            
            # Resize if necessary while maintaining aspect ratio
            max_width, max_height = 400, 400
            if pil_img.width > max_width or pil_img.height > max_height:
                pil_img.thumbnail((max_width, max_height), PILImage.Resampling.LANCZOS)
            
            # Save to bytes
            img_bytes = BytesIO()
            pil_img.save(img_bytes, format='JPEG', quality=90)
            img_bytes.seek(0)
            
            logger.info(f"✅ Passport photo prepared: {absolute_path}, size: {pil_img.size}")
            return Image(img_bytes, width=width, height=height)
            
        except Exception as e:
            logger.error(f"Error preparing passport image: {e}")
            return None
    
    def _create_header_footer(self, canvas_obj, doc, title="", is_terms=False):
        """Create header and footer for all pages with logo"""
        canvas_obj.saveState()
        
        # Add logo at top right corner if available
        if self.logo_image and self.logo_bytes:
            try:
                self.logo_image.seek(0)
                
                # Draw logo at top right
                logo_width = 1.5 * inch
                logo_height = 0.75 * inch
                logo_x = doc.width + doc.leftMargin - logo_width - 0.2*inch
                logo_y = doc.height + doc.topMargin - 0.0*inch
                
                canvas_obj.drawImage(ImageReader(self.logo_image), logo_x, logo_y, 
                                   width=logo_width, height=logo_height, 
                                   mask='auto', preserveAspectRatio=True)
                logger.info("✅ Logo added to PDF header")
            except Exception as e:
                logger.warning(f"Could not draw logo image: {e}")
                # Fallback to text
                self._draw_logo_placeholder(canvas_obj, doc)
        else:
            # Draw text placeholder for logo
            self._draw_logo_placeholder(canvas_obj, doc)
        
        # Header text
        canvas_obj.setFont('Helvetica-Bold', 14)
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        canvas_obj.drawString(doc.leftMargin, doc.height + doc.topMargin + 0.8*inch, COMPANY_INFO['name'])
        
        # Address in 3 lines
        canvas_obj.setFont('Helvetica-Bold', 9)
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        
        address_y = doc.height + doc.topMargin + 0.55*inch
        canvas_obj.drawString(doc.leftMargin, address_y, COMPANY_INFO['address_line1'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.18*inch, COMPANY_INFO['address_line2'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.36*inch, COMPANY_INFO['address_line3'])
        
        # Draw line under header
        canvas_obj.setStrokeColor(colors.HexColor('#1a237e'))
        canvas_obj.setLineWidth(1)
        line_y = doc.height + doc.topMargin - 0.05*inch
        canvas_obj.line(doc.leftMargin, line_y, 
                       doc.width + doc.leftMargin, line_y)
        
        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.gray)
        
        # Left footer - page number
        canvas_obj.drawString(doc.leftMargin, 0.5*inch, f"Page {doc.page}")
        
        # Center footer - document info
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas_obj.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, doc_info)
        
        # Right footer - date
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas_obj.drawRightString(doc.width + doc.leftMargin, 0.5*inch, date_str)
        
        # Draw line above footer
        canvas_obj.setStrokeColor(colors.lightgrey)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(doc.leftMargin, 0.7*inch, doc.width + doc.leftMargin, 0.7*inch)
        
        canvas_obj.restoreState()
    
    def _draw_logo_placeholder(self, canvas_obj, doc):
        """Draw logo placeholder text"""
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        canvas_obj.setFont('Helvetica-Bold', 14)
        canvas_obj.drawRightString(doc.width + doc.leftMargin - 0.2*inch, 
                                  doc.height + doc.topMargin + 0.5*inch, "MCN")
        canvas_obj.setFont('Helvetica-Bold', 9)
        canvas_obj.drawRightString(doc.width + doc.leftMargin - 0.2*inch, 
                                  doc.height + doc.topMargin + 0.3*inch, "LOGO")
    
    def _add_background_watermark(self, canvas_obj, doc):
        """Add logo as background watermark"""
        canvas_obj.saveState()
        
        # Only add watermark if logo is available
        if self.logo_image and self.logo_bytes:
            try:
                # Set transparency
                canvas_obj.setFillAlpha(0.08)
                
                # Reset logo stream position
                self.logo_image.seek(0)
                
                # Calculate position for centered watermark
                center_x = doc.width/2 + doc.leftMargin
                center_y = doc.height/2 + doc.topMargin
                
                # Draw logo watermark
                logo_width = 3.5 * inch
                logo_height = 1.75 * inch
                logo_x = center_x - logo_width/2
                logo_y = center_y - logo_height/2
                
                canvas_obj.drawImage(ImageReader(self.logo_image), logo_x, logo_y, 
                                   width=logo_width, height=logo_height, 
                                   mask='auto', preserveAspectRatio=True)
                logger.info("✅ Logo watermark added to PDF")
            except Exception as e:
                logger.warning(f"Could not draw watermark: {e}")
                # Fallback to text watermark
                self._draw_text_watermark(canvas_obj, doc)
        else:
            # Draw text watermark
            self._draw_text_watermark(canvas_obj, doc)
        
        canvas_obj.restoreState()
    
    def _draw_text_watermark(self, canvas_obj, doc):
        """Draw text watermark"""
        canvas_obj.setFillAlpha(0.1)
        
        # Calculate position for centered watermark
        center_x = doc.width/2 + doc.leftMargin
        center_y = doc.height/2 + doc.topMargin
        
        # Rotate the watermark
        canvas_obj.translate(center_x, center_y)
        canvas_obj.rotate(45)
        
        # Draw MCN text as watermark
        canvas_obj.setFont('Helvetica-Bold', 52)
        canvas_obj.setFillColor(colors.lightgrey)
        canvas_obj.drawCentredString(0, 0, "MCN")
        
        canvas_obj.setFont('Helvetica-Bold', 26)
        canvas_obj.drawCentredString(0, -40, "Marshal Core of Nigeria")
    
    def _format_date(self, date_value):
        """Format date for display"""
        if not date_value:
            return "N/A"
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime("%d %B, %Y")
        
        if isinstance(date_value, str):
            try:
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]:
                    try:
                        parsed_date = datetime.strptime(date_value, fmt)
                        return parsed_date.strftime("%d %B, %Y")
                    except:
                        continue
            except:
                pass
        
        return str(date_value)
    
    def _format_reason(self, reason_code: str) -> str:
        """Convert reason code to human-readable text"""
        reason_map = {
            'seeking_employment': 'Seeking Employment & Work',
            'skill_acquisition': 'Skill Acquisition & Handwork Training',
            'armed_forces': 'Armed Forces Preparation',
            'personal_development': 'Personal Development & Discipline',
            'ict_knowledge': 'ICT Knowledge & Basic Computer Skills',
            'security_association': 'Security Association & Legal Protection',
            'tech_career': 'Tech Career Pathway (Full SXTM Training)',
            'networking': 'Networking & Professional Status Enhancement',
            'security_awareness': 'Security Awareness & Risk Management',
            'business_protection': 'Business Protection & Organizational Backup'
        }
        return reason_map.get(reason_code, reason_code.replace('_', ' ').title())
    
    # ==================== EXISTING OFFICER METHODS (KEEP AS IS) ====================
    
    def generate_terms_conditions(self, officer_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Terms & Conditions PDF for an officer
        """
        try:
            logger.info(f"Generating Terms & Conditions PDF for user: {user_id}")
            
            # Generate filename
            filename = self._generate_filename(user_id, "terms")
            filepath, relative_path = self._save_pdf("terms", filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            # Story (content) container
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=18,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=24,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                leftIndent=0,
                fontName='Helvetica-Bold'
            )
            
            heading2_style = ParagraphStyle(
                'Heading2',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#3949ab'),
                spaceBefore=10,
                spaceAfter=4,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalJustified',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'
            )
            
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold'
            )
            
            warning_style = ParagraphStyle(
                'WarningStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.red,
                fontSize=10
            )
            
            nin_bold_style = ParagraphStyle(
                'NINBoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.black
            )
            
            # Title
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            # Document Information
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-NG-{user_id}-{datetime.now().strftime('%Y%m%d')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Effective Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # IMPORTANT NOTICE
            story.append(Paragraph(
                "<b>IMPORTANT NOTICE:</b> This is a legally binding agreement between "
                "Marshal Core of Nigeria (hereinafter referred to as 'the Organization') "
                "and the Officer/Applicant (hereinafter referred to as 'the Officer'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            # 1. PARTIES TO THE AGREEMENT
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            
            # 1.1 The Organization
            story.append(Paragraph(
                f"<b>1.1 The Organization:</b> Marshal Core of Nigeria, a voluntary organization "
                "duly registered under ministry of humanitarian affairs with certificate number: "
                f"<b>{COMPANY_INFO['certificate_number']}</b>, and incorporated under the "
                "COMPANIES AND ALLIED MATTERS ACT 2020 Federal Republic of Nigeria with "
                f"RC Number: <b>{COMPANY_INFO['rc_number']}</b>, having its principal office at",
                normal_style
            ))
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            
            # 1.2 The Officer
            story.append(Paragraph(
                f"<b>1.2 The Officer:</b> {officer_data.get('full_name', 'CORE MARSHAL')}, "
                "with National Identification Number: ",
                normal_style
            ))
            # NIN in bold
            story.append(Paragraph(
                f"<b>{officer_data.get('nin_number', '{Number}')}</b>, ",
                nin_bold_style
            ))
            story.append(Paragraph(
                "residing at",
                normal_style
            ))
            officer_address = officer_data.get('residential_address', 'Address not provided')
            story.append(Paragraph(
                f"{officer_address}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 2. APPOINTMENT AND DUTIES
            story.append(Paragraph("2. APPOINTMENT AND DUTIES", heading1_style))
            
            # 2.1 Appointment
            story.append(Paragraph(
                "<b>2.1 Appointment:</b> The Officer is hereby appointed as Director in the "
                "None department, subject to the terms and conditions herein.",
                normal_style
            ))
            
            # 2.2 Duties
            story.append(Paragraph(
                "<b>2.2 Duties:</b> The Officer shall perform all duties assigned by the organization "
                "including but not limited to security services, patrol duties, client protection, "
                "and any other lawful instructions from authorized supervisors.",
                normal_style
            ))
            
            # 2.3 Code of Conduct
            story.append(Paragraph(
                "<b>2.3 Code of Conduct:</b> The Officer shall at all times maintain the highest "
                "standards of professionalism, integrity, and discipline as outlined in the "
                "organization Code of Conduct Manual.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 3. TERM AND TERMINATION
            story.append(Paragraph("3. TERM AND TERMINATION", heading1_style))
            
            # 3.1 Term
            story.append(Paragraph(
                '<b>3.1 Term:</b> This agreement shall commence on "Date" and continue until '
                "terminated in accordance with these terms.",
                normal_style
            ))
            
            # 3.2 Termination for Cause
            story.append(Paragraph(
                "<b>3.2 Termination for Cause:</b> The organization may immediately terminate this agreement for:",
                normal_style
            ))
            
            # Termination reasons
            termination_reasons = [
                "Criminal conduct or conviction",
                "Gross misconduct or negligence",
                "Violation of organization policies",
                "Unauthorized disclosure of confidential information",
                "Failure to perform assigned duties",
                "Absence without leave for more than 2 consecutive months"
            ]
            
            for reason in termination_reasons:
                story.append(Paragraph(f"• {reason}", normal_style))
            
            story.append(Spacer(1, 6))
            
            # 4. LEGAL CONSEQUENCES OF MISCONDUCT
            story.append(Paragraph("4. LEGAL CONSEQUENCES OF MISCONDUCT", heading1_style))
            
            # Page header from document
            story.append(Paragraph(
                f'Page 1 Terms & Conditions "{datetime.now().strftime("%d/%m/%Y %H:%M")}"',
                ParagraphStyle(
                    'PageHeader',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_RIGHT
                )
            ))
            
            story.append(Paragraph(
                "Marshal Core of Nigeria",
                ParagraphStyle(
                    'CompanyHeader',
                    parent=normal_style,
                    fontSize=9,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
            ))
            
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                ParagraphStyle(
                    'AddressHeader',
                    parent=normal_style,
                    fontSize=8,
                    alignment=TA_CENTER
                )
            ))
            
            story.append(Spacer(1, 6))
            
            # WARNING section
            story.append(Paragraph("WARNING:", warning_style))
            story.append(Paragraph(
                "Any breach of these terms may result in:",
                normal_style
            ))
            
            # Legal consequences
            legal_consequences = [
                "Immediate termination of employment/voluntary service",
                "Forfeiture of all benefits and entitlements",
                "Returning/seizure of all marshal property in your possession including the marshal property you bought by yourself. Read this most carefully",
                "Legal prosecution in accordance with Nigerian laws",
                "Civil liability for damages caused",
                "Criminal charges where applicable",
                "Court proceedings and possible imprisonment",
                "Financial penalties and compensation payments"
            ]
            
            for consequence in legal_consequences:
                if "including the marshal property you bought by yourself" in consequence:
                    story.append(Paragraph(f"• {consequence}", warning_style))
                else:
                    story.append(Paragraph(f"• {consequence}", normal_style))
            
            story.append(Spacer(1, 12))
            
            # 5. CONFIDENTIALITY
            story.append(Paragraph("5. CONFIDENTIALITY", heading1_style))
            
            # 5.1 Confidential Information
            story.append(Paragraph(
                "<b>5.1 Confidential Information:</b> The Officer shall not disclose any confidential "
                "information about the Organization, its clients, or operations during or after employment.",
                normal_style
            ))
            
            # 5.2 Non-Disclosure
            story.append(Paragraph(
                "<b>5.2 Non-Disclosure:</b> This obligation continues for 10 years after termination of employment.",
                normal_style
            ))
            
            story.append(Spacer(1, 12))
            
            # Page break for signature section
            story.append(PageBreak())
            
            # ACCEPTANCE AND SIGNATURE SECTION
            story.append(Paragraph("ACCEPTANCE AND SIGNATURE", heading1_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph(
                f'I, "{officer_data.get("full_name", "Name")}" hereby acknowledge that I have read, '
                "understood, and agree to be bound by all the terms and conditions stated in this document.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Officer Signature
            story.append(Paragraph("<b>Signature of Officer:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 48))
            
            # Organization Signature
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            story.append(Spacer(1, 12))
            
            # Build PDF with custom canvas
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Terms & Conditions PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Terms & Conditions PDF: {str(e)}")
    
    def generate_application_form(self, applicant_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Application Form PDF for an applicant/officer
        """
        try:
            logger.info(f"Generating Application Form PDF for user: {user_id}")
            
            # Generate filename
            filename = self._generate_filename(user_id, "application")
            filepath, relative_path = self._save_pdf("applications", filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            # Story (content) container
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=16,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=12,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=12,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                leftIndent=0,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                fontName='Helvetica'
            )
            
            field_label_style = ParagraphStyle(
                'FieldLabel',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1a237e')
            )
            
            nin_bold_style = ParagraphStyle(
                'NINBoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.black
            )
            
            # PASSPORT PHOTO SECTION
            passport_path = applicant_data.get('passport_path') or applicant_data.get('passport_photo')
            passport_available = False
            
            if passport_path:
                absolute_path = None
                
                # Check if it's already an absolute path
                if os.path.isabs(passport_path):
                    absolute_path = passport_path
                else:
                    # Try relative paths
                    possible_paths = [
                        passport_path,
                        os.path.join(UPLOADS_DIR, passport_path),
                        os.path.join(STATIC_DIR, passport_path),
                        os.path.join(BASE_DIR, passport_path),
                    ]
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            absolute_path = path
                            break
                
                if absolute_path and os.path.exists(absolute_path):
                    try:
                        # Create a table for passport photo layout
                        passport_data = [
                            [Paragraph("<b>PASSPORT PHOTO</b>", field_label_style)],
                            [Image(absolute_path, width=1.5*inch, height=2*inch)]
                        ]
                        
                        passport_table = Table(passport_data, colWidths=[2*inch])
                        passport_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ]))
                        
                        story.append(passport_table)
                        story.append(Spacer(1, 12))
                        passport_available = True
                        logger.info(f"✅ Passport photo added to application form from: {absolute_path}")
                        
                    except Exception as e:
                        logger.warning(f"Could not add passport photo to PDF: {e}")
                        story.append(Paragraph("<b>Passport Photo:</b> [File exists but could not be embedded]", normal_style))
                        story.append(Spacer(1, 12))
                else:
                    logger.warning(f"Passport path not found: {passport_path}")
                    story.append(Paragraph("<b>Passport Photo:</b> [Not Available]", normal_style))
                    story.append(Spacer(1, 12))
            else:
                story.append(Paragraph("<b>Passport Photo:</b> [Not Uploaded]", normal_style))
                story.append(Spacer(1, 12))
            
            # Title
            story.append(Paragraph("MARSHAL CORE OF NIGERIA", title_style))
            story.append(Paragraph("OFFICER APPLICATION FORM", title_style))
            story.append(Spacer(1, 12))
            
            # Organization Information
            story.append(Paragraph(
                f"<b>Organization:</b> Marshal Core of Nigeria (Voluntary Organization)",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Certificate Number:</b> {COMPANY_INFO['certificate_number']}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>RC Number:</b> {COMPANY_INFO['rc_number']}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Address:</b> {COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # Application Information
            story.append(Paragraph(
                f"<b>Application ID:</b> {applicant_data.get('unique_id', user_id)}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Submission Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # Personal Information Section
            story.append(Paragraph("PERSONAL INFORMATION", heading1_style))
            
            # Full Name
            story.append(Paragraph(f"<b>Full Name:</b> {applicant_data.get('full_name', 'N/A')}", normal_style))
            story.append(Spacer(1, 4))
            
            # Officer ID
            story.append(Paragraph(f"<b>Officer ID:</b> {applicant_data.get('unique_id', applicant_data.get('officer_id', 'N/A'))}", normal_style))
            story.append(Spacer(1, 4))
            
            # NIN Number in BOLD
            story.append(Paragraph("<b>NIN Number:</b> ", normal_style))
            story.append(Paragraph(f"<b>{applicant_data.get('nin_number', 'N/A')}</b>", nin_bold_style))
            story.append(Spacer(1, 4))
            
            # Other personal info
            personal_info_fields = [
                ("Date of Birth", self._format_date(applicant_data.get('date_of_birth'))),
                ("Gender", applicant_data.get('gender', 'N/A')),
                ("Marital Status", applicant_data.get('marital_status', 'N/A')),
                ("Nationality", applicant_data.get('nationality', 'N/A')),
                ("Religion", applicant_data.get('religion', 'N/A')),
                ("Place of Birth", applicant_data.get('place_of_birth', 'N/A')),
            ]
            
            for label, value in personal_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Contact Information
            story.append(Paragraph("CONTACT INFORMATION", heading1_style))
            
            officer_address = applicant_data.get('residential_address', 'Address not provided')
            contact_info_fields = [
                ("Email Address", applicant_data.get('email', 'N/A')),
                ("Phone Number", applicant_data.get('phone', applicant_data.get('mobile_number', 'N/A'))),
                ("Residential Address", officer_address),
                ("State of Residence", applicant_data.get('state_of_residence', 'N/A')),
                ("LGA of Residence", applicant_data.get('local_government_residence', 'N/A')),
                ("Country of Residence", applicant_data.get('country_of_residence', 'N/A')),
            ]
            
            for label, value in contact_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Origin Information
            story.append(Paragraph("ORIGIN INFORMATION", heading1_style))
            
            origin_info_fields = [
                ("State of Origin", applicant_data.get('state_of_origin', 'N/A')),
                ("LGA of Origin", applicant_data.get('local_government_origin', 'N/A')),
            ]
            
            for label, value in origin_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Professional Information
            story.append(Paragraph("PROFESSIONAL INFORMATION", heading1_style))
            
            professional_info_fields = [
                ("Rank", applicant_data.get('rank', 'CORE MARSHAL')),
                ("Position", "Director in None department"),
                ("Years of Service", applicant_data.get('years_of_service', 'N/A')),
                ("Service Number", applicant_data.get('service_number', 'N/A')),
                ("Additional Skills", applicant_data.get('additional_skills', 'N/A')),
            ]
            
            for label, value in professional_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Financial Information
            story.append(Paragraph("FINANCIAL INFORMATION", heading1_style))
            
            financial_info_fields = [
                ("Bank Name", applicant_data.get('bank_name', 'N/A')),
                ("Account Number", applicant_data.get('account_number', 'N/A')),
            ]
            
            for label, value in financial_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Service Dates
            story.append(Paragraph("SERVICE DATES", heading1_style))
            
            service_date_fields = [
                ("Date of Enlistment", self._format_date(applicant_data.get('date_of_enlistment'))),
                ("Date of Promotion", self._format_date(applicant_data.get('date_of_promotion'))),
            ]
            
            for label, value in service_date_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Documents Submitted
            story.append(Paragraph("DOCUMENTS SUBMITTED", heading1_style))
            
            documents_info_fields = [
                ("Passport Photo", "✓ Submitted" if passport_available else "✗ Not Submitted"),
                ("NIN Slip", "✓ Submitted" if applicant_data.get('nin_number') else "✗ Not Submitted"),
            ]
            
            for label, value in documents_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 24))
            
            # Declaration
            story.append(Paragraph("DECLARATION", heading1_style))
            story.append(Paragraph(
                "I hereby declare that all information provided in this application is true and correct "
                "to the best of my knowledge. I understand that any false information may lead to "
                "disqualification or termination of appointment as per the Terms and Conditions.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Signature lines
            story.append(Paragraph("<b>Signature of Officer:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}", field_label_style))
            story.append(Spacer(1, 48))
            
            # Organization signature
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", field_label_style))
            story.append(Spacer(1, 12))
            
            # Footer note
            story.append(Paragraph(
                "This document is electronically generated by Marshal Core of Nigeria. "
                "For official use only.",
                ParagraphStyle(
                    'FooterNote',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_CENTER
                )
            ))
            
            # Build PDF with custom canvas
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Application Form PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Application Form PDF: {str(e)}")
    
    # ==================== NEW APPLICANT METHODS ====================
    
    def generate_applicant_terms_pdf(self, applicant_data: Dict[str, Any], applicant_id: str, tier: str) -> str:
        """Generate Terms & Conditions PDF for NEW APPLICANT"""
        try:
            logger.info(f"Generating Applicant Terms PDF for: {applicant_id} (Tier: {tier})")
            
            filename = self._generate_filename(applicant_id, "applicant_terms", tier)
            filepath, relative_path = self._save_pdf("applicants", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Title'],
                fontSize=18,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=24,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'
            )
            
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold'
            )
            
            # Title
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            # Document info
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-APP-{applicant_id}-{datetime.now().strftime('%Y%m%d')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Effective Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Applicant Tier:</b> {tier.upper()}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # IMPORTANT NOTICE
            story.append(Paragraph(
                "<b>IMPORTANT NOTICE:</b> This is a legally binding agreement between "
                "Marshal Core of Nigeria (hereinafter referred to as 'the Organization') "
                "and the Applicant (hereinafter referred to as 'the Applicant'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            # 1. PARTIES TO THE AGREEMENT
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            
            # 1.1 The Organization
            story.append(Paragraph(
                f"<b>1.1 The Organization:</b> Marshal Core of Nigeria, a voluntary organization "
                "duly registered under ministry of humanitarian affairs with certificate number: "
                f"<b>{COMPANY_INFO['certificate_number']}</b>, and incorporated under the "
                "COMPANIES AND ALLIED MATTERS ACT 2020 Federal Republic of Nigeria with "
                f"RC Number: <b>{COMPANY_INFO['rc_number']}</b>, having its principal office at",
                normal_style
            ))
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            
            # 1.2 The Applicant
            story.append(Paragraph(
                f"<b>1.2 The Applicant:</b> {applicant_data.get('full_name', 'Applicant')}",
                normal_style
            ))
            
            if applicant_data.get('nin_number'):
                story.append(Paragraph(
                    f"<b>National Identification Number:</b> {applicant_data.get('nin_number')}",
                    normal_style
                ))
            
            story.append(Paragraph(
                f"<b>Email Address:</b> {applicant_data.get('email', 'Not provided')}",
                normal_style
            ))
            
            if applicant_data.get('phone_number'):
                story.append(Paragraph(
                    f"<b>Phone Number:</b> {applicant_data.get('phone_number')}",
                    normal_style
            ))
            
            story.append(Spacer(1, 12))
            
            # 2. PURPOSE OF AGREEMENT
            story.append(Paragraph("2. PURPOSE OF AGREEMENT", heading1_style))
            story.append(Paragraph(
                "This agreement outlines the terms and conditions governing the "
                "applicant's participation in the Marshal Core of Nigeria program. "
                "The applicant agrees to abide by all rules, regulations, and "
                "instructions provided by the organization.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 3. MEMBERSHIP BENEFITS
            story.append(Paragraph("3. MEMBERSHIP BENEFITS", heading1_style))
            story.append(Paragraph(
                "3.1 The organization shall provide the following benefits:",
                bold_style
            ))
            
            benefits = [
                "Comprehensive security training",
                "Skill acquisition programs",
                "Networking opportunities",
                "Professional development",
                "Career placement assistance",
                "Legal protection and security association benefits"
            ]
            
            for benefit in benefits:
                story.append(Paragraph(f"• {benefit}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # 4. OBLIGATIONS OF THE APPLICANT
            story.append(Paragraph("4. OBLIGATIONS OF THE APPLICANT", heading1_style))
            
            obligations = [
                "Adhere to all training schedules and requirements",
                "Maintain professional conduct at all times",
                "Complete all assigned tasks and responsibilities",
                "Respect the authority of training officers",
                "Maintain confidentiality of organizational information",
                "Participate actively in all programs and activities"
            ]
            
            for obligation in obligations:
                story.append(Paragraph(f"• {obligation}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # 5. FEES AND PAYMENTS
            story.append(Paragraph("5. FEES AND PAYMENTS", heading1_style))
            
            if tier.lower() == "vip":
                fee_info = [
                    ("Application Fee", "₦25,900 (Non-refundable)"),
                    ("Uniform Package", "₦200,000 (Payable in installments)"),
                    ("VIP Benefits", "Full SXTM training, executive security association, advanced protocols")
                ]
            else:
                fee_info = [
                    ("Application Fee", "₦5,180 (Non-refundable)"),
                    ("Uniform Package", "₦95,000 (Payable in installments)"),
                    ("Training Benefits", "Comprehensive security training and job placement")
                ]
            
            for fee_name, fee_amount in fee_info:
                story.append(Paragraph(f"<b>{fee_name}:</b> {fee_amount}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # 6. TERMINATION
            story.append(Paragraph("6. TERMINATION", heading1_style))
            story.append(Paragraph(
                "6.1 The organization reserves the right to terminate this agreement "
                "if the applicant violates any terms or engages in misconduct.",
                normal_style
            ))
            story.append(Paragraph(
                "6.2 The applicant may terminate this agreement with written notice, "
                "but application fees are non-refundable.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 7. CONFIDENTIALITY
            story.append(Paragraph("7. CONFIDENTIALITY", heading1_style))
            story.append(Paragraph(
                "The applicant agrees to maintain the confidentiality of all "
                "organizational information, training materials, and internal "
                "procedures.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 8. GOVERNING LAW
            story.append(Paragraph("8. GOVERNING LAW", heading1_style))
            story.append(Paragraph(
                "This agreement shall be governed by and construed in accordance "
                "with the laws of the Federal Republic of Nigeria.",
                normal_style
            ))
            
            story.append(PageBreak())
            
            # SIGNATURE PAGE
            story.append(Paragraph("ACCEPTANCE AND SIGNATURE", title_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph(
                "I, the undersigned Applicant, hereby acknowledge that I have "
                "read, understood, and agree to all the terms and conditions "
                "outlined in this agreement.",
                normal_style
            ))
            story.append(Spacer(1, 36))
            
            # Applicant signature
            story.append(Paragraph(f"<b>Name of Applicant:</b> {applicant_data.get('full_name', '')}", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("<b>Signature of Applicant</b>", bold_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d %B, %Y')}", bold_style))
            
            story.append(Spacer(1, 72))
            
            # Organization signature
            story.append(Paragraph("<b>FOR MARSHAL CORE OF NIGERIA:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("<b>OSEOBOH JOSHUA EROMONSELE</b>", bold_style))
            story.append(Paragraph("<b>Director General</b>", bold_style))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d %B, %Y')}", bold_style))
            
            story.append(Spacer(1, 48))
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            story.append(Paragraph("[ORGANIZATION SEAL]", normal_style))
            
            # Build PDF
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"✅ Applicant Terms PDF generated: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"❌ Failed to generate Applicant Terms PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Applicant Terms PDF: {str(e)}")
    
    def generate_applicant_application_pdf(self, applicant_data: Dict[str, Any], applicant_id: str, tier: str, 
                                         payment_data: Dict[str, Any] = None) -> str:
        """Generate Application Form PDF for NEW APPLICANT with passport photo and payment details"""
        try:
            logger.info(f"Generating Applicant Application PDF for: {applicant_id} (Tier: {tier})")
            
            filename = self._generate_filename(applicant_id, "applicant_application", tier)
            filepath, relative_path = self._save_pdf("applicants", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Title'],
                fontSize=16,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=12,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=12,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                fontName='Helvetica'
            )
            
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1a237e')
            )
            
            # ✅ PASSPORT PHOTO SECTION
            passport_embedded = False
            passport_table = None
            
            passport_path = applicant_data.get('passport_photo')
            if passport_path:
                passport_img = self._prepare_passport_image(passport_path)
                if passport_img:
                    passport_data = [
                        [Paragraph("<b>PASSPORT PHOTOGRAPH</b>", bold_style)],
                        [passport_img],
                        [Paragraph("<i>Required for identification</i>", 
                                 ParagraphStyle('PhotoNote', parent=normal_style, fontSize=8, 
                                              textColor=colors.gray, alignment=TA_CENTER))]
                    ]
                    
                    passport_table = Table(passport_data, colWidths=[2*inch])
                    passport_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1a237e')),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e3f2fd')),
                        ('PADDING', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ]))
                    passport_embedded = True
                    logger.info("✅ Passport photo embedded in Applicant PDF")
            
            # Title
            story.append(Paragraph("MARSHAL CORE OF NIGERIA", title_style))
            story.append(Paragraph("APPLICANT REGISTRATION FORM", title_style))
            story.append(Spacer(1, 12))
            
            # Application Information
            story.append(Paragraph("APPLICATION INFORMATION", heading1_style))
            
            app_info = [
                ("Application ID", applicant_id),
                ("Application Tier", tier.upper()),
                ("Submission Date", datetime.now().strftime("%d %B %Y")),
            ]
            
            for label, value in app_info:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Create two-column layout with passport photo
            if passport_table and passport_embedded:
                personal_info = []
                personal_info.append([Paragraph("PERSONAL INFORMATION", heading1_style), ""])
                
                personal_fields = [
                    ("Full Name", applicant_data.get('full_name')),
                    ("Email Address", applicant_data.get('email')),
                    ("Phone Number", applicant_data.get('phone_number')),
                    ("Date of Birth", self._format_date(applicant_data.get('date_of_birth'))),
                    ("NIN Number", applicant_data.get('nin_number', 'Optional - To be provided later')),
                ]
                
                for label, value in personal_fields:
                    personal_info.append([
                        Paragraph(f"<b>{label}:</b> {value}", normal_style),
                        ""
                    ])
                
                personal_table = Table(personal_info, colWidths=[4*inch, 0.5*inch])
                
                two_col_data = [
                    [personal_table, passport_table]
                ]
                
                two_col_table = Table(two_col_data, colWidths=[4.5*inch, 2.5*inch])
                two_col_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                
                story.append(two_col_table)
            else:
                story.append(Paragraph("PERSONAL INFORMATION", heading1_style))
                
                personal_fields = [
                    ("Full Name", applicant_data.get('full_name')),
                    ("Email Address", applicant_data.get('email')),
                    ("Phone Number", applicant_data.get('phone_number')),
                    ("Date of Birth", self._format_date(applicant_data.get('date_of_birth'))),
                    ("NIN Number", applicant_data.get('nin_number', 'Optional - To be provided later')),
                ]
                
                for label, value in personal_fields:
                    story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                    story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Contact Information
            story.append(Paragraph("CONTACT INFORMATION", heading1_style))
            
            contact_fields = [
                ("State of Residence", applicant_data.get('state_of_residence')),
                ("Local Government Area", applicant_data.get('lga')),
                ("Residential Address", applicant_data.get('address')),
            ]
            
            for label, value in contact_fields:
                if value:
                    story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                    story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Reasons for Joining
            story.append(Paragraph("REASONS FOR JOINING", heading1_style))
            
            selected_reasons = applicant_data.get('selected_reasons', [])
            if isinstance(selected_reasons, str):
                try:
                    import json
                    selected_reasons = json.loads(selected_reasons)
                except:
                    selected_reasons = []
            
            if selected_reasons:
                for reason in selected_reasons:
                    story.append(Paragraph(f"• {self._format_reason(reason)}", normal_style))
                    story.append(Spacer(1, 2))
            else:
                story.append(Paragraph("No reasons specified", normal_style))
            
            story.append(Spacer(1, 12))
            
            # Additional Details
            additional_details = applicant_data.get('additional_details')
            if additional_details:
                story.append(Paragraph("ADDITIONAL DETAILS", heading1_style))
                story.append(Paragraph(additional_details, normal_style))
                story.append(Spacer(1, 12))
            
            # ✅ PAYMENT RECEIPT SECTION
            story.append(Paragraph("PAYMENT CONFIRMATION", heading1_style))
            
            if payment_data:
                payment_info = [
                    ["Payment Status:", "✅ COMPLETED"],
                    ["Application Fee Paid:", f"₦{payment_data.get('amount', 0):,}"],
                    ["Payment Reference:", payment_data.get('reference', 'N/A')],
                    ["Payment Date:", self._format_date(payment_data.get('date')) or datetime.now().strftime("%d %B, %Y")],
                    ["Payment Method:", "Online Payment (Paystack)"]
                ]
                
                payment_table = Table(payment_info, colWidths=[2.5*inch, 3.5*inch])
                payment_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f5e9')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#4CAF50')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ('PADDING', (0, 0), (-1, -1), 8),
                ]))
                
                story.append(payment_table)
                story.append(Spacer(1, 4))
                story.append(Paragraph(
                    "<i>This confirms successful payment of application fee. Keep this receipt for your records.</i>",
                    ParagraphStyle('ReceiptNote', parent=normal_style, fontSize=9, textColor=colors.gray)
                ))
            else:
                story.append(Paragraph(
                    "<i>Payment confirmation will be updated once payment is verified.</i>",
                    ParagraphStyle('ReceiptNote', parent=normal_style, fontSize=9, textColor=colors.gray)
                ))
            
            story.append(Spacer(1, 24))
            
            # Documents Section
            story.append(Paragraph("DOCUMENTS SUBMITTED", heading1_style))
            
            docs_info = [
                ("Passport Photograph", "✓ Submitted" if passport_embedded else "✗ Not Submitted"),
                ("NIN Slip", "✓ Submitted" if applicant_data.get('nin_number') else "✗ Optional"),
                ("Application Form", "✓ Completed"),
                ("Payment Receipt", "✓ Included" if payment_data else "Pending"),
            ]
            
            for label, status in docs_info:
                color = colors.HexColor('#2e7d32') if '✓' in status else colors.gray
                story.append(Paragraph(
                    f"<b>{label}:</b> <font color='{color}'>{status}</font>", 
                    normal_style
                ))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 24))
            
            # Declaration
            story.append(Paragraph("DECLARATION", heading1_style))
            story.append(Paragraph(
                "I hereby declare that all information provided in this application is true and correct "
                "to the best of my knowledge. I understand that any false information may lead to "
                "disqualification or termination of appointment as per the Terms and Conditions.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Signature lines
            story.append(Paragraph("<b>Signature of Applicant:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}", bold_style))
            story.append(Spacer(1, 48))
            
            # Organization signature
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            
            story.append(Spacer(1, 24))
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            
            story.append(Spacer(1, 12))
            
            # Footer note
            story.append(Paragraph(
                "This document is electronically generated by Marshal Core of Nigeria. "
                "For official use only.",
                ParagraphStyle(
                    'FooterNote',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_CENTER
                )
            ))
            
            # Build PDF with watermark
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"✅ Applicant Application PDF generated: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"❌ Failed to generate Applicant Application PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Applicant Application PDF: {str(e)}")
    
    def generate_applicant_pdfs(self, applicant_data: Dict[str, Any], applicant_id: str, tier: str,
                              payment_data: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Generate all PDFs for a new applicant
        Returns paths to all generated PDFs
        """
        try:
            logger.info(f"Generating all PDFs for applicant: {applicant_id} (Tier: {tier})")
            
            # Generate Terms PDF
            terms_pdf_path = self.generate_applicant_terms_pdf(applicant_data, applicant_id, tier)
            
            # Generate Application PDF with passport and payment
            app_pdf_path = self.generate_applicant_application_pdf(applicant_data, applicant_id, tier, payment_data)
            
            # Guarantor form path (static file)
            guarantor_pdf_path = "static/guarantor-form.pdf"
            
            return {
                "terms_pdf_path": terms_pdf_path,
                "application_pdf_path": app_pdf_path,
                "guarantor_pdf_path": guarantor_pdf_path,
                "generated_at": datetime.now().isoformat(),
                "applicant_id": applicant_id,
                "tier": tier
            }
            
        except Exception as e:
            logger.error(f"Failed to generate applicant PDFs: {str(e)}")
            raise PDFGenerationError(f"Failed to generate applicant PDFs: {str(e)}")
    
    def generate_both_pdfs(self, user_data: Dict[str, Any], user_id: str, user_type: str = "officer") -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        Now supports both officer and applicant types
        """
        try:
            logger.info(f"Generating both PDFs for {user_type}: {user_id}")
            
            if user_type.lower() == "applicant":
                # For applicants, we need tier information
                tier = user_data.get('application_tier', 'regular')
                return self.generate_applicant_pdfs(user_data, user_id, tier)
            else:
                # For officers (existing code)
                terms_pdf_path = self.generate_terms_conditions(user_data, user_id)
                app_pdf_path = self.generate_application_form(user_data, user_id)
                
                return {
                    "terms_pdf_path": terms_pdf_path,
                    "application_pdf_path": app_pdf_path,
                    "generated_at": datetime.now().isoformat(),
                    "user_id": user_id,
                    "user_type": user_type
                }
            
        except Exception as e:
            logger.error(f"Failed to generate both PDFs: {str(e)}")
            raise PDFGenerationError(f"Failed to generate both PDFs: {str(e)}")

# Singleton instance for easy import
pdf_generator = PDFGenerator()