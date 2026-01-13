# app/services/pdf_service.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.utils.pdf import pdf_generator
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_data(self, user_id: str, user_type: str) -> Dict[str, Any]:
        """Get user data for PDF generation based on user type"""
        user_data = {}
        
        if user_type == "applicant":
            user = self.db.query(Applicant).filter(Applicant.id == user_id).first()
            if user:
                user_data = {
                    'id': str(user.id),
                    'unique_id': user.unique_id,
                    'full_name': user.full_name,
                    'nin_number': user.nin_number,
                    'email': user.email,
                    'mobile_number': user.mobile_number,
                    'phone_number': user.phone_number,
                    'gender': user.gender,
                    'date_of_birth': user.date_of_birth,
                    'marital_status': user.marital_status,
                    'nationality': user.nationality,
                    'place_of_birth': user.place_of_birth,
                    'religion': user.religion,
                    'category': user.category,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'passport_photo': user.passport_photo,
                    'nin_slip': user.nin_slip,
                    'ssce_certificate': user.ssce_certificate,
                    'higher_education_degree': user.higher_education_degree,
                    'do_you_smoke': user.do_you_smoke,
                    'agree_to_join': user.agree_to_join,
                    'agree_to_abide_rules': user.agree_to_abide_rules,
                    'agree_to_return_properties': user.agree_to_return_properties,
                    'additional_skills': user.additional_skills,
                    'design_rating': user.design_rating,
                }
        
        elif user_type == "officer":
            user = self.db.query(Officer).filter(Officer.id == user_id).first()
            if user:
                user_data = {
                    'id': str(user.id),
                    'unique_id': user.unique_id,
                    'full_name': user.full_name or "Officer",
                    'email': user.email,
                    'phone': user.phone,
                    'rank': user.rank,
                    'position': user.position,
                    'date_of_birth': user.date_of_birth,
                    'gender': user.gender,
                    'nin_number': user.nin_number,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'additional_skills': user.additional_skills,
                }
                
                # Try to get more data from applicant if available
                if user.applicant:
                    applicant = user.applicant
                    user_data.update({
                        'full_name': applicant.full_name or user_data['full_name'],
                        'nin_number': applicant.nin_number or user_data['nin_number'],
                        'date_of_birth': applicant.date_of_birth or user_data['date_of_birth'],
                        'gender': applicant.gender or user_data['gender'],
                        'marital_status': applicant.marital_status,
                        'nationality': applicant.nationality,
                        'place_of_birth': applicant.place_of_birth,
                        'religion': applicant.religion,
                        'category': applicant.category,
                        'residential_address': applicant.residential_address or user_data['residential_address'],
                        'state_of_residence': applicant.state_of_residence or user_data['state_of_residence'],
                        'local_government_residence': applicant.local_government_residence,
                        'country_of_residence': applicant.country_of_residence,
                        'state_of_origin': applicant.state_of_origin,
                        'local_government_origin': applicant.local_government_origin,
                        'bank_name': applicant.bank_name,
                        'account_number': applicant.account_number,
                        'passport_photo': applicant.passport_photo,
                        'nin_slip': applicant.nin_slip,
                        'ssce_certificate': applicant.ssce_certificate,
                        'higher_education_degree': applicant.higher_education_degree,
                        'do_you_smoke': applicant.do_you_smoke,
                        'agree_to_join': applicant.agree_to_join,
                        'agree_to_abide_rules': applicant.agree_to_abide_rules,
                        'agree_to_return_properties': applicant.agree_to_return_properties,
                        'additional_skills': applicant.additional_skills or user_data['additional_skills'],
                        'design_rating': applicant.design_rating,
                    })
        
        elif user_type == "existing_officer":
            user = self.db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
            if user:
                user_data = {
                    'officer_id': user.officer_id,
                    'full_name': user.full_name,
                    'nin_number': user.nin_number,
                    'email': user.email,
                    'phone': user.phone,
                    'rank': user.rank,
                    'position': user.position,
                    'date_of_birth': user.date_of_birth,
                    'gender': user.gender,
                    'marital_status': user.marital_status,
                    'nationality': user.nationality,
                    'place_of_birth': user.place_of_birth,
                    'religion': user.religion,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'additional_skills': user.additional_skills,
                    'passport_photo': user.passport_photo,
                    'nin_slip': user.nin_slip,
                    'ssce_certificate': user.ssce_certificate,
                }
        
        return user_data
    
    def generate_terms_conditions(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> str:
        """
        Generate Terms & Conditions PDF for a user
        """
        try:
            logger.info(f"Generating Terms & Conditions for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate PDF
            pdf_path = pdf_generator.generate_terms_conditions(user_data, user_id)
            
            # Update database record
            self._update_pdf_record(user_id, user_type, 'terms', pdf_path)
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions: {str(e)}")
            raise
    
    def generate_application_form(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> str:
        """
        Generate Application Form PDF for a user
        """
        try:
            logger.info(f"Generating Application Form for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate PDF
            pdf_path = pdf_generator.generate_application_form(user_data, user_id)
            
            # Update database record
            self._update_pdf_record(user_id, user_type, 'application', pdf_path)
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form: {str(e)}")
            raise
    
    def generate_both_pdfs(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        """
        try:
            logger.info(f"Generating both PDFs for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate both PDFs
            pdf_paths = pdf_generator.generate_both_pdfs(user_data, user_id, user_type)
            
            # Update database records
            self._update_pdf_record(
                user_id, 
                user_type, 
                'terms', 
                pdf_paths['terms_pdf_path']
            )
            self._update_pdf_record(
                user_id, 
                user_type, 
                'application', 
                pdf_paths['application_pdf_path']
            )
            
            return pdf_paths
            
        except Exception as e:
            logger.error(f"Failed to generate both PDFs: {str(e)}")
            raise
    
    def _update_pdf_record(
        self,
        user_id: str,
        user_type: str,
        pdf_type: str,
        pdf_path: str
    ):
        """
        Update database record with PDF path
        """
        try:
            now = datetime.now()
            
            if user_type == "applicant":
                applicant = self.db.query(Applicant).filter(Applicant.id == user_id).first()
                if applicant:
                    if pdf_type == 'terms':
                        applicant.terms_pdf_path = pdf_path
                        applicant.terms_generated_at = now
                    else:
                        applicant.application_pdf_path = pdf_path
                        applicant.application_generated_at = now
                    self.db.commit()
            
            elif user_type == "officer":
                officer = self.db.query(Officer).filter(Officer.id == user_id).first()
                if officer:
                    if pdf_type == 'terms':
                        officer.terms_pdf_path = pdf_path
                        officer.terms_generated_at = now
                    else:
                        officer.application_pdf_path = pdf_path
                        officer.application_generated_at = now
                    self.db.commit()
            
            elif user_type == "existing_officer":
                officer = self.db.query(ExistingOfficer).filter(
                    ExistingOfficer.id == user_id
                ).first()
                if officer:
                    if pdf_type == 'terms':
                        officer.terms_pdf_path = pdf_path
                        officer.terms_generated_at = now
                    else:
                        officer.application_pdf_path = pdf_path
                        officer.application_generated_at = now
                    self.db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to update PDF record: {str(e)}")