# app/utils/pdf.py
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import uuid

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
PDFS_DIR = STATIC_DIR / "pdfs"
TERMS_DIR = PDFS_DIR / "terms"
APPLICATIONS_DIR = PDFS_DIR / "applications"

# Ensure directories exist
for directory in [PDFS_DIR, TERMS_DIR, APPLICATIONS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Company information
COMPANY_INFO = {
    "name": "Marshal Core Nigeria Limited",
    "rc_number": "RC: 1234567",
    "address": "123 Security Plaza, Central Business District, Abuja, Nigeria",
    "phone": "+234 800 000 0000",
    "email": "legal@marshalcoreng.com",
    "website": "www.marshalcoreng.com"
}

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

class PDFGenerator:
    """PDF generation utility using ReportLab"""
    
    def __init__(self):
        """Initialize PDF generator"""
        logger.info("Initializing ReportLab PDF Generator")
    
    def _generate_filename(self, user_id: str, document_type: str) -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, category: str, filename: str) -> str:
        """Get filepath for saving PDF"""
        category_dir = PDFS_DIR / category
        category_dir.mkdir(exist_ok=True)
        
        file_path = category_dir / filename
        
        # Return relative path for web access
        relative_path = f"static/pdfs/{category}/{filename}"
        logger.info(f"PDF will be saved to: {relative_path}")
        return str(file_path), relative_path
    
    def _create_header_footer(self, canvas, doc, title="", is_terms=False):
        """Create header and footer for all pages"""
        canvas.saveState()
        
        # Header
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor('#1a237e'))
        canvas.drawString(inch, doc.height + inch + 0.5*inch, COMPANY_INFO['name'])
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(inch, doc.height + inch + 0.3*inch, COMPANY_INFO['address'])
        
        # Draw line under header
        canvas.setStrokeColor(colors.HexColor('#1a237e'))
        canvas.setLineWidth(1)
        canvas.line(inch, doc.height + inch + 0.2*inch, doc.width + inch, doc.height + inch + 0.2*inch)
        
        # Footer
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        
        # Left footer - page number
        canvas.drawString(inch, 0.5*inch, f"Page {doc.page}")
        
        # Center footer - document info
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas.drawCentredString(doc.width/2 + inch, 0.5*inch, doc_info)
        
        # Right footer - date
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawRightString(doc.width + inch, 0.5*inch, date_str)
        
        # Draw line above footer
        canvas.setStrokeColor(colors.lightgrey)
        canvas.setLineWidth(0.5)
        canvas.line(inch, 0.7*inch, doc.width + inch, 0.7*inch)
        
        canvas.restoreState()
    
    def generate_terms_conditions(self, officer_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Terms & Conditions PDF for an officer
        
        Args:
            officer_data: Dictionary containing officer information
            user_id: Unique identifier for the user
        
        Returns:
            Relative path to generated PDF file
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
                topMargin=100,  # Extra space for header
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
            
            # Title
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            # Document Information
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-TC-{user_id}-{datetime.now().strftime('%Y%m%d')}",
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
                "Marshal Core Nigeria Limited (hereinafter referred to as 'the Company') "
                "and the Officer/Applicant (hereinafter referred to as 'the Officer'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            # 1. PARTIES TO THE AGREEMENT
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            story.append(Paragraph(
                "<b>1.1 The Company:</b> Marshal Core Nigeria Limited, a private security company "
                "duly registered under the laws of the Federal Republic of Nigeria with RC Number: 1234567, "
                "having its principal office at 123 Security Plaza, Central Business District, Abuja, Nigeria.",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>1.2 The Officer:</b> {officer_data.get('full_name', 'N/A')}, "
                f"with National Identification Number: {officer_data.get('nin_number', 'N/A')}, "
                f"residing at {officer_data.get('residential_address', 'N/A')}.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 2. APPOINTMENT AND DUTIES
            story.append(Paragraph("2. APPOINTMENT AND DUTIES", heading1_style))
            story.append(Paragraph(
                f"<b>2.1 Appointment:</b> The Officer is hereby appointed as "
                f"{officer_data.get('rank', 'N/A')} in the {officer_data.get('position', 'N/A')} "
                "department, subject to the terms and conditions herein.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>2.2 Duties:</b> The Officer shall perform all duties assigned by the Company "
                "including but not limited to security services, patrol duties, client protection, "
                "and any other lawful instructions from authorized supervisors.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>2.3 Code of Conduct:</b> The Officer shall at all times maintain the highest "
                "standards of professionalism, integrity, and discipline as outlined in the "
                "Company's Code of Conduct Manual.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 3. TERM AND TERMINATION
            story.append(Paragraph("3. TERM AND TERMINATION", heading1_style))
            story.append(Paragraph(
                f"<b>3.1 Term:</b> This agreement shall commence on {datetime.now().strftime('%d %B %Y')} "
                "and continue until terminated in accordance with these terms.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>3.2 Termination for Cause:</b> The Company may immediately terminate this agreement for:",
                normal_style
            ))
            
            termination_reasons = [
                "Criminal conduct or conviction",
                "Gross misconduct or negligence",
                "Violation of company policies",
                "Unauthorized disclosure of confidential information",
                "Failure to perform assigned duties",
                "Absence without leave for more than 3 consecutive days"
            ]
            
            for reason in termination_reasons:
                story.append(Paragraph(f"• {reason}", normal_style))
            
            story.append(Spacer(1, 6))
            
            # 4. LEGAL CONSEQUENCES
            story.append(Paragraph("4. LEGAL CONSEQUENCES OF MISCONDUCT", heading1_style))
            story.append(Paragraph(
                "<b>WARNING:</b> Any breach of these terms may result in:",
                bold_style
            ))
            
            legal_consequences = [
                "Immediate termination of employment",
                "Forfeiture of all benefits and entitlements",
                "Legal prosecution in accordance with Nigerian laws",
                "Civil liability for damages caused",
                "Criminal charges where applicable",
                "Court proceedings and possible imprisonment",
                "Financial penalties and compensation payments"
            ]
            
            for consequence in legal_consequences:
                story.append(Paragraph(f"• {consequence}", normal_style))
            
            story.append(Spacer(1, 12))
            
            # 5. CONFIDENTIALITY
            story.append(Paragraph("5. CONFIDENTIALITY", heading1_style))
            story.append(Paragraph(
                "<b>5.1 Confidential Information:</b> The Officer shall not disclose any confidential "
                "information about the Company, its clients, or operations during or after employment.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>5.2 Non-Disclosure:</b> This obligation continues for 5 years after termination of employment.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # Page break for signature section
            story.append(PageBreak())
            
            # SIGNATURE SECTION
            story.append(Paragraph("ACCEPTANCE AND SIGNATURE", heading1_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph(
                f"I, <b>{officer_data.get('full_name', 'N/A')}</b>, hereby acknowledge that I have read, "
                "understood, and agree to be bound by all the terms and conditions stated in this document.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Officer Signature
            story.append(Paragraph("<b>Signature of Officer:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", normal_style))
            story.append(Spacer(1, 48))
            
            # Company Signature
            story.append(Paragraph("<b>For Marshal Core Nigeria Limited:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: _________________________", normal_style))
            story.append(Paragraph("Title: _________________________", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Company Stamp:</b>", bold_style))
            story.append(Spacer(1, 12))
            
            # Build PDF
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Terms & Conditions PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Terms & Conditions PDF: {str(e)}")
    
    def generate_application_form(self, applicant_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Application Form PDF for an applicant/officer
        
        Args:
            applicant_data: Dictionary containing applicant information
            user_id: Unique identifier for the user
        
        Returns:
            Relative path to generated PDF file
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
                topMargin=72,
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
            
            # Title
            story.append(Paragraph("MARSHAL CORE NIGERIA LIMITED", title_style))
            story.append(Paragraph("OFFICER APPLICATION FORM", title_style))
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
            
            personal_info_fields = [
                ("Full Name", applicant_data.get('full_name', 'N/A')),
                ("Officer ID", applicant_data.get('unique_id', applicant_data.get('officer_id', 'N/A'))),
                ("NIN Number", applicant_data.get('nin_number', 'N/A')),
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
            
            contact_info_fields = [
                ("Email Address", applicant_data.get('email', 'N/A')),
                ("Phone Number", applicant_data.get('phone', applicant_data.get('mobile_number', 'N/A'))),
                ("Residential Address", applicant_data.get('residential_address', 'N/A')),
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
                ("Rank", applicant_data.get('rank', 'N/A')),
                ("Position", applicant_data.get('position', 'N/A')),
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
            
            # Documents Submitted
            story.append(Paragraph("DOCUMENTS SUBMITTED", heading1_style))
            
            documents_info_fields = [
                ("Passport Photo", "✓ Submitted" if applicant_data.get('passport_photo') else "✗ Not Submitted"),
                ("NIN Slip", "✓ Submitted" if applicant_data.get('nin_slip') else "✗ Not Submitted"),
                ("SSCE Certificate", "✓ Submitted" if applicant_data.get('ssce_certificate') else "✗ Not Submitted"),
                ("Higher Education Degree", "✓ Submitted" if applicant_data.get('higher_education_degree') else "✗ Not Applicable"),
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
                "disqualification or termination of appointment.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Signature lines
            story.append(Paragraph("<b>Signature:</b> ___________________________", field_label_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph("<b>Date:</b> ___________________________", field_label_style))
            story.append(Spacer(1, 48))
            
            # Footer note
            story.append(Paragraph(
                "This document is electronically generated. Keep this copy for your records.",
                ParagraphStyle(
                    'FooterNote',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_CENTER
                )
            ))
            
            # Build PDF
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Application Form PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Application Form PDF: {str(e)}")
    
    def _format_date(self, date_value):
        """Format date for display"""
        if not date_value:
            return "N/A"
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime("%d %B, %Y")
        
        if isinstance(date_value, str):
            try:
                # Try to parse various date formats
                from datetime import datetime as dt
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]:
                    try:
                        parsed_date = dt.strptime(date_value, fmt)
                        return parsed_date.strftime("%d %B, %Y")
                    except:
                        continue
            except:
                pass
        
        return str(date_value)
    
    def generate_both_pdfs(self, user_data: Dict[str, Any], user_id: str) -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        
        Args:
            user_data: Dictionary containing user information
            user_id: Unique identifier for the user
        
        Returns:
            Dictionary with paths to both PDFs
        """
        try:
            logger.info(f"Generating both PDFs for user: {user_id}")
            
            # Generate Terms & Conditions
            terms_pdf_path = self.generate_terms_conditions(user_data, user_id)
            
            # Generate Application Form
            app_pdf_path = self.generate_application_form(user_data, user_id)
            
            return {
                "terms_pdf_path": terms_pdf_path,
                "application_pdf_path": app_pdf_path,
                "generated_at": datetime.now().isoformat(),
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Failed to generate both PDFs: {str(e)}")
            raise PDFGenerationError(f"Failed to generate both PDFs: {str(e)}")

# Singleton instance for easy import
pdf_generator = PDFGenerator()