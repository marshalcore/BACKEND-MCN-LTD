# app/services/immediate_transfer.py - COMPLETE UPDATED VERSION FOR PRODUCTION
"""
Service to handle immediate bank transfers using Paystack LIVE Transfer API.
After each successful payment, automatically transfer:
- 35% to DG's UBA account
- 15% to eSTech's OPay account
"""
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import time
import uuid

from app.config import settings
from app.models.immediate_transfer import ImmediateTransfer
from app.models.payment import Payment

logger = logging.getLogger(__name__)

class ImmediateTransferService:
    """Service to handle immediate bank transfers with LIVE Paystack"""
    
    def __init__(self):
        self.paystack_secret = settings.PAYSTACK_SECRET_KEY
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.paystack_secret}",
            "Content-Type": "application/json"
        }
        
        # Check if we're in LIVE mode
        self.is_live_mode = not settings.PAYSTACK_TEST_MODE
        self.enable_transfers = settings.ENABLE_IMMEDIATE_TRANSFERS
        
        # Recipient configurations for LIVE transfers
        self.recipients = {
            "director_general": {
                "type": "nuban",
                "name": settings.DG_ACCOUNT_NAME,
                "account_number": settings.DG_ACCOUNT_NUMBER,
                "bank_code": settings.DG_BANK_CODE,
                "currency": "NGN",
                "description": "Director General - Marshal Core Nigeria"
            },
            "estech_system": {
                "type": "nuban",
                "name": "AUTHOR WISDOM GODWIN",  # Actual beneficiary name
                "account_number": settings.ESTECH_BANK_ACCOUNT_NUMBER,
                "bank_code": "100",  # OPay bank code
                "currency": "NGN",
                "description": settings.ESTECH_COMMISSION_PURPOSE
            }
        }
        
        logger.info(f"ImmediateTransferService initialized: {'LIVE' if self.is_live_mode else 'TEST'} mode")
        logger.info(f"Transfers enabled: {self.enable_transfers}")
        
        # Test mode validation
        if not self.is_live_mode:
            logger.warning("⚠️ WARNING: Running in TEST mode - No actual transfers will be made!")
            logger.warning("⚠️ Set PAYSTACK_TEST_MODE=false for LIVE transfers")
    
    async def create_transfer_recipient(
        self,
        recipient_type: str
    ) -> Dict[str, Any]:
        """
        Create a transfer recipient in Paystack
        Returns recipient_code for future transfers
        """
        try:
            if recipient_type not in self.recipients:
                return {
                    "status": "error",
                    "message": f"Unknown recipient type: {recipient_type}"
                }
            
            recipient_data = self.recipients[recipient_type]
            
            # In test mode, return a mock recipient code
            if not self.is_live_mode:
                logger.info(f"TEST MODE: Simulating recipient creation for {recipient_type}")
                mock_codes = {
                    "director_general": "RCP_test_dg_001",
                    "estech_system": "RCP_test_estech_001"
                }
                return {
                    "status": "success",
                    "recipient_code": mock_codes.get(recipient_type, f"RCP_test_{recipient_type}"),
                    "recipient_type": recipient_type,
                    "test_mode": True,
                    "message": "TEST MODE - No actual recipient created"
                }
            
            logger.info(f"Creating LIVE recipient for {recipient_type}: {recipient_data['account_number']}")
            
            response = httpx.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json=recipient_data,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data["status"]:
                recipient_code = data["data"]["recipient_code"]
                logger.info(f"✅ Created recipient for {recipient_type}: {recipient_code}")
                return {
                    "status": "success",
                    "recipient_code": recipient_code,
                    "recipient_type": recipient_type,
                    "account_name": data["data"]["name"],
                    "account_number": data["data"]["details"]["account_number"],
                    "bank": data["data"]["details"]["bank_name"],
                    "test_mode": False
                }
            else:
                error_msg = data.get("message", "Failed to create recipient")
                logger.error(f"❌ Paystack recipient creation failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "recipient_type": recipient_type,
                    "test_mode": False
                }
                
        except httpx.RequestError as e:
            logger.error(f"❌ Network error creating recipient: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while creating recipient",
                "recipient_type": recipient_type,
                "test_mode": False
            }
        except Exception as e:
            logger.error(f"❌ Error creating recipient: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "recipient_type": recipient_type,
                "test_mode": False
            }
    
    async def initiate_transfer(
        self,
        recipient_code: str,
        amount: int,  # Amount in kobo
        reason: str,
        recipient_type: str,
        payment_reference: str
    ) -> Dict[str, Any]:
        """
        Initiate transfer to a recipient
        """
        try:
            # Convert amount to kobo
            amount_kobo = amount
            
            # Generate unique transfer reference
            transfer_ref = f"TRF_{payment_reference}_{recipient_type}_{uuid.uuid4().hex[:8]}"
            
            transfer_data = {
                "source": "balance",
                "amount": amount_kobo,
                "recipient": recipient_code,
                "reason": reason,
                "reference": transfer_ref,
                "currency": "NGN"
            }
            
            # In test mode, simulate successful transfer
            if not self.is_live_mode:
                logger.info(f"TEST MODE: Simulating transfer of ₦{amount/100:,} to {recipient_type}")
                
                return {
                    "status": "success",
                    "transfer_code": f"TRC_TEST_{uuid.uuid4().hex[:8]}",
                    "transfer_reference": transfer_ref,
                    "amount": amount,
                    "reason": reason,
                    "recipient_type": recipient_type,
                    "test_mode": True,
                    "message": "Transfer simulated in test mode"
                }
            
            logger.info(f"🔵 Initiating LIVE transfer: ₦{amount/100:,} to {recipient_type}")
            logger.info(f"Transfer reference: {transfer_ref}")
            
            response = httpx.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json=transfer_data,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data["status"]:
                logger.info(f"✅ Transfer initiated: ₦{amount/100:,} to {recipient_type}")
                logger.info(f"Transfer code: {data['data']['transfer_code']}")
                
                return {
                    "status": "success",
                    "transfer_code": data["data"]["transfer_code"],
                    "transfer_reference": data["data"]["reference"],
                    "amount": amount,
                    "reason": reason,
                    "recipient_type": recipient_type,
                    "test_mode": False
                }
            else:
                error_msg = data.get("message", "Transfer failed")
                logger.error(f"❌ Paystack transfer failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "recipient_type": recipient_type,
                    "test_mode": False
                }
                
        except httpx.RequestError as e:
            logger.error(f"❌ Network error initiating transfer: {str(e)}")
            return {
                "status": "error",
                "message": "Network error while initiating transfer",
                "recipient_type": recipient_type,
                "test_mode": False
            }
        except Exception as e:
            logger.error(f"❌ Error initiating transfer: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "recipient_type": recipient_type,
                "test_mode": False
            }
    
    async def verify_transfer(self, transfer_code: str) -> Dict[str, Any]:
        """
        Verify transfer status
        """
        try:
            if not self.is_live_mode:
                return {
                    "status": "success",
                    "transfer_status": "success",
                    "test_mode": True,
                    "message": "TEST MODE - Transfer verified"
                }
            
            response = httpx.get(
                f"{self.base_url}/transfer/{transfer_code}",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data["status"]:
                status = data["data"]["status"]
                logger.info(f"Transfer {transfer_code} status: {status}")
                return {
                    "status": "success",
                    "transfer_status": status,
                    "amount": data["data"]["amount"] / 100,
                    "recipient": data["data"]["recipient"],
                    "transfer_code": transfer_code,
                    "test_mode": False
                }
            else:
                error_msg = data.get("message", "Transfer verification failed")
                logger.error(f"Transfer verification failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "test_mode": False
                }
                
        except Exception as e:
            logger.error(f"❌ Error verifying transfer: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "test_mode": False
            }
    
    async def process_immediate_splits(
        self,
        payment_reference: str,
        payment_amount: float,
        db: Session
    ) -> Dict[str, Any]:
        """
        Process immediate transfers to DG and eSTech after payment
        """
        try:
            if not self.enable_transfers:
                logger.info(f"Immediate transfers disabled for {payment_reference}")
                return {
                    "status": "skipped",
                    "message": "Immediate transfers are disabled",
                    "payment_reference": payment_reference
                }
            
            logger.info(f"🔵 Processing immediate splits for payment: {payment_reference}")
            
            # Get payment details
            payment = db.query(Payment).filter(
                Payment.payment_reference == payment_reference
            ).first()
            
            if not payment:
                return {
                    "status": "error",
                    "message": f"Payment not found: {payment_reference}"
                }
            
            # Check if transfers already processed
            if payment.immediate_transfers_processed:
                logger.info(f"Transfers already processed for {payment_reference}")
                return {
                    "status": "success",
                    "message": "Transfers already processed",
                    "already_processed": True,
                    "payment_reference": payment_reference
                }
            
            # Get expected transfer amounts from payment metadata
            transfer_results = []
            all_successful = True
            
            # Process Director General transfer (35%)
            dg_amount = payment.director_general_share
            if dg_amount > 0:
                logger.info(f"🔵 Transferring ₦{dg_amount:,} to Director General")
                
                # Create or get recipient code
                recipient_result = await self.create_transfer_recipient("director_general")
                
                if recipient_result.get("status") == "success":
                    # Initiate transfer
                    transfer_result = await self.initiate_transfer(
                        recipient_code=recipient_result["recipient_code"],
                        amount=int(dg_amount * 100),  # Convert to kobo
                        reason=f"Marshal Core - DG Share for {payment_reference}",
                        recipient_type="director_general",
                        payment_reference=payment_reference
                    )
                    
                    # Record transfer
                    if transfer_result.get("status") == "success":
                        transfer = ImmediateTransfer(
                            payment_reference=payment_reference,
                            recipient_type="director_general",
                            amount=dg_amount,
                            recipient_account=f"{self.recipients['director_general']['name']} - {self.recipients['director_general']['account_number']}",
                            recipient_bank=settings.DG_BANK_NAME,
                            transfer_reference=transfer_result.get("transfer_reference"),
                            status="initiated",
                            transferred_at=datetime.utcnow(),
                            paystack_transfer_code=transfer_result.get("transfer_code"),
                            paystack_response=transfer_result,
                            is_test_mode=transfer_result.get("test_mode", False)
                        )
                        db.add(transfer)
                        
                        transfer_results.append({
                            "recipient": "director_general",
                            "amount": dg_amount,
                            "status": "initiated",
                            "transfer_reference": transfer_result.get("transfer_reference"),
                            "test_mode": transfer_result.get("test_mode", False),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        logger.info(f"✅ Director General transfer initiated: ₦{dg_amount:,}")
                    else:
                        all_successful = False
                        # Record failed transfer
                        transfer = ImmediateTransfer(
                            payment_reference=payment_reference,
                            recipient_type="director_general",
                            amount=dg_amount,
                            recipient_account=f"{self.recipients['director_general']['name']} - {self.recipients['director_general']['account_number']}",
                            recipient_bank=settings.DG_BANK_NAME,
                            transfer_reference=None,
                            status="failed",
                            transferred_at=datetime.utcnow(),
                            paystack_response=transfer_result,
                            is_test_mode=True if not self.is_live_mode else False
                        )
                        db.add(transfer)
                        
                        transfer_results.append({
                            "recipient": "director_general",
                            "amount": dg_amount,
                            "status": "failed",
                            "error": transfer_result.get("message"),
                            "test_mode": True if not self.is_live_mode else False
                        })
                        logger.error(f"❌ Director General transfer failed: {transfer_result.get('message')}")
                else:
                    all_successful = False
                    transfer_results.append({
                        "recipient": "director_general",
                        "amount": dg_amount,
                        "status": "failed",
                        "error": recipient_result.get("message"),
                        "test_mode": True if not self.is_live_mode else False
                    })
                    logger.error(f"❌ Failed to create DG recipient: {recipient_result.get('message')}")
            
            # Process eSTech System transfer (15%)
            estech_amount = payment.estech_system_share
            if estech_amount > 0:
                logger.info(f"🔵 Transferring ₦{estech_amount:,} to eSTech System")
                
                recipient_result = await self.create_transfer_recipient("estech_system")
                
                if recipient_result.get("status") == "success":
                    transfer_result = await self.initiate_transfer(
                        recipient_code=recipient_result["recipient_code"],
                        amount=int(estech_amount * 100),  # Convert to kobo
                        reason=f"Marshal Core - eSTech Services for {payment_reference}",
                        recipient_type="estech_system",
                        payment_reference=payment_reference
                    )
                    
                    if transfer_result.get("status") == "success":
                        transfer = ImmediateTransfer(
                            payment_reference=payment_reference,
                            recipient_type="estech_system",
                            amount=estech_amount,
                            recipient_account=f"{self.recipients['estech_system']['name']} - {self.recipients['estech_system']['account_number']}",
                            recipient_bank=settings.ESTECH_BANK_NAME,
                            transfer_reference=transfer_result.get("transfer_reference"),
                            status="initiated",
                            transferred_at=datetime.utcnow(),
                            paystack_transfer_code=transfer_result.get("transfer_code"),
                            paystack_response=transfer_result,
                            is_test_mode=transfer_result.get("test_mode", False)
                        )
                        db.add(transfer)
                        
                        transfer_results.append({
                            "recipient": "estech_system",
                            "amount": estech_amount,
                            "status": "initiated",
                            "transfer_reference": transfer_result.get("transfer_reference"),
                            "test_mode": transfer_result.get("test_mode", False),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        logger.info(f"✅ eSTech System transfer initiated: ₦{estech_amount:,}")
                    else:
                        all_successful = False
                        # Record failed transfer
                        transfer = ImmediateTransfer(
                            payment_reference=payment_reference,
                            recipient_type="estech_system",
                            amount=estech_amount,
                            recipient_account=f"{self.recipients['estech_system']['name']} - {self.recipients['estech_system']['account_number']}",
                            recipient_bank=settings.ESTECH_BANK_NAME,
                            transfer_reference=None,
                            status="failed",
                            transferred_at=datetime.utcnow(),
                            paystack_response=transfer_result,
                            is_test_mode=True if not self.is_live_mode else False
                        )
                        db.add(transfer)
                        
                        transfer_results.append({
                            "recipient": "estech_system",
                            "amount": estech_amount,
                            "status": "failed",
                            "error": transfer_result.get("message"),
                            "test_mode": True if not self.is_live_mode else False
                        })
                        logger.error(f"❌ eSTech System transfer failed: {transfer_result.get('message')}")
                else:
                    all_successful = False
                    transfer_results.append({
                        "recipient": "estech_system",
                        "amount": estech_amount,
                        "status": "failed",
                        "error": recipient_result.get("message"),
                        "test_mode": True if not self.is_live_mode else False
                    })
                    logger.error(f"❌ Failed to create eSTech recipient: {recipient_result.get('message')}")
            
            # Update payment record
            payment.immediate_transfers_processed = all_successful
            payment.transfer_metadata = {
                "processed_at": datetime.utcnow().isoformat(),
                "transfers": transfer_results,
                "status": "completed" if all_successful else "partial_failure",
                "is_live_mode": self.is_live_mode
            }
            
            db.commit()
            
            if all_successful:
                logger.info(f"✅✅✅ ALL immediate transfers processed for {payment_reference}")
                return {
                    "status": "success",
                    "message": "All transfers processed successfully",
                    "payment_reference": payment_reference,
                    "transfers": transfer_results,
                    "all_successful": True,
                    "is_live_mode": self.is_live_mode
                }
            else:
                logger.warning(f"⚠️ Some transfers failed for {payment_reference}")
                return {
                    "status": "partial",
                    "message": "Some transfers failed",
                    "payment_reference": payment_reference,
                    "transfers": transfer_results,
                    "all_successful": False,
                    "is_live_mode": self.is_live_mode
                }
            
        except Exception as e:
            logger.error(f"❌❌❌ Error processing immediate splits: {str(e)}", exc_info=True)
            
            # Update payment with error
            if payment:
                payment.transfer_metadata = {
                    "processed_at": datetime.utcnow().isoformat(),
                    "error": str(e),
                    "status": "error",
                    "is_live_mode": self.is_live_mode
                }
                try:
                    db.commit()
                except:
                    db.rollback()
            
            return {
                "status": "error",
                "message": str(e),
                "payment_reference": payment_reference,
                "is_live_mode": self.is_live_mode
            }
    
    async def retry_failed_transfers(
        self,
        payment_reference: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Retry failed transfers for a payment
        """
        try:
            if not self.enable_transfers:
                return {
                    "status": "skipped",
                    "message": "Immediate transfers are disabled"
                }
            
            # Get failed transfers for this payment
            failed_transfers = db.query(ImmediateTransfer).filter(
                ImmediateTransfer.payment_reference == payment_reference,
                ImmediateTransfer.status.in_(["failed", "pending"])
            ).all()
            
            if not failed_transfers:
                return {
                    "status": "success",
                    "message": "No failed transfers found"
                }
            
            logger.info(f"🔄 Retrying {len(failed_transfers)} failed transfers for {payment_reference}")
            
            retry_results = []
            
            for transfer in failed_transfers:
                logger.info(f"🔄 Retrying transfer: {transfer.recipient_type} - ₦{transfer.amount:,}")
                
                # Determine recipient type
                recipient_type = transfer.recipient_type
                
                # Get recipient code
                recipient_result = await self.create_transfer_recipient(recipient_type)
                
                if recipient_result.get("status") == "success":
                    # Retry transfer
                    transfer_result = await self.initiate_transfer(
                        recipient_code=recipient_result["recipient_code"],
                        amount=int(transfer.amount * 100),
                        reason=f"Marshal Core - Retry {recipient_type} share for {payment_reference}",
                        recipient_type=recipient_type,
                        payment_reference=payment_reference
                    )
                    
                    if transfer_result.get("status") == "success":
                        transfer.status = "retried"
                        transfer.transfer_reference = transfer_result.get("transfer_reference")
                        transfer.transferred_at = datetime.utcnow()
                        transfer.retry_count = (transfer.retry_count or 0) + 1
                        transfer.last_retry_at = datetime.utcnow()
                        transfer.paystack_transfer_code = transfer_result.get("transfer_code")
                        transfer.paystack_response = transfer_result
                        transfer.is_test_mode = transfer_result.get("test_mode", False)
                        
                        retry_results.append({
                            "recipient_type": recipient_type,
                            "amount": transfer.amount,
                            "status": "success",
                            "new_reference": transfer_result.get("transfer_reference"),
                            "test_mode": transfer_result.get("test_mode", False)
                        })
                        logger.info(f"✅ Retry successful for {recipient_type}")
                    else:
                        transfer.retry_count = (transfer.retry_count or 0) + 1
                        transfer.last_retry_at = datetime.utcnow()
                        retry_results.append({
                            "recipient_type": recipient_type,
                            "amount": transfer.amount,
                            "status": "failed",
                            "error": transfer_result.get("message"),
                            "test_mode": transfer_result.get("test_mode", False)
                        })
                        logger.error(f"❌ Retry failed for {recipient_type}: {transfer_result.get('message')}")
                else:
                    transfer.retry_count = (transfer.retry_count or 0) + 1
                    transfer.last_retry_at = datetime.utcnow()
                    retry_results.append({
                        "recipient_type": recipient_type,
                        "amount": transfer.amount,
                        "status": "failed",
                        "error": recipient_result.get("message"),
                        "test_mode": recipient_result.get("test_mode", False)
                    })
                    logger.error(f"❌ Recipient creation failed for retry: {recipient_result.get('message')}")
            
            db.commit()
            
            # Check if all retries succeeded
            all_retried = all(r["status"] == "success" for r in retry_results)
            if all_retried:
                # Update payment record
                payment = db.query(Payment).filter(
                    Payment.payment_reference == payment_reference
                ).first()
                if payment:
                    payment.immediate_transfers_processed = True
                    payment.transfer_metadata = {
                        "retried_at": datetime.utcnow().isoformat(),
                        "retry_results": retry_results,
                        "status": "completed_after_retry",
                        "is_live_mode": self.is_live_mode
                    }
                    db.commit()
                    logger.info(f"✅ All retries successful for {payment_reference}")
            
            return {
                "status": "success",
                "message": f"Retried {len(failed_transfers)} transfers",
                "results": retry_results,
                "all_successful": all_retried,
                "is_live_mode": self.is_live_mode
            }
            
        except Exception as e:
            logger.error(f"❌ Error retrying transfers: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "is_live_mode": self.is_live_mode
            }
    
    async def check_transfer_balance(self) -> Dict[str, Any]:
        """
        Check Paystack transfer balance
        """
        try:
            if not self.is_live_mode:
                return {
                    "status": "success",
                    "balance": 1000000.00,
                    "currency": "NGN",
                    "test_mode": True,
                    "message": "TEST MODE - Mock balance"
                }
            
            response = httpx.get(
                f"{self.base_url}/balance",
                headers=self.headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status"):
                balance = data["data"][0]["balance"] / 100
                logger.info(f"💰 Paystack transfer balance: ₦{balance:,.2f}")
                return {
                    "status": "success",
                    "balance": balance,
                    "currency": data["data"][0]["currency"],
                    "test_mode": False
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Failed to check balance"),
                    "test_mode": False
                }
                
        except Exception as e:
            logger.error(f"❌ Error checking transfer balance: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "test_mode": False if self.is_live_mode else True
            }