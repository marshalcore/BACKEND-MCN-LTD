"""
Admin API endpoints for manual payment recovery.
These endpoints allow admins to fix payment issues where Paystack confirmed payment
but the system failed to record it properly.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import secrets
import string
import logging
import os

from app.database import get_db
from app.models import PreApplicant, Payment, Applicant
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-recovery"])

def generate_password(length=6):
    """Generate a random alphanumeric password"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def send_recovery_email(email: str, password: str, verification_link: str, full_name: str = None):
    """Send payment recovery email to user"""
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        
        # Read email template
        template_path = os.path.join(
            os.path.dirname(__file__), 
            "../../templates/email/payment_recovery.html"
        )
        
        with open(template_path, 'r') as f:
            email_html = f.read()
        
        # Replace placeholders
        email_html = email_html.replace("{{EMAIL}}", email)
        email_html = email_html.replace("{{PASSWORD}}", password)
        email_html = email_html.replace("{{VERIFICATION_LINK}}", verification_link)
        
        if full_name:
            email_html = email_html.replace("Dear Applicant,", f"Dear {full_name},")
        
        # Send email
        email_service.send_email(
            to_email=email,
            subject="Payment Recovery - Marshal Core of Nigeria VIP Application",
            html_content=email_html
        )
        
        logger.info(f"📧 Recovery email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send recovery email: {str(e)}")
        return False

class PaymentRecoveryRequest(BaseModel):
    email: str
    paystack_reference: str
    amount: int  # in kobo (e.g., 2590000 for ₦25,900)
    payment_type: str  # regular or vip
    full_name: Optional[str] = None

class PasswordRecoveryRequest(BaseModel):
    email: str

@router.post("/recover-payment")
async def recover_payment(
    request: PaymentRecoveryRequest,
    db: Session = Depends(get_db)
):
    """
    Manually mark a payment as paid when Paystack confirmed but system didn't record it.
    
    This creates a payment record and marks the pre-applicant as paid.
    """
    try:
        # Find pre-applicant
        pre_applicant = db.query(PreApplicant).filter(
            PreApplicant.email == request.email.lower()
        ).first()
        
        if not pre_applicant:
            raise HTTPException(status_code=404, detail="Pre-applicant not found")
        
        # Store pre_applicant_id as string (avoid UUID serialization issues)
        pre_applicant_id = str(pre_applicant.id)
        
        # Check if payment already exists
        existing_payment = db.query(Payment).filter(
            Payment.paystack_reference == request.paystack_reference
        ).first()
        
        payment_ref = None
        if existing_payment:
            if existing_payment.status == "success":
                return {
                    "status": "already_recovered",
                    "message": "Payment already marked as paid",
                    "payment_reference": existing_payment.payment_reference
                }
            # Update existing payment
            existing_payment.status = "success"
            existing_payment.paid_at = datetime.utcnow()
            payment_ref = existing_payment.payment_reference
            logger.info(f"✅ Updated existing payment to success: {existing_payment.payment_reference}")
        else:
            # Create new payment record
            payment_ref = f"MCN_{request.payment_type.upper()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            payment = Payment(
                id=str(uuid.uuid4()),
                user_email=request.email.lower(),
                user_type="pre_applicant",
                amount=request.amount // 100,  # Convert kobo to naira
                payment_type=request.payment_type,
                status="success",
                payment_reference=payment_ref,
                paystack_reference=request.paystack_reference,
                paid_at=datetime.utcnow(),
                immediate_transfers_processed=True
            )
            db.add(payment)
            logger.info(f"✅ Created recovery payment: {payment_ref}")
        
        # Mark pre-applicant as paid
        pre_applicant.has_paid = True
        pre_applicant.status = "paid"
        pre_applicant.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Payment marked as paid for {request.email}",
            "payment_type": request.payment_type,
            "payment_reference": payment_ref,
            "pre_applicant_id": pre_applicant_id,
            "next_step": "Generate password and send recovery email"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Payment recovery failed: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-password")
async def generate_password_recovery(
    request: PasswordRecoveryRequest,
    send_email: bool = True,
    db: Session = Depends(get_db)
):
    """
    Generate a new password for a user whose payment was manually recovered.
    Sends a recovery email with verification link.
    """
    try:
        # Find pre-applicant
        pre_applicant = db.query(PreApplicant).filter(
            PreApplicant.email == request.email.lower()
        ).first()
        
        if not pre_applicant:
            raise HTTPException(status_code=404, detail="Pre-applicant not found")
        
        if not pre_applicant.has_paid:
            raise HTTPException(
                status_code=400, 
                detail="User has not paid. Cannot generate password."
            )
        
        # Store values as strings (avoid UUID serialization issues)
        pre_applicant_id = str(pre_applicant.id)
        pre_applicant_email = pre_applicant.email
        pre_applicant_full_name = pre_applicant.full_name
        
        # Generate password
        password = generate_password()
        
        # Store hashed password
        from app.utils.hash import hash_password
        pre_applicant.password = hash_password(password)
        pre_applicant.password_generated = True
        pre_applicant.password_sent = True
        pre_applicant.password_sent_at = datetime.utcnow()
        pre_applicant.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Generate verification token
        from app.utils.jwt_handler import create_access_token
        token = create_access_token({
            "sub": pre_applicant_id,
            "email": pre_applicant_email,
            "type": "password_verification",
            "password": password  # Include password in token for verification
        })
        
        verification_link = f"https://marshalcoreofnigeria.ng/apply.html?verify=true&token={token}"
        
        # Send recovery email
        if send_email:
            send_recovery_email(
                email=pre_applicant_email,
                password=password,
                verification_link=verification_link,
                full_name=pre_applicant_full_name
            )
        
        logger.info(f"📧 Password generated for {pre_applicant_email}: {password}")
        
        return {
            "status": "success",
            "message": "Password generated successfully",
            "email": pre_applicant_email,
            "verification_token": token,
            "verification_link": verification_link,
            "email_sent": send_email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Password generation failed: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/full-recovery")
async def full_recovery(
    request: PaymentRecoveryRequest,
    db: Session = Depends(get_db)
):
    """
    Complete recovery: mark payment as paid AND generate password in one call.
    Sends a recovery email to the user with password and verification link.
    """
    try:
        # Step 1: Recover payment
        recover_response = await recover_payment(request, db)
        
        if recover_response["status"] == "already_recovered":
            # Payment already recovered, just generate password
            pass
        elif recover_response["status"] != "success":
            raise HTTPException(status_code=400, detail=recover_response.get("message"))
        
        # Step 2: Generate password and send email
        password_response = await generate_password_recovery(
            PasswordRecoveryRequest(email=request.email),
            send_email=True,
            db=db
        )
        
        return {
            "status": "success",
            "message": f"Full recovery completed for {request.email}",
            "payment_type": request.payment_type,
            "email": request.email,
            "verification_link": password_response["verification_link"],
            "email_sent": True,
            "note": "Recovery email sent to user with password and verification link"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Full recovery failed: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-email")
async def test_email(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Test endpoint to verify email service is working.
    Sends a simple test email to the specified address.
    """
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        
        test_html = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #1a237e;">✅ Email Service Test</h2>
            <p>This is a test email from <strong>Marshal Core of Nigeria</strong>.</p>
            <p>If you received this email, the email service is working correctly!</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Sent at: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
            </p>
        </body>
        </html>
        """
        
        # Use send_email_direct to get detailed results
        result = await email_service.send_email_direct(
            to_email=email,
            subject="✅ Test Email - Marshal Core of Nigeria",
            html_content=test_html
        )
        
        logger.info(f"📧 Email test result: {result}")
        
        if result.get("status") == "success":
            logger.info(f"✅ Test email sent to {email}")
            return {
                "status": "success",
                "message": f"Test email sent to {email}",
                "email": email,
                "provider": result.get("provider"),
                "details": result
            }
        else:
            logger.error(f"❌ Failed to send test email to {email}: {result}")
            return {
                "status": "failed",
                "message": f"Failed to send test email to {email}",
                "email": email,
                "provider": result.get("provider"),
                "details": result
            }
            
    except Exception as e:
        logger.error(f"❌ Test email error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/email-status")
async def email_status():
    """
    Check email service configuration and status.
    """
    try:
        from app.services.email_service import EmailService
        from app.config import settings
        
        email_service = EmailService()
        stats = email_service.get_stats()
        
        # Check environment variables
        import os
        resend_key = os.getenv("RESEND_API_KEY", "")
        resend_from = os.getenv("RESEND_FROM_EMAIL", "")
        
        return {
            "status": "ok",
            "email_service_config": {
                "resend_enabled": stats.get("config", {}).get("resend_enabled", False),
                "is_render": stats.get("config", {}).get("is_render", False),
                "smtp_available": stats.get("config", {}).get("smtp_ports_available", 0) > 0,
            },
            "environment_variables": {
                "RESEND_API_KEY_SET": bool(resend_key),
                "RESEND_API_KEY_PREFIX": resend_key[:10] + "..." if resend_key else "NOT SET",
                "RESEND_FROM_EMAIL": resend_from,
            },
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"❌ Email status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
