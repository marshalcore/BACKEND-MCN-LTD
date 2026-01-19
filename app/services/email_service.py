# app/services/email_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import settings
from jinja2 import Environment, FileSystemLoader
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import os
import json

# ✅ ADD RESEND IMPORTS
try:
    import resend
    from resend.exceptions import ResendError
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None
    ResendError = Exception

logger = logging.getLogger(__name__)

# ✅ ENVIRONMENT DETECTION
IS_RENDER = os.getenv("RENDER") == "true"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@marshalcoreofnigeria.ng")
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", "Marshal Core Nigeria")
RESEND_ENABLED = bool(RESEND_API_KEY and RESEND_AVAILABLE)

# ✅ Always include a professional display name
MAIL_FROM_WITH_NAME = f"Marshal Core <{settings.EMAIL_FROM}>"

# 🔄 ALL SMTP PORT CONFIGURATIONS
SMTP_CONFIGS = [
    # Primary: TLS on port 587 (most common)
    {
        "name": "tls_587",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=587,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Secondary: SSL on port 465
    {
        "name": "ssl_465",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=465,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=False,
            MAIL_SSL_TLS=True,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Alternative: Port 25 (standard SMTP)
    {
        "name": "plain_25",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=25,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Alternative: Port 2525 (common alternative)
    {
        "name": "tls_2525",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=2525,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Alternative: Port 8025 (development/common alt)
    {
        "name": "tls_8025",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=8025,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    }
]

env = Environment(loader=FileSystemLoader("templates/email"))

# 🔑 Purpose normalizer (fix)
def normalize_purpose(purpose: str) -> str:
    mapping = {
        "admin_signup": "signup",
        "admin_login": "login",
        "admin_reset": "password_reset",
        "officer_signup": "officer_signup"
    }
    return mapping.get(purpose, purpose)

# 🚀 CONCURRENT PORT TESTING
async def test_smtp_connection_async(host: str, port: int, use_tls: bool = False, use_ssl: bool = False) -> bool:
    """Test SMTP connection to a specific port"""
    try:
        smtp = aiosmtplib.SMTP(
            hostname=host,
            port=port,
            use_tls=use_ssl,  # SSL is immediate TLS
            start_tls=use_tls,  # STARTTLS (upgrade after connection)
            timeout=5
        )
        
        await smtp.connect()
        
        if use_tls and not use_ssl:
            await smtp.starttls()
        
        await smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        await smtp.quit()
        
        logger.info(f"✅ SMTP connection successful on port {port}")
        return True
    except Exception as e:
        logger.debug(f"❌ SMTP connection failed on port {port}: {str(e)}")
        return False

async def find_best_smtp_port() -> Optional[ConnectionConfig]:
    """Test all ports concurrently and return the first working one"""
    tasks = []
    
    # Test all ports concurrently
    for config in SMTP_CONFIGS:
        port = config["config"].MAIL_PORT
        use_tls = config["config"].MAIL_STARTTLS
        use_ssl = config["config"].MAIL_SSL_TLS
        
        task = test_smtp_connection_async(
            settings.EMAIL_HOST,
            port,
            use_tls,
            use_ssl
        )
        tasks.append((config, task))
    
    # Wait for the first successful connection
    for config, task in tasks:
        try:
            success = await asyncio.wait_for(task, timeout=10)
            if success:
                logger.info(f"🎯 Selected SMTP port {config['config'].MAIL_PORT} ({config['name']})")
                return config["config"]
        except (asyncio.TimeoutError, Exception):
            continue
    
    logger.error("❌ All SMTP ports failed")
    return None

# 📧 EMAIL SERVICE CLASS WITH RESEND SUPPORT
class EmailService:
    """Email service with Resend API primary and SMTP fallback"""
    
    def __init__(self):
        # Check environment
        self.is_render = IS_RENDER
        self.resend_enabled = RESEND_ENABLED
        
        # Initialize Resend if enabled
        if self.resend_enabled:
            try:
                resend.api_key = RESEND_API_KEY
                self.from_email = RESEND_FROM_EMAIL
                self.from_name = RESEND_FROM_NAME
                logger.info("✅ Resend API initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Resend: {e}")
                self.resend_enabled = False
        
        # Keep SMTP config for backup/local
        self.smtp_configs = SMTP_CONFIGS
        
        # Stats tracking
        self.stats = {
            "total_sent": 0,
            "resend_success": 0,
            "smtp_success": 0,
            "failures": 0,
            "last_sent": None
        }
        
        logger.info(f"📧 EmailService initialized - Resend: {self.resend_enabled}, Render: {self.is_render}")
    
    # ✅ NEW RESEND METHOD
    async def send_email_resend(self, to_email: str, subject: str, html_content: str, 
                              attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email using Resend API"""
        if not self.resend_enabled:
            return {"status": "error", "provider": "resend", "error": "Resend not enabled"}
        
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            
            # Add attachments if provided
            if attachments:
                params["attachments"] = attachments
            
            email = resend.Emails.send(params)
            
            self.stats["resend_success"] += 1
            self.stats["total_sent"] += 1
            self.stats["last_sent"] = datetime.now()
            
            logger.info(f"✅ Email sent via Resend to {to_email}: {subject}")
            return {"status": "success", "provider": "resend", "id": email.get("id", "unknown")}
            
        except ResendError as e:
            logger.error(f"❌ Resend API error for {to_email}: {str(e)}")
            return {"status": "error", "provider": "resend", "error": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error in Resend for {to_email}: {str(e)}")
            return {"status": "error", "provider": "resend", "error": str(e)}
    
    # ✅ KEEP SMTP METHOD (renamed from send_email_with_retry logic)
    async def send_email_smtp(self, to_email: str, subject: str, html_content: str,
                            attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email using SMTP (backup for local development)"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Find best port for this attempt
                best_config = await find_best_smtp_port()
                
                if not best_config:
                    logger.error(f"❌ No working SMTP port found on attempt {attempt + 1}")
                    await asyncio.sleep(retry_delay)
                    continue
                
                # Create message
                message = MessageSchema(
                    subject=subject,
                    recipients=[to_email],
                    body=html_content,
                    subtype="html",
                    attachments=attachments or []
                )
                
                # Send email with selected config
                fm = FastMail(best_config)
                await fm.send_message(message)
                
                self.stats["smtp_success"] += 1
                self.stats["total_sent"] += 1
                self.stats["last_sent"] = datetime.now()
                
                logger.info(f"✅ {subject} email sent via SMTP to {to_email} via port {best_config.MAIL_PORT}")
                return {"status": "success", "provider": "smtp", "port": best_config.MAIL_PORT}
                
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed for {subject} to {to_email}: {str(e)}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
        
        self.stats["failures"] += 1
        logger.error(f"❌ Failed to send {subject} email via SMTP to {to_email} after {max_retries} attempts")
        return {"status": "error", "provider": "smtp", "error": "All attempts failed"}
    
    # ✅ FALLBACK METHOD
    async def send_email_fallback(self, to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Fallback method when all email services fail"""
        try:
            # Log to file
            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, "email_failures.jsonl")
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "to_email": to_email,
                "subject": subject,
                "html_content": html_content[:500] + "..." if len(html_content) > 500 else html_content,
                "status": "failed_all_providers"
            }
            
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            logger.warning(f"📝 Email logged to file (all providers failed): {subject} to {to_email}")
            return {"status": "logged", "provider": "file", "path": log_file}
            
        except Exception as e:
            logger.error(f"❌ Failed to log email to file: {str(e)}")
            return {"status": "error", "provider": "file", "error": str(e)}
    
    # ✅ UPDATED SEND EMAIL DIRECT METHOD
    async def send_email_direct(self, to_email: str, subject: str, html_content: str,
                              attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send email - Try Resend first, fallback to SMTP
        """
        logger.info(f"📤 Sending email to {to_email}: {subject}")
        
        # TRY RESEND FIRST (if enabled)
        if self.resend_enabled:
            result = await self.send_email_resend(to_email, subject, html_content, attachments)
            if result.get("status") == "success":
                return result
        
        # FALLBACK TO SMTP (if not on Render or Resend not enabled)
        if not self.is_render or not self.resend_enabled:
            result = await self.send_email_smtp(to_email, subject, html_content, attachments)
            if result.get("status") == "success":
                return result
        
        # LAST RESORT: Log to file
        return await self.send_email_fallback(to_email, subject, html_content)
    
    # ✅ COMPATIBILITY METHOD (for existing code)
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Compatibility method for existing code
        Returns boolean for backward compatibility
        """
        result = await self.send_email_direct(to_email, subject, html_content)
        return result.get("status") in ["success", "logged"]
    
    # ✅ TEMPLATE METHODS
    def create_otp_template(self, otp_code: str, user_name: str = "") -> str:
        """Create HTML for OTP email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .otp-box {{ background: white; padding: 20px; border-radius: 8px; border: 2px dashed #1a237e; text-align: center; margin: 20px 0; }}
                .otp-code {{ font-size: 32px; font-weight: bold; color: #1a237e; letter-spacing: 8px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Marshal Core Nigeria</h1>
                    <h2>Verification Code</h2>
                </div>
                
                <div class="content">
                    <h3>Dear {user_name or 'User'},</h3>
                    
                    <p>Your verification code for Marshal Core Nigeria is:</p>
                    
                    <div class="otp-box">
                        <div class="otp-code">{otp_code}</div>
                    </div>
                    
                    <p>This code will expire in 10 minutes. Please do not share this code with anyone.</p>
                    
                    <p>If you did not request this code, please ignore this email or contact support.</p>
                    
                    <p>Best regards,<br>
                    <strong>Marshal Core Nigeria Security Team</strong></p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>© {datetime.now().year} Marshal Core Nigeria. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def create_welcome_template(self, user_name: str) -> str:
        """Create HTML for welcome email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .welcome-message {{ background: white; padding: 20px; border-left: 4px solid #4CAF50; margin: 20px 0; }}
                .button {{ display: inline-block; background-color: #1a237e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Marshal Core Nigeria</h1>
                </div>
                
                <div class="content">
                    <div class="welcome-message">
                        <h2>Hello {user_name}!</h2>
                        <p>Welcome to Marshal Core Nigeria - Your trusted security partner.</p>
                        
                        <p>We're excited to have you join our community of security professionals. Your account has been successfully created and is now active.</p>
                        
                        <p><strong>What's next?</strong></p>
                        <ul>
                            <li>Complete your profile information</li>
                            <li>Upload required documents</li>
                            <li>Explore training materials</li>
                            <li>Connect with other officers</li>
                        </ul>
                        
                        <p>You can now login to your dashboard to get started:</p>
                        
                        <div style="text-align: center;">
                            <a href="https://marshal-core-frontend.onrender.com/officer-login.html" class="button">Go to Dashboard</a>
                        </div>
                    </div>
                    
                    <p>If you have any questions or need assistance, our support team is here to help.</p>
                    
                    <p>Best regards,<br>
                    <strong>The Marshal Core Nigeria Team</strong></p>
                </div>
                
                <div class="footer">
                    <p>This is an automated welcome email.</p>
                    <p>© {datetime.now().year} Marshal Core Nigeria. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def create_payment_template(self, name: str, payment_reference: str, amount: int, 
                               payment_type: str, payment_date: str, payment_method: str = "Online Payment") -> str:
        """Create HTML for payment confirmation"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .receipt {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .amount {{ font-size: 24px; color: #1a237e; font-weight: bold; margin: 10px 0; }}
                .status-success {{ color: #4CAF50; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Marshal Core Nigeria</h1>
                    <h2>Payment Confirmation</h2>
                </div>
                
                <div class="content">
                    <h3>Dear {name},</h3>
                    
                    <p>Thank you for your payment. Your transaction has been completed successfully.</p>
                    
                    <div class="receipt">
                        <h4>Payment Details:</h4>
                        <p><strong>Reference Number:</strong> {payment_reference}</p>
                        <p><strong>Payment Type:</strong> {payment_type}</p>
                        <p><strong>Payment Method:</strong> {payment_method}</p>
                        <p><strong>Date & Time:</strong> {payment_date}</p>
                        <p><strong>Amount:</strong> <span class="amount">₦{amount:,.2f}</span></p>
                        <p><strong>Status:</strong> <span class="status-success">✓ Completed</span></p>
                    </div>
                    
                    <p>This receipt confirms that your payment has been received and processed successfully by Marshal Core Nigeria.</p>
                    
                    <p>Please keep this receipt for your records. You can also download it from your dashboard.</p>
                    
                    <p>If you have any questions about this payment, please contact our support team.</p>
                    
                    <p>Best regards,<br>
                    <strong>Marshal Core Nigeria Finance Team</strong></p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>© {datetime.now().year} Marshal Core Nigeria. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    # ✅ TEST METHOD (renamed from test_smtp_connection)
    async def test_email_connection(self) -> Dict[str, Any]:
        """Test email connection (both Resend and SMTP)"""
        test_email = "test@example.com"
        test_subject = "Connection Test"
        test_html = "<h1>Test Email</h1><p>This is a test email to verify connection.</p>"
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "is_render": self.is_render,
                "resend_enabled": self.resend_enabled,
                "smtp_available": bool(self.smtp_configs)
            },
            "tests": {}
        }
        
        # Test Resend if enabled
        if self.resend_enabled:
            try:
                resend_result = await self.send_email_resend(test_email, test_subject, test_html)
                results["tests"]["resend"] = resend_result
            except Exception as e:
                results["tests"]["resend"] = {"status": "error", "error": str(e)}
        
        # Test SMTP (always test if not on Render)
        if not self.is_render:
            try:
                # Find best port first
                best_config = await find_best_smtp_port()
                if best_config:
                    smtp_result = await self.send_email_smtp(test_email, test_subject, test_html)
                    results["tests"]["smtp"] = smtp_result
                else:
                    results["tests"]["smtp"] = {"status": "error", "error": "No working SMTP port found"}
            except Exception as e:
                results["tests"]["smtp"] = {"status": "error", "error": str(e)}
        
        # Determine overall status
        if any(test.get("status") == "success" for test in results["tests"].values()):
            results["overall_status"] = "healthy"
        elif self.resend_enabled or not self.is_render:
            results["overall_status"] = "degraded"
        else:
            results["overall_status"] = "unhealthy"
        
        return results
    
    # ✅ GET STATS METHOD
    def get_stats(self) -> Dict[str, Any]:
        """Get email service statistics"""
        return {
            **self.stats,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "resend_enabled": self.resend_enabled,
                "is_render": self.is_render,
                "smtp_ports_available": len(self.smtp_configs)
            }
        }

# 🔁 CENTRAL RETRY WRAPPER WITH CONCURRENT PORT TESTING (keeping for compatibility)
async def send_email_with_retry(message: MessageSchema, subject: str, to_email: str) -> bool:
    """Send email using the best available SMTP port with concurrent testing"""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Find best port for this attempt
            best_config = await find_best_smtp_port()
            
            if not best_config:
                logger.error(f"❌ No working SMTP port found on attempt {attempt + 1}")
                await asyncio.sleep(retry_delay)
                continue
            
            # Send email with selected config
            fm = FastMail(best_config)
            await fm.send_message(message)
            
            logger.info(f"✅ {subject} email sent to {to_email} via port {best_config.MAIL_PORT}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt + 1} failed for {subject} to {to_email}: {str(e)}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    logger.error(f"❌ Failed to send {subject} email to {to_email} after {max_retries} attempts")
    return False

# 📧 EMAIL QUEUE SYSTEM (Decoupling PDF from Email)
class EmailQueue:
    """Simple in-memory email queue with retry logic"""
    
    def __init__(self, email_service: EmailService = None):
        self.queue = asyncio.Queue()
        self.failed_queue = asyncio.Queue()
        self.is_processing = False
        self.email_service = email_service or EmailService()
    
    async def add_email(self, message: MessageSchema, subject: str, to_email: str):
        """Add email to queue"""
        await self.queue.put({
            "message": message,
            "subject": subject,
            "to_email": to_email,
            "attempts": 0,
            "max_attempts": 3,
            "added_at": datetime.now()
        })
        logger.info(f"📨 Email queued for {to_email}: {subject}")
    
    async def process_queue(self):
        """Process email queue in background using EmailService"""
        if self.is_processing:
            return
        
        self.is_processing = True
        logger.info("🚀 Starting email queue processor")
        
        while True:
            try:
                # Get email from queue (with timeout)
                try:
                    email_item = await asyncio.wait_for(self.queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    # No emails, check failed queue
                    await self.retry_failed_emails()
                    continue
                
                # Extract message details
                message = email_item["message"]
                to_email = email_item["to_email"]
                subject = email_item["subject"]
                
                # Convert attachments format if needed
                attachments = []
                if hasattr(message, 'attachments') and message.attachments:
                    for att in message.attachments:
                        if isinstance(att, dict) and 'file' in att:
                            attachments.append({
                                "filename": Path(att['file']).name,
                                "path": att['file'],
                                "content": None  # Will be read by EmailService
                            })
                
                # Send using EmailService
                result = await self.email_service.send_email_direct(
                    to_email=to_email,
                    subject=subject,
                    html_content=message.body,
                    attachments=attachments if attachments else None
                )
                
                if result.get("status") in ["success", "logged"]:
                    logger.info(f"✅ Queued email sent: {subject} to {to_email} via {result.get('provider', 'unknown')}")
                else:
                    # Move to failed queue for retry
                    email_item["attempts"] += 1
                    if email_item["attempts"] < email_item["max_attempts"]:
                        # Schedule retry with exponential backoff
                        retry_delay = 60 * (2 ** email_item["attempts"])  # 1min, 2min, 4min
                        email_item["retry_at"] = datetime.now().timestamp() + retry_delay
                        await self.failed_queue.put(email_item)
                        logger.warning(f"⚠️ Email moved to retry queue: {subject} (attempt {email_item['attempts']})")
                    else:
                        logger.error(f"❌ Email permanently failed: {subject} to {to_email}")
                
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Error in email queue processor: {str(e)}")
                await asyncio.sleep(5)
    
    async def retry_failed_emails(self):
        """Retry failed emails"""
        retry_items = []
        current_time = datetime.now().timestamp()
        
        # Collect items ready for retry
        while not self.failed_queue.empty():
            try:
                item = self.failed_queue.get_nowait()
                if item.get("retry_at", 0) <= current_time:
                    retry_items.append(item)
                else:
                    # Put back if not ready
                    await self.failed_queue.put(item)
            except asyncio.QueueEmpty:
                break
        
        # Retry collected items
        for item in retry_items:
            logger.info(f"🔄 Retrying email: {item['subject']} (attempt {item['attempts'] + 1})")
            await self.queue.put(item)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queue_size": self.queue.qsize(),
            "failed_queue_size": self.failed_queue.qsize(),
            "is_processing": self.is_processing,
            "email_service_stats": self.email_service.get_stats()
        }

# Global instances for backward compatibility
email_service = EmailService()
email_queue = EmailQueue(email_service=email_service)

# 🔑 OTP email (compatibility function)
async def send_otp_email(to_email: str, name: str, token: str, purpose: str):
    """Generic function to send OTP emails via queue"""
    try:
        canonical_purpose = normalize_purpose(purpose)

        if canonical_purpose == "signup":
            subject = "Marshal Core - Verify Your Account"
            template = "signup_otp.html"
        elif canonical_purpose == "login":
            subject = "Marshal Core - Login Verification"
            template = "login_otp.html"
        elif canonical_purpose == "password_reset":
            subject = "Marshal Core - Password Reset"
            template = "reset_password.html"
        elif canonical_purpose == "officer_signup":
            subject = "Marshal Core - Officer Account Verification"
            template = "officer_signup_otp.html"
        else:
            subject = "Marshal Core - Verification Code"
            template = "generic_otp.html"

        html = env.get_template(template).render(name=name, token=token)

        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=html,
            subtype="html"
        )

        # Queue email instead of sending directly
        await email_queue.add_email(message, subject, to_email)
        return True
        
    except Exception as e:
        logger.error(f"Failed to build OTP email for {to_email}: {str(e)}")
        # Still return True to not block user flow
        return True

# ♻️ Reuse retry for other emails (compatibility functions)
async def send_password_reset_email(to_email: str, name: str, token: str):
    html = env.get_template("reset_password.html").render(name=name, token=token)
    message = MessageSchema(
        subject="Marshal Core - Password Reset",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Password Reset", to_email)
    return True

async def send_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Received",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Application Confirmation", to_email)
    return True

async def send_application_password_email(to_email: str, name: str, password: str):
    html = env.get_template("application_password.html").render(name=name, password=password)
    message = MessageSchema(
        subject="Your Marshal Core Application Password",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Application Password", to_email)
    return True

async def send_guarantor_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Submitted Successfully",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Guarantor Confirmation", to_email)
    return True

# NEW: PDF Email Functions - DECOUPLED VERSION
async def send_pdfs_email(
    to_email: str, 
    name: str, 
    terms_pdf_path: str, 
    application_pdf_path: str,
    cc_email: Optional[str] = None
) -> bool:
    """
    Queue PDF email for sending (decoupled from PDF generation)
    """
    try:
        logger.info(f"📨 Queueing PDFs email to: {to_email}")
        
        # Prepare HTML content
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .button {{ display: inline-block; background-color: #1a237e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 10px 5px; }}
                .document-list {{ background: white; padding: 15px; border-left: 4px solid #1a237e; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Marshal Core Nigeria</h1>
                    <h2>Officer Registration Documents</h2>
                </div>
                
                <div class="content">
                    <h3>Dear {name},</h3>
                    
                    <p>Thank you for completing your application with Marshal Core Nigeria. Your application documents have been generated and are attached to this email.</p>
                    
                    <div class="document-list">
                        <h4>📎 Attached Documents:</h4>
                        <ol>
                            <li><strong>Terms & Conditions</strong> - Official terms and conditions for Marshal Core Nigeria officers</li>
                            <li><strong>Application Form</strong> - Your completed registration form</li>
                        </ol>
                    </div>
                    
                    <p>Please keep these documents safe as they are required for official records and future reference.</p>
                    
                    <p><strong>Next Steps:</strong></p>
                    <ul>
                        <li>Save the attached PDFs to your device</li>
                        <li>Print copies for your personal records</li>
                        <li>Login to your dashboard to track your registration status</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact our support team.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://marshal-core-frontend.onrender.com/existing-officer-login.html" class="button">Login to Dashboard</a>
                        <a href="https://marshal-core-frontend.onrender.com/contact.html" class="button" style="background-color: #4CAF50;">Contact Support</a>
                    </div>
                    
                    <p>Best regards,<br>
                    <strong>Marshal Core Nigeria Admin Team</strong></p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>© 2024 Marshal Core Nigeria. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Prepare recipients
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        
        # Create message with attachments
        message = MessageSchema(
            subject="Your Marshal Core Application Documents",
            recipients=recipients,
            body=html,
            subtype="html",
            attachments=[
                {
                    "file": terms_pdf_path,
                    "headers": {
                        "Content-Disposition": f'attachment; filename="{Path(terms_pdf_path).name}"'
                    }
                },
                {
                    "file": application_pdf_path,
                    "headers": {
                        "Content-Disposition": f'attachment; filename="{Path(application_pdf_path).name}"'
                    }
                }
            ]
        )
        
        # Queue email (decoupled from PDF generation)
        await email_queue.add_email(message, "Application Documents", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to queue PDFs email for {to_email}: {str(e)}")
        # Return True to not block PDF generation
        return True

# In app/services/email_service.py, update this function:

async def send_existing_officer_pdfs_email(
    to_email: str,
    name: str,
    officer_id: str,
    terms_pdf_path: str = None,
    registration_pdf_path: str = None,
    cc_email: Optional[str] = None
) -> bool:
    """
    Send existing officer PDFs email with DIRECT DOWNLOAD LINKS
    """
    try:
        logger.info(f"📨 Queueing PDFs email for existing officer: {to_email} (ID: {officer_id})")
        
        # ✅ CREATE PUBLIC DOWNLOAD URLs
        base_url = "https://backend-mcn-ltd.onrender.com"
        
        terms_pdf_filename = os.path.basename(terms_pdf_path) if terms_pdf_path else ""
        registration_pdf_filename = os.path.basename(registration_pdf_path) if registration_pdf_path else ""
        
        terms_pdf_url = f"{base_url}/download/pdf/{terms_pdf_filename}"
        registration_pdf_url = f"{base_url}/download/pdf/{registration_pdf_filename}"
        
        logger.info(f"✅ Generated download URLs:")
        logger.info(f"   Terms PDF: {terms_pdf_url}")
        logger.info(f"   Registration PDF: {registration_pdf_url}")
        
        # Try to use template with download links
        try:
            template = env.get_template("existing_officer_documents.html")
            html = template.render(
                name=name,
                officer_id=officer_id,
                date=datetime.now().strftime('%d %B, %Y'),
                category="Marshal Core Officer",  # You can get this from officer data
                terms_pdf_url=terms_pdf_url,
                registration_pdf_url=registration_pdf_url
            )
        except Exception as template_error:
            logger.warning(f"Template rendering failed: {str(template_error)}")
            # Fallback HTML with download links
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                    .button {{ display: inline-block; background-color: #d32f2f; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 10px 5px; font-weight: bold; }}
                    .pdf-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Marshal Core of Nigeria</h1>
                        <h2>Your Registration Documents</h2>
                    </div>
                    
                    <div class="content">
                        <h3>Dear {name},</h3>
                        
                        <p>Your registration documents for <strong>Marshal Core of Nigeria</strong> are ready.</p>
                        
                        <div class="pdf-section">
                            <h4>📥 Download Your Documents:</h4>
                            
                            <p><strong>1. Terms & Conditions PDF:</strong></p>
                            <a href="{terms_pdf_url}" class="button">
                                📄 Download Terms & Conditions
                            </a>
                            
                            <p style="margin-top: 20px;"><strong>2. Registration Form PDF:</strong></p>
                            <a href="{registration_pdf_url}" class="button">
                                📄 Download Registration Form
                            </a>
                        </div>
                        
                        <p><strong>Officer ID:</strong> {officer_id}</p>
                        <p><strong>Date:</strong> {datetime.now().strftime('%d %B, %Y')}</p>
                        
                        <p>Best regards,<br>
                        <strong>Marshal Core Nigeria Admin Team</strong></p>
                    </div>
                    
                    <div class="footer">
                        <p>© 2025 Marshal Core of Nigeria</p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # Prepare recipients
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        
        # Create message with BOTH download links AND attachments
        message_attachments = []
        
        # Add Terms PDF as attachment (optional - can remove if only want links)
        if terms_pdf_path and os.path.exists(terms_pdf_path):
            message_attachments.append({
                "file": terms_pdf_path,
                "headers": {
                    "Content-Disposition": f'attachment; filename="Marshal_Core_Terms_{officer_id}.pdf"'
                }
            })
        
        # Add Registration PDF as attachment (optional)
        if registration_pdf_path and os.path.exists(registration_pdf_path):
            message_attachments.append({
                "file": registration_pdf_path,
                "headers": {
                    "Content-Disposition": f'attachment; filename="Marshal_Core_Registration_{officer_id}.pdf"'
                }
            })
        
        # Create message
        message = MessageSchema(
            subject=f"Marshal Core of Nigeria - Registration Documents for Officer {officer_id}",
            recipients=recipients,
            body=html,
            subtype="html",
            attachments=message_attachments if message_attachments else None
        )
        
        # Queue email
        await email_queue.add_email(message, f"Officer Documents - {officer_id}", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error queueing officer documents email: {str(e)}")
        return True

# In app/services/email_service.py, update this function too:

async def send_existing_officer_welcome_email(
    to_email: str,
    name: str,
    officer_id: str,
    category: str
) -> bool:
    """Queue welcome email for existing officer"""
    try:
        logger.info(f"Queueing welcome email for existing officer: {to_email} (ID: {officer_id})")
        
        try:
            template = env.get_template("existing_officer_welcome.html")
            html = template.render(
                name=name,
                officer_id=officer_id,
                category=category,
                date=datetime.now().strftime('%d %B, %Y')
            )
        except:
            # Fallback
            html = f"""
            <!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; background-color: #f9f9f9; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        .welcome-box {{ background: white; padding: 20px; border-radius: 8px; border: 2px solid #1a237e; margin: 20px 0; }}
        .button {{ display: inline-block; background-color: #1a237e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Marshal Core Nigeria</h1>
            <h2>Welcome to the Team!</h2>
        </div>
        
        <div class="content">
            <div class="welcome-box">
                <h2>Hello {name}!</h2>
                <p>Welcome to Marshal Core Nigeria - Your trusted security partner.</p>
                
                <p>We're excited to have you join our community of security professionals. Your existing officer account has been successfully registered and is now active.</p>
                
                <p><strong>Your Officer Details:</strong></p>
                <ul>
                    <li><strong>Officer ID:</strong> {officer_id}</li>
                    <li><strong>Category:</strong> {category}</li>
                    <li><strong>Registration Date:</strong> {datetime.now().strftime('%d %B, %Y')}</li>
                </ul>
                
                <p><strong>What's next?</strong></p>
                <ul>
                    <li>Your registration documents (Terms & Conditions and Registration Form) are being generated</li>
                    <li>You will receive them via email shortly</li>
                    <li>Login to your dashboard to track your registration status</li>
                    <li>Upload any missing required documents</li>
                </ul>
                
                <p>You can now login to your dashboard using your Officer ID:</p>
                
                <div style="text-align: center;">
                    <a href="https://marshal-core-frontend.onrender.com/existing-officer-login.html" class="button">Go to Dashboard</a>
                </div>
            </div>
            
            <p>If you have any questions or need assistance, our support team is here to help.</p>
            
            <p>Best regards,<br>
            <strong>The Marshal Core Nigeria Team</strong></p>
        </div>
        
        <div class="footer">
            <p>This is an automated welcome email.</p>
            <p>© {datetime.now().year} Marshal Core Nigeria. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
            """
        
        message = MessageSchema(
            subject=f"Welcome to Marshal Core Nigeria - Officer {officer_id}",
            recipients=[to_email],
            body=html,
            subtype="html"
        )
        
        await email_queue.add_email(message, f"Existing Officer Welcome - {officer_id}", to_email)
        return True
        
    except Exception as e:
        logger.error(f"Error queueing welcome email: {str(e)}")
        return True

# PAYMENT RECEIPT EMAIL - ADDED THIS FUNCTION
async def send_payment_receipt_email(
    to_email: str,
    name: str,
    payment_reference: str,
    amount: int,
    payment_type: str,
    paid_at: datetime = None,
    payment_method: str = None
) -> bool:
    """
    Send payment receipt email
    """
    try:
        logger.info(f"Queueing payment receipt email to: {to_email}")
        
        # Format the date
        payment_date = paid_at.strftime('%d %B, %Y %I:%M %p') if paid_at else datetime.now().strftime('%d %B, %Y %I:%M %p')
        
        # Try to use template if available
        try:
            template = env.get_template("payment_receipt.html")
            html = template.render(
                name=name,
                payment_reference=payment_reference,
                amount=amount,
                payment_type=payment_type,
                payment_date=payment_date,
                payment_method=payment_method or "Online Payment"
            )
        except Exception as template_error:
            logger.warning(f"Payment receipt template not found: {str(template_error)}")
            # Fallback HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .receipt {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                    .amount {{ font-size: 24px; color: #1a237e; font-weight: bold; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Marshal Core Nigeria</h1>
                        <h2>Payment Receipt</h2>
                    </div>
                    
                    <div class="content">
                        <h3>Dear {name},</h3>
                        
                        <p>Thank you for your payment. Your transaction has been completed successfully.</p>
                        
                        <div class="receipt">
                            <h4>Payment Details:</h4>
                            <p><strong>Reference Number:</strong> {payment_reference}</p>
                            <p><strong>Payment Type:</strong> {payment_type}</p>
                            <p><strong>Payment Method:</strong> {payment_method or 'Online Payment'}</p>
                            <p><strong>Date:</strong> {payment_date}</p>
                            <p><strong>Amount:</strong> <span class="amount">₦{amount:,.2f}</span></p>
                            <p><strong>Status:</strong> <span style="color: #4CAF50; font-weight: bold;">✓ Completed</span></p>
                        </div>
                        
                        <p>This receipt confirms that your payment has been received and processed successfully.</p>
                        
                        <p>Please keep this receipt for your records. You can also download it from your dashboard.</p>
                        
                        <p>If you have any questions about this payment, please contact our support team.</p>
                        
                        <p>Best regards,<br>
                        <strong>Marshal Core Nigeria Finance Team</strong></p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated email. Please do not reply to this message.</p>
                        <p>© 2024 Marshal Core Nigeria. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # Create message
        message = MessageSchema(
            subject=f"Payment Receipt - {payment_reference}",
            recipients=[to_email],
            body=html,
            subtype="html"
        )
        
        # Queue email
        await email_queue.add_email(message, "Payment Receipt", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to queue payment receipt email for {to_email}: {str(e)}")
        # Return True to not block payment flow
        return True

# 🚀 Start email queue processor on module import
async def start_email_queue():
    """Start the email queue processor"""
    asyncio.create_task(email_queue.process_queue())
    logger.info("📧 Email queue processor started")

# Initialize when module is imported
import asyncio
loop = asyncio.get_event_loop()
if loop.is_running():
    asyncio.create_task(start_email_queue())
else:
    loop.run_until_complete(start_email_queue())