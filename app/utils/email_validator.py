# app/utils/email_validator.py
import re
import dns.resolver
import logging
import smtplib
from typing import Tuple, Optional, List
from email_validator import validate_email as email_validate, EmailNotValidError

logger = logging.getLogger(__name__)

class EmailValidator:
    """Email validation utility to prevent hard bounces - ACTIVE EMAIL VALIDATION"""
    
    @staticmethod
    def validate_syntax(email: str) -> Tuple[bool, str]:
        """
        Validate email syntax using email-validator library
        Returns: (is_valid, normalized_email)
        """
        if not email:
            return False, "Email is required"
        
        try:
            # Validate and get normalized email
            valid = email_validate(email, check_deliverability=False)
            normalized_email = valid.email
            return True, normalized_email
        except EmailNotValidError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Email validation failed: {str(e)}"
    
    @staticmethod
    def has_valid_mx(email: str) -> Tuple[bool, str]:
        """
        Check if email domain has valid MX records (can receive mail)
        Returns: (has_mx, message)
        """
        try:
            domain = email.split('@')[1]
            
            # Get MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                if mx_records and len(mx_records) > 0:
                    # Sort by priority (lower = higher priority)
                    mx_list = sorted(mx_records, key=lambda x: x.preference)
                    primary_mx = str(mx_list[0].exchange).rstrip('.')
                    return True, f"Domain has {len(mx_records)} MX record(s). Primary: {primary_mx}"
                else:
                    return False, "Domain has no MX records - cannot receive email"
            except dns.resolver.NoAnswer:
                return False, "Domain has no MX records"
            except dns.resolver.NXDOMAIN:
                return False, "Domain does not exist"
            except dns.resolver.Timeout:
                return False, "DNS lookup timed out - domain may be unreachable"
                
        except IndexError:
            return False, "Invalid email format"
        except Exception as e:
            logger.error(f"MX record check failed: {str(e)}")
            return False, f"MX record check failed: {str(e)}"
    
    @staticmethod
    def verify_mailbox_smtp(email: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        SMTP-based mailbox verification (most accurate)
        Actually connects to the mail server to verify if mailbox exists
        
        WARNING: Can be slow (2-5 seconds per email)
        Use with caution in production
        """
        try:
            domain = email.split('@')[1]
            
            # Get MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                if not mx_records:
                    return False, "No MX records found"
                
                # Get the highest priority MX server
                mx_record = sorted(mx_records, key=lambda x: x.preference)[0]
                mx_host = str(mx_record.exchange).rstrip('.')
                
                # Connect to SMTP server
                server = smtplib.SMTP(timeout=timeout)
                server.set_debuglevel(0)  # Set to 1 for debugging
                
                try:
                    server.connect(mx_host, 25)
                    server.helo(server.local_hostname)
                    server.mail('test@example.com')  # Use a valid from address
                    
                    # This is the key command - it checks if the mailbox exists
                    code, message = server.rcpt(email)
                    server.quit()
                    
                    if code == 250:
                        return True, "Mailbox exists and is active"
                    elif code == 550:
                        return False, "Mailbox does not exist (hard bounce)"
                    else:
                        return False, f"Server response: {code} - {message.decode() if hasattr(message, 'decode') else message}"
                        
                except smtplib.SMTPServerDisconnected:
                    return False, "SMTP server disconnected"
                except smtplib.SMTPConnectError:
                    return False, "Could not connect to mail server"
                except Exception as e:
                    return False, f"SMTP verification failed: {str(e)}"
                finally:
                    try:
                        server.quit()
                    except:
                        pass
                        
            except Exception as e:
                return False, f"MX lookup failed: {str(e)}"
                
        except IndexError:
            return False, "Invalid email format"
    
    @staticmethod
    def validate_active_email(email: str, verify_smtp: bool = False) -> Tuple[bool, str]:
        """
        Main validation function - checks if email is active and can receive mail
        
        Args:
            email: Email to validate
            verify_smtp: If True, performs SMTP verification (slower but accurate)
                        If False, only checks MX records (faster, good for most cases)
        
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        # Step 1: Syntax validation
        syntax_valid, result = EmailValidator.validate_syntax(email)
        if not syntax_valid:
            return False, result
        
        normalized_email = result
        
        # Step 2: MX record validation (domain can receive mail)
        mx_valid, mx_message = EmailValidator.has_valid_mx(normalized_email)
        if not mx_valid:
            return False, f"Domain cannot receive email: {mx_message}"
        
        # Step 3: Optional SMTP verification (slow but accurate)
        if verify_smtp:
            smtp_valid, smtp_message = EmailValidator.verify_mailbox_smtp(normalized_email)
            if not smtp_valid:
                return False, f"Mailbox verification failed: {smtp_message}"
            return True, "Email is active and can receive mail"
        
        return True, "Domain can receive email (MX records verified)"
    
    @staticmethod
    def validate_officer_email(email: str, strict: bool = False) -> Tuple[bool, str]:
        """
        Simplified validation for officer emails
        Use this in registration endpoints
        
        Args:
            email: Email to validate
            strict: If True, performs MX validation (recommended)
        """
        # Syntax check
        syntax_valid, result = EmailValidator.validate_syntax(email)
        if not syntax_valid:
            return False, result
        
        normalized_email = result
        
        # Optional MX check (recommended)
        if strict:
            mx_valid, mx_message = EmailValidator.has_valid_mx(normalized_email)
            if not mx_valid:
                return False, f"Email domain cannot receive mail: {mx_message}"
            return True, "Email is valid and domain can receive mail"
        
        return True, "Email syntax is valid"
    
    @staticmethod
    def check_for_typos(email: str) -> List[str]:
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
            'protomail.com': 'protonmail.com',
            'protonmal.com': 'protonmail.com',
            'yaho.co.uk': 'yahoo.co.uk',
            'gamil.com': 'gmail.com',
            'gmaiil.com': 'gmail.com',
            'gmiall.com': 'gmail.com',
            'gnail.com': 'gmail.com'
        }
        
        try:
            domain = email.split('@')[1].lower()
            if domain in common_typos:
                suggestions.append(f"Did you mean @{common_typos[domain]}?")
        except:
            pass
        
        return suggestions
    
    @staticmethod
    def get_email_domain(email: str) -> Optional[str]:
        """Extract and return domain from email"""
        try:
            return email.split('@')[1].lower()
        except:
            return None
    
    @staticmethod
    def get_email_provider(email: str) -> Optional[str]:
        """Get email provider name"""
        domain = EmailValidator.get_email_domain(email)
        if domain:
            if 'gmail.com' in domain:
                return 'Google/Gmail'
            elif 'yahoo.com' in domain or 'yahoo.co.uk' in domain:
                return 'Yahoo'
            elif 'hotmail.com' in domain or 'outlook.com' in domain:
                return 'Microsoft'
            elif 'icloud.com' in domain:
                return 'Apple'
            elif 'protonmail.com' in domain:
                return 'ProtonMail'
            elif 'marshalcoreofnigeria.ng' in domain:
                return 'Marshal Core Official'
            else:
                return 'Other'
        return None


# ==================== CONVENIENCE FUNCTIONS ====================

def validate_email(email: str, strict: bool = False) -> Tuple[bool, str]:
    """
    Main validation function - checks if email can receive mail
    
    Args:
        email: Email to validate
        strict: If True, performs MX validation (recommended)
    
    Returns:
        Tuple[bool, str]: (is_valid, message)
    """
    return EmailValidator.validate_active_email(email, verify_smtp=False) if strict else EmailValidator.validate_syntax(email)

def validate_officer_email(email: str, strict: bool = True) -> Tuple[bool, str]:
    """
    Officer email validation - with MX check by default
    """
    return EmailValidator.validate_officer_email(email, strict=strict)

def check_email_typos(email: str) -> List[str]:
    """Check for common email typos"""
    return EmailValidator.check_for_typos(email)

def get_email_domain(email: str) -> Optional[str]:
    """Extract domain from email"""
    return EmailValidator.get_email_domain(email)

def get_email_provider(email: str) -> Optional[str]:
    """Get email provider name"""
    return EmailValidator.get_email_provider(email)