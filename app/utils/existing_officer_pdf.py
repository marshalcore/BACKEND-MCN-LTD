# app/utils/pdf/existing_officer_pdf.py
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from datetime import datetime
from typing import Dict, Any

class ExistingOfficerPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom styles for Marshal Core branding"""
        self.styles.add(ParagraphStyle(
            name='MarshalTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30
        ))
        
        self.styles.add(ParagraphStyle(
            name='MarshalHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#283593'),
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='MarshalBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
        
        self.styles.add(ParagraphStyle(
            name='MarshalFooter',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=1  # Center alignment
        ))
    
    def generate_registration_form(self, officer_data: Dict[str, Any]) -> str:
        """Generate Existing Officer Registration Form PDF"""
        try:
            # Create filename with new officer ID format
            officer_id = officer_data.get('officer_id', 'unknown').replace('/', '_')
            filename = f"existing_officer_{officer_id}_registration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Create directory if it doesn't exist
            base_dir = os.path.join("static", "pdfs", "existing_officers")
            os.makedirs(base_dir, exist_ok=True)
            filepath = os.path.join(base_dir, filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            story = []
            
            # Add Marshal Core Header
            story.append(self.create_header())
            story.append(Spacer(1, 20))
            
            # Title
            story.append(Paragraph("EXISTING OFFICER REGISTRATION FORM", self.styles['MarshalTitle']))
            story.append(Spacer(1, 10))
            
            # Registration Details
            story.append(self.create_registration_details(officer_data))
            story.append(Spacer(1, 20))
            
            # Officer Information Section
            story.append(Paragraph("PERSONAL INFORMATION", self.styles['MarshalHeading']))
            story.append(self.create_personal_info_table(officer_data))
            story.append(Spacer(1, 20))
            
            # Service Details Section (NEW FIELDS)
            story.append(Paragraph("SERVICE DETAILS", self.styles['MarshalHeading']))
            story.append(self.create_service_details_table(officer_data))
            story.append(Spacer(1, 20))
            
            # Contact Information
            story.append(Paragraph("CONTACT INFORMATION", self.styles['MarshalHeading']))
            story.append(self.create_contact_info_table(officer_data))
            story.append(Spacer(1, 20))
            
            # Document Checklist
            story.append(Paragraph("DOCUMENT CHECKLIST", self.styles['MarshalHeading']))
            story.append(self.create_document_checklist(officer_data))
            story.append(Spacer(1, 30))
            
            # Footer
            story.append(self.create_footer())
            
            # Build PDF
            doc.build(story)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    def create_header(self):
        """Create PDF header with Marshal Core branding"""
        header_data = [
            ["MARSHAL CORE SECURITY SERVICES"],
            ["Existing Officer Registration System"],
            ["Official Document - Confidential"]
        ]
        
        header_table = Table(header_data, colWidths=[6*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTSIZE', (0, 1), (0, 1), 12),
            ('FONTSIZE', (0, 2), (0, 2), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a237e')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        return header_table
    
    def create_registration_details(self, data):
        """Create registration details table"""
        registration_info = [
            ["Registration ID:", data.get('officer_id', 'N/A')],
            ["Registration Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Officer Category:", data.get('category', 'N/A')],
            ["Verification Status:", "Verified" if data.get('is_verified') else "Pending"],
        ]
        
        table = Table(registration_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
        ]))
        
        return table
    
    def create_personal_info_table(self, data):
        """Create personal information table"""
        personal_info = [
            ["Full Name:", data.get('full_name', 'N/A')],
            ["NIN Number:", data.get('nin_number', 'N/A')],
            ["Date of Birth:", self.format_date(data.get('date_of_birth'))],
            ["Gender:", data.get('gender', 'N/A')],
            ["Marital Status:", data.get('marital_status', 'N/A')],
            ["Nationality:", data.get('nationality', 'Nigerian')],
            ["Place of Birth:", data.get('place_of_birth', 'N/A')],
            ["Religion:", data.get('religion', 'N/A')],
        ]
        
        table = Table(personal_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
        ]))
        
        return table
    
    def create_service_details_table(self, data):
        """Create service details table with NEW fields"""
        service_info = [
            ["Date of Enlistment:", self.format_date(data.get('date_of_enlistment'))],
            ["Date of Promotion:", self.format_date(data.get('date_of_promotion'))],
            ["Rank:", data.get('rank', 'N/A')],
            ["Position:", data.get('position', 'N/A')],
            ["Years of Service:", data.get('years_of_service', 'N/A')],
            ["Service Number:", data.get('service_number', 'N/A')],
            ["Additional Skills:", data.get('additional_skills', 'N/A')],
        ]
        
        table = Table(service_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
        ]))
        
        return table
    
    def create_contact_info_table(self, data):
        """Create contact information table"""
        contact_info = [
            ["Email Address:", data.get('email', 'N/A')],
            ["Phone Number:", data.get('phone', 'N/A')],
            ["Residential Address:", data.get('residential_address', 'N/A')],
            ["State of Residence:", data.get('state_of_residence', 'N/A')],
            ["LGA of Residence:", data.get('local_government_residence', 'N/A')],
            ["Country of Residence:", data.get('country_of_residence', 'Nigeria')],
            ["State of Origin:", data.get('state_of_origin', 'N/A')],
            ["LGA of Origin:", data.get('local_government_origin', 'N/A')],
            ["Bank Name:", data.get('bank_name', 'N/A')],
            ["Account Number:", data.get('account_number', 'N/A')],
        ]
        
        table = Table(contact_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3e5f5')),
        ]))
        
        return table
    
    def create_document_checklist(self, data):
        """Create document checklist table"""
        documents = [
            ["✓" if data.get('has_passport') else "□", "Passport Photograph", "Required", "Uploaded" if data.get('has_passport') else "Not Uploaded"],
            ["✓" if data.get('has_nin') else "□", "NIN Slip", "Required", "Uploaded" if data.get('has_nin') else "Not Uploaded"],
            ["✓" if data.get('has_ssce') else "□", "SSCE Certificate", "Required", "Uploaded" if data.get('has_ssce') else "Not Uploaded"],
            ["✓" if data.get('has_birth_cert') else "□", "Birth Certificate", "Optional", "Uploaded" if data.get('has_birth_cert') else "Not Uploaded"],
            ["✓" if data.get('has_appointment') else "□", "Appointment Letter", "Optional", "Uploaded" if data.get('has_appointment') else "Not Uploaded"],
            ["✓" if data.get('has_promotion') else "□", "Promotion Letters", "Optional", "Uploaded" if data.get('has_promotion') else "Not Uploaded"]
        ]
        
        table = Table(documents, colWidths=[0.3*inch, 2.5*inch, 1.2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e3f2fd')),
        ]))
        
        return table
    
    def create_footer(self):
        """Create PDF footer"""
        footer_text = f"""
        <para alignment='center'>
        <font color='gray' size=8>
        <b>MARSHAL CORE SECURITY SERVICES</b><br/>
        This document is computer-generated and does not require a signature.<br/>
        For inquiries, contact: support@marshalcore.com | Phone: +234-XXX-XXXX-XXXX<br/>
        Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </font>
        </para>
        """
        
        return Paragraph(footer_text, self.styles['MarshalFooter'])
    
    def format_date(self, date_value):
        """Format date for display"""
        if not date_value:
            return "N/A"
        
        if isinstance(date_value, str):
            try:
                # Try to parse string date
                date_obj = datetime.strptime(date_value, "%Y-%m-%d")
                return date_obj.strftime("%d %B %Y")
            except:
                return date_value
        elif isinstance(date_value, datetime):
            return date_value.strftime("%d %B %Y")
        
        return str(date_value)