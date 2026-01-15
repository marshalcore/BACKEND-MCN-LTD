# app/utils/email_validator.py
import re
import dns.resolver
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class EmailValidator:
    """Email validation utility to prevent hard bounces"""
    
    @staticmethod
    def is_valid_format(email: str) -> Tuple[bool, str]:
        """
        Validate email format using regex
        Returns: (is_valid, error_message)
        """
        if not email or not isinstance(email, str):
            return False, "Email is required"
        
        email = email.strip().lower()
        
        # Basic email format regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        # Check for common disposable email domains
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'guerrillamail.com',
            'mailinator.com', 'yopmail.com', 'throwawaymail.com',
            'fakeinbox.com', 'trashmail.com', 'getairmail.com',
            'dispostable.com', 'maildrop.cc'
        ]
        
        domain = email.split('@')[1]
        if any(disposable in domain for disposable in disposable_domains):
            return False, "Disposable email addresses are not allowed"
        
        # Check for Nigerian email providers (preferred)
        nigerian_domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'icloud.com', 'aol.com', 'zoho.com', 'protonmail.com',
            'marshalcoreofnigeria.ng', 'mcn.gov.ng', 'yahoo.co.uk'
        ]
        
        if not any(nigerian_domain in domain for nigerian_domain in nigerian_domains):
            logger.warning(f"Non-standard email domain detected: {domain}")
            # We'll still accept it but log it
        
        return True, "Email format is valid"
    
    @staticmethod
    def has_valid_mx_record(email: str) -> Tuple[bool, str]:
        """
        Check if email domain has valid MX records
        Returns: (has_mx, error_message)
        """
        try:
            domain = email.split('@')[1]
            
            # Try to get MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                if len(mx_records) > 0:
                    return True, f"Domain has {len(mx_records)} MX record(s)"
                else:
                    return False, "Domain has no MX records"
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                return False, "Domain does not exist or has no MX records"
            except dns.resolver.Timeout:
                return False, "DNS lookup timed out"
                
        except Exception as e:
            logger.error(f"MX record check failed: {str(e)}")
            return False, f"MX record check failed: {str(e)}"
    
    @staticmethod
    def validate_officer_email(email: str) -> Tuple[bool, str]:
        """
        Simplified validation for officer emails
        Use this in registration endpoints
        """
        # Format check
        format_valid, format_msg = EmailValidator.is_valid_format(email)
        if not format_valid:
            return False, format_msg
        
        # Additional checks for officer emails
        email_lower = email.lower()
        
        # Check for Marshal Core specific domains
        if 'marshalcore' in email_lower or 'mcn' in email_lower:
            return True, "Valid Marshal Core email"
        
        # Check for common professional domains
        professional_domains = [
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'icloud.com', 'protonmail.com', 'zoho.com'
        ]
        
        domain = email_lower.split('@')[1]
        if domain not in professional_domains:
            logger.warning(f"Non-standard domain for officer: {domain}")
            # Still accept but log for review
        
        return True, "Email validation passed"
    
    @staticmethod
    def check_for_typos(email: str) -> list:
        """Check for common email typos"""
        suggestions = []
        common_typos = {
            'gmial.com': 'gmail.com',
            'gmal.com': 'gmail.com',
            'gmail.cm': 'gmail.com',
            'gmail.con': 'gmail.com',
            'gmai.com': 'gmail.com',
            'yaho.com': 'yahoo.com',
            'yahoo.cm': 'yahoo.com',
            'hotmal.com': 'hotmail.com',
            'hotmail.cm': 'hotmail.com',
            'outlok.com': 'outlook.com',
            'outlook.cm': 'outlook.com',
            'yaho.co.uk': 'yahoo.co.uk',
            'gamil.com': 'gmail.com'
        }
        
        domain = email.split('@')[1]
        if domain in common_typos:
            suggestions.append(f"Did you mean @{common_typos[domain]}?")
        
        return suggestions