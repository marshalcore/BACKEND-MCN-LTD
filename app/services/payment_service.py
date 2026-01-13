import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.pre_applicant import PreApplicant
from app.utils.password import generate_password
from app.services.email_service import send_application_password_email
from app.config import settings
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


async def process_payment_success(email: str, db: Session):
    """Process payment success and generate application password"""
    logger.info(f"Processing payment success for email: {email}")
    
    normalized_email = email.strip().lower()
    
    # Find pre-applicant
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()

    if not pre_applicant:
        logger.error(f"PreApplicant not found for email: {email}")
        raise HTTPException(status_code=404, detail="PreApplicant not found")

    # Check if already paid
    if pre_applicant.has_paid:
        logger.info(f"PreApplicant {email} already marked as paid")
        return {"message": "Already paid."}

    # ✅ Set payment status and update timestamps
    pre_applicant.has_paid = True
    pre_applicant.status = "payment_completed"
    
    # ✅ Generate password only if not already generated or expired
    needs_new_password = True
    
    if pre_applicant.application_password:
        # Check if existing password is still valid
        if (pre_applicant.password_expires_at and 
            pre_applicant.password_expires_at > datetime.utcnow()):
            logger.info(f"Password already valid for {email}, skipping regeneration")
            needs_new_password = False
        else:
            logger.info(f"Existing password expired for {email}, generating new one")
    
    if needs_new_password:
        password = generate_password()
        pre_applicant.application_password = password
        pre_applicant.password_generated = True
        pre_applicant.password_generated_at = datetime.utcnow()
        pre_applicant.password_expires_at = datetime.utcnow() + timedelta(hours=24)
        pre_applicant.status = "password_sent"
        
        logger.info(f"Sending password email to {email}")
        try:
            await send_application_password_email(email, pre_applicant.full_name, password)
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Payment verified but failed to send password email. Please contact support."
            )
    else:
        # Ensure status is correct for existing password
        pre_applicant.status = "password_sent"

    db.commit()
    logger.info(f"Payment processed successfully for {email}")

    return {"message": "Payment verified. Password sent if not already generated."}


def verify_paystack_payment(reference: str) -> bool:
    """Verify Paystack payment reference"""
    if not settings.PAYSTACK_SECRET_KEY:
        logger.error("Paystack secret key not configured")
        return False
    
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()

        data = response.json().get("data", {})
        logger.info(f"Paystack verification response: {data.get('status')}")
        
        return data.get("status") == "success"

    except httpx.RequestError as e:
        logger.error(f"[Paystack] Request error: {e}")
        return False
    except httpx.HTTPStatusError as e:
        logger.error(f"[Paystack] HTTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"[Paystack] Unknown error: {e}")
        return False


def verify_flutterwave_payment(reference: str) -> bool:
    """Verify Flutterwave payment reference"""
    if not settings.FLUTTERWAVE_SECRET_KEY:
        logger.error("Flutterwave secret key not configured")
        return False
    
    headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}
    url = f"https://api.flutterwave.com/v3/transactions/{reference}/verify"

    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()

        data = response.json().get("data", {})
        logger.info(f"Flutterwave verification response: {data.get('status')}")
        
        return data.get("status") == "successful"

    except httpx.RequestError as e:
        logger.error(f"[Flutterwave] Request error: {e}")
        return False
    except httpx.HTTPStatusError as e:
        logger.error(f"[Flutterwave] HTTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"[Flutterwave] Unknown error: {e}")
        return False