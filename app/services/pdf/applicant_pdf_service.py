# app/services/pdf/applicant_pdf_service.py
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
PDFS_DIR = STATIC_DIR / "pdfs"
APPLICANTS_DIR = PDFS_DIR / "applicants"
LOGO_DIR = STATIC_DIR / "images"
UPLOADS_DIR = STATIC_DIR / "uploads"

# Ensure directories exist
for directory in [APPLICANTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Company information
COMPANY_INFO = {
    "name": "Marshal Core of Nigeria",
    "certificate_number": "YA/CLB/10100",
    "rc_number": "8405988",
    "address_line1": "KM. 3, MARSHAL CORE OF NIGERIA NATIONAL HEADQUARTERS",
    "address_line2": "ABUMWENRENRE COMMUNITY, EKIADOLOR/AGEKPANU ROAD",
    "address_line3": "BENIN CITY, EDO STATE, NIGERIA",
    "phone": "+234 9137 428 031",
    "email": "info@marshalcoreofnigeria.ng",
    "website": "www.marshalcoreofnigeria.ng",
    "logo_path": str(LOGO_DIR / "logo.png")
}

class ApplicantPDFGenerationError(Exception):
    """Custom exception for Applicant PDF generation errors"""
    pass

class ApplicantPDFService:
    """PDF generation service for NEW APPLICANTS only (not existing officers)"""
    
    def __init__(self):
        """Initialize Applicant PDF generator"""
        logger.info("Initializing Applicant PDF Service")
        self.logo_image = None
        self.logo_bytes = None
        self._load_logo()
    
    def _load_logo(self):
        """Load company logo"""
        try:
            logo_path = Path(COMPANY_INFO['logo_path'])
            
            if logo_path.exists():
                with open(logo_path, 'rb') as f:
                    self.logo_bytes = f.read()
                    self.logo_image = BytesIO(self.logo_bytes)
                logger.info("✅ Logo loaded successfully for Applicant PDF")
                return True
            
            # Try alternative locations
            possible_paths = [
                LOGO_DIR / "logo.png",
                STATIC_DIR / "logo.png",
                BASE_DIR / "static" / "images" / "logo.png",
                BASE_DIR / "static" / "logo.png",
                Path("/app/static/images/logo.png"),
            ]
            
            for path in possible_paths:
                if path.exists():
                    with open(path, 'rb') as f:
                        self.logo_bytes = f.read()
                        self.logo_image = BytesIO(self.logo_bytes)
                    logger.info(f"✅ Logo loaded from {path}")
                    return True
            
            logger.warning("⚠️ Logo file not found")
            return False
                
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")
            return False
    
    def _resolve_passport_path(self, passport_path: str) -> Optional[Path]:
        """Resolve absolute path for passport photo"""
        if not passport_path:
            return None
        
        try:
            # Check if it's already an absolute path
            if os.path.isabs(passport_path):
                path = Path(passport_path)
                if path.exists():
                    return path
            
            # Try relative paths
            possible_paths = [
                Path(passport_path),
                UPLOADS_DIR / passport_path,
                STATIC_DIR / passport_path,
                BASE_DIR / passport_path,
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"✅ Found passport photo at: {path}")
                    return path
            
            logger.warning(f"Passport photo not found: {passport_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving passport path: {e}")
            return None
    
    def _prepare_passport_image(self, passport_path: str, width=1.5*inch, height=2*inch) -> Optional[Image]:
        """Prepare passport image for PDF embedding - HIGH PRIORITY"""
        try:
            absolute_path = self._resolve_passport_path(passport_path)
            if not absolute_path:
                return None
            
            # Validate file size
            file_size = absolute_path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(f"Passport photo too large: {file_size} bytes")
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
            pil_img.save(img_bytes, format='JPEG', quality=90)  # Higher quality for passport
            img_bytes.seek(0)
            
            logger.info(f"✅ Passport photo prepared: {absolute_path}, size: {pil_img.size}")
            return Image(img_bytes, width=width, height=height)
            
        except Exception as e:
            logger.error(f"Error preparing passport image: {e}")
            return None
    
    def _generate_filename(self, user_id: str, document_type: str, tier: str = "") -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        tier_prefix = f"{tier}_" if tier else ""
        return f"{tier_prefix}{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, filename: str) -> Tuple[str, str]:
        """Get filepath for saving PDF"""
        file_path = APPLICANTS_DIR / filename
        relative_path = f"static/pdfs/applicants/{filename}"
        
        return str(file_path), relative_path
    
    def _create_header_footer(self, canvas_obj, doc, title="", is_terms=False):
        """Create header and footer for PDF pages - ENHANCED LOGO"""
        canvas_obj.saveState()
        
        # Add logo at top right - ENHANCED: Bigger and sharper
        if self.logo_image and self.logo_bytes:
            try:
                self.logo_image.seek(0)
                # ENHANCED LOGO SIZE: Bigger and sharper
                logo_width = 1.8 * inch  # Increased size
                logo_height = 0.9 * inch  # Increased size
                logo_x = doc.width + doc.leftMargin - logo_width - 0.1*inch
                logo_y = doc.height + doc.topMargin - 0.0*inch
                
                # Draw logo with higher quality
                canvas_obj.drawImage(ImageReader(self.logo_image), logo_x, logo_y,
                                   width=logo_width, height=logo_height,
                                   mask='auto', preserveAspectRatio=True)
                
                # Add subtle shadow/border for sharpness
                canvas_obj.setStrokeColor(colors.HexColor('#1a237e'))
                canvas_obj.setLineWidth(0.5)
                canvas_obj.rect(logo_x, logo_y, logo_width, logo_height)
                
            except Exception as e:
                logger.warning(f"Could not draw logo: {e}")
                # Fallback to text
                self._draw_logo_placeholder(canvas_obj, doc)
        else:
            self._draw_logo_placeholder(canvas_obj, doc)
        
        # Header text - ENHANCED: Bolder and clearer
        canvas_obj.setFont('Helvetica-Bold', 16)  # Increased size
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        canvas_obj.drawString(doc.leftMargin, doc.height + doc.topMargin + 0.9*inch, COMPANY_INFO['name'])
        
        # Address - ENHANCED: Clearer formatting
        canvas_obj.setFont('Helvetica-Bold', 9)
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        
        address_y = doc.height + doc.topMargin + 0.6*inch
        canvas_obj.drawString(doc.leftMargin, address_y, COMPANY_INFO['address_line1'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.2*inch, COMPANY_INFO['address_line2'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.4*inch, COMPANY_INFO['address_line3'])
        
        # Line under header - ENHANCED: Thicker and colored
        canvas_obj.setStrokeColor(colors.HexColor('#d32f2f'))  # Red color
        canvas_obj.setLineWidth(2)  # Thicker line
        line_y = doc.height + doc.topMargin - 0.05*inch
        canvas_obj.line(doc.leftMargin, line_y, doc.width + doc.leftMargin, line_y)
        
        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.gray)
        
        # Page number
        canvas_obj.drawString(doc.leftMargin, 0.5*inch, f"Page {doc.page}")
        
        # Document info
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas_obj.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, doc_info)
        
        # Date
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas_obj.drawRightString(doc.width + doc.leftMargin, 0.5*inch, date_str)
        
        # Line above footer
        canvas_obj.setStrokeColor(colors.lightgrey)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(doc.leftMargin, 0.7*inch, doc.width + doc.leftMargin, 0.7*inch)
        
        canvas_obj.restoreState()
    
    def _draw_logo_placeholder(self, canvas_obj, doc):
        """Draw logo placeholder text - ENHANCED"""
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        canvas_obj.setFont('Helvetica-Bold', 16)
        canvas_obj.drawRightString(doc.width + doc.leftMargin - 0.2*inch, 
                                  doc.height + doc.topMargin + 0.6*inch, "MCN")
        canvas_obj.setFont('Helvetica-Bold', 10)
        canvas_obj.drawRightString(doc.width + doc.leftMargin - 0.2*inch, 
                                  doc.height + doc.topMargin + 0.4*inch, "LOGO")
    
    def _add_background_watermark(self, canvas_obj, doc):
        """Add logo as background watermark - ENHANCED"""
        canvas_obj.saveState()
        
        # Only add watermark if logo is available
        if self.logo_image and self.logo_bytes:
            try:
                # Set transparency - ENHANCED: Slightly more visible
                canvas_obj.setFillAlpha(0.12)  # Increased from 0.08
                
                # Reset logo stream position
                self.logo_image.seek(0)
                
                # Calculate position for centered watermark
                center_x = doc.width/2 + doc.leftMargin
                center_y = doc.height/2 + doc.topMargin
                
                # Draw logo watermark - ENHANCED: Bigger and sharper
                logo_width = 4 * inch  # Increased size
                logo_height = 2 * inch  # Increased size
                logo_x = center_x - logo_width/2
                logo_y = center_y - logo_height/2
                
                # Draw with better quality
                canvas_obj.drawImage(ImageReader(self.logo_image), logo_x, logo_y, 
                                   width=logo_width, height=logo_height, 
                                   mask='auto', preserveAspectRatio=True)
                
                logger.info("✅ Enhanced logo watermark added to PDF")
                
            except Exception as e:
                logger.warning(f"Could not draw watermark: {e}")
                self._draw_text_watermark(canvas_obj, doc)
        else:
            self._draw_text_watermark(canvas_obj, doc)
        
        canvas_obj.restoreState()
    
    def _draw_text_watermark(self, canvas_obj, doc):
        """Draw text watermark - ENHANCED"""
        canvas_obj.setFillAlpha(0.12)  # Increased visibility
        
        # Calculate position for centered watermark
        center_x = doc.width/2 + doc.leftMargin
        center_y = doc.height/2 + doc.topMargin
        
        # Rotate the watermark
        canvas_obj.translate(center_x, center_y)
        canvas_obj.rotate(45)
        
        # Draw MCN text as watermark - ENHANCED: Bolder and bigger
        canvas_obj.setFont('Helvetica-Bold', 60)  # Increased size
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))  # Brand color
        canvas_obj.drawCentredString(0, 0, "MCN")
        
        canvas_obj.setFont('Helvetica-Bold', 30)  # Increased size
        canvas_obj.drawCentredString(0, -50, "Marshal Core")
    
    def _format_date(self, date_value) -> str:
        """Format date for display"""
        if not date_value:
            return "Not Provided"
        
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
    
    def generate_applicant_terms_pdf(self, applicant_data: Dict[str, Any], applicant_id: str, tier: str) -> str:
        """Generate Terms & Conditions PDF for NEW APPLICANT"""
        try:
            logger.info(f"Generating Applicant Terms PDF for: {applicant_id} (Tier: {tier})")
            
            filename = self._generate_filename(applicant_id, "terms", tier)
            filepath, relative_path = self._save_pdf(filename)
            
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
            
            # Continue with standard terms content...
            # [Rest of the terms content - you can copy from existing terms PDF generation]
            
            # Build PDF
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Applicant Terms PDF generated: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Applicant Terms PDF: {str(e)}")
            raise ApplicantPDFGenerationError(f"Failed to generate Applicant Terms PDF: {str(e)}")
    
    def generate_applicant_application_pdf(self, applicant_data: Dict[str, Any], applicant_id: str, tier: str, 
                                         payment_data: Dict[str, Any] = None) -> str:
        """Generate Application Form PDF for NEW APPLICANT with passport photo and payment details"""
        try:
            logger.info(f"Generating Applicant Application PDF for: {applicant_id} (Tier: {tier})")
            
            filename = self._generate_filename(applicant_id, "application", tier)
            filepath, relative_path = self._save_pdf(filename)
            
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
            
            payment_style = ParagraphStyle(
                'PaymentStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#d32f2f'),
                fontSize=11
            )
            
            # ✅ PASSPORT PHOTO SECTION - HIGH PRIORITY
            passport_embedded = False
            passport_table = None
            
            passport_path = applicant_data.get('passport_photo')
            if passport_path:
                passport_img = self._prepare_passport_image(passport_path)
                if passport_img:
                    # Create table for passport photo with label
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
            
            # Start content
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
                # Left column: Personal Info, Right column: Passport Photo
                personal_info = []
                
                # Personal Information
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
                
                # Create two-column table
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
                # Single column layout (no passport)
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
            
            # ✅ PAYMENT RECEIPT SECTION (HIGH PRIORITY)
            story.append(Paragraph("PAYMENT CONFIRMATION", heading1_style))
            
            if payment_data:
                # Create payment receipt box
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
            
            # Build PDF with enhanced watermark
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
                self._add_background_watermark(canvas_obj, doc_obj)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Applicant Application PDF generated: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Applicant Application PDF: {str(e)}")
            raise ApplicantPDFGenerationError(f"Failed to generate Applicant Application PDF: {str(e)}")
    
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
            raise ApplicantPDFGenerationError(f"Failed to generate applicant PDFs: {str(e)}")

# Singleton instance
applicant_pdf_service = ApplicantPDFService()