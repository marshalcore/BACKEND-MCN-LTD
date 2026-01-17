import asyncio
import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

class KeepAliveService:
    """
    Keep-alive service to prevent Render.com from sleeping
    Pings endpoints every 4 minutes (240 seconds)
    """
    
    _instance = None
    _is_running = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KeepAliveService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # Determine the base URL
            if os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER"):
                # On Render.com production
                self.base_url = os.getenv("RENDER_EXTERNAL_URL", "https://backend-mcn-ltd.onrender.com")
            else:
                # Local development
                self.base_url = "http://localhost:8000"
                
            # Endpoints to ping - ALL THESE NOW SUPPORT HEAD REQUESTS
            self.endpoints = [
                "/",  # Root endpoint - now has HEAD support
                "/health",  # Health check - now has HEAD support
                "/pdf/status",  # PDF status - now has HEAD support
                "/api/health",  # Enhanced health - has HEAD support
            ]
            
            self.ping_interval = 240  # 4 minutes
            self.timeout = 10  # seconds
            self.task = None
            self.client = None
            self.stats = {
                "total_pings": 0,
                "successful_pings": 0,
                "failed_pings": 0,
                "last_ping": None,
                "started_at": datetime.now()
            }
            self._initialized = True
    
    async def initialize_client(self):
        """Initialize HTTP client"""
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "MarshalCore-KeepAlive/1.0"
                }
            )
    
    async def ping_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """Ping a single endpoint using GET method"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            await self.initialize_client()
            
            # USE GET METHOD - works for all endpoints
            response = await self.client.get(url)
            elapsed = response.elapsed.total_seconds() * 1000
            
            # Consider 2xx and 3xx as successful
            if response.status_code < 400:
                return {
                    "endpoint": endpoint,
                    "status": "success",
                    "status_code": response.status_code,
                    "response_time_ms": elapsed,
                    "method_used": "GET",
                    "timestamp": datetime.now()
                }
            elif response.status_code == 405:
                # Method not allowed - should not happen with GET
                return {
                    "endpoint": endpoint,
                    "status": "method_not_allowed",
                    "status_code": response.status_code,
                    "method_used": "GET",
                    "timestamp": datetime.now()
                }
            else:
                return {
                    "endpoint": endpoint,
                    "status": "warning",
                    "status_code": response.status_code,
                    "response_time_ms": elapsed,
                    "method_used": "GET",
                    "timestamp": datetime.now()
                }
                
        except httpx.ConnectError:
            # This is expected when pinging production from localhost
            if "localhost" in self.base_url and "render.com" in url:
                return {
                    "endpoint": endpoint,
                    "status": "skipped",
                    "reason": "local_testing",
                    "timestamp": datetime.now()
                }
            else:
                return {
                    "endpoint": endpoint,
                    "status": "connection_error",
                    "timestamp": datetime.now()
                }
        except httpx.RequestError as e:
            return {
                "endpoint": endpoint,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now()
            }
        except Exception as e:
            return {
                "endpoint": endpoint,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    async def ping_all_endpoints(self):
        """Ping all endpoints concurrently"""
        self.stats["last_ping"] = datetime.now()
        
        tasks = [self.ping_endpoint(endpoint) for endpoint in self.endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = 0
        total_with_failures = 0
        
        for result in results:
            if isinstance(result, Exception):
                self.stats["failed_pings"] += 1
                logger.error(f"❌ Ping task failed: {str(result)}")
            elif result.get("status") == "success":
                successful += 1
                self.stats["successful_pings"] += 1
            elif result.get("status") in ["skipped"]:
                # Don't count these as failed
                pass
            else:
                self.stats["failed_pings"] += 1
                total_with_failures += 1
        
        self.stats["total_pings"] += len(self.endpoints)
        
        # Only log if there's an issue
        if successful < len(self.endpoints):
            failed_count = len(self.endpoints) - successful
            logger.info(f"📊 Keep-alive: {successful}/{len(self.endpoints)} successful ({failed_count} issues)")
        else:
            # Only log success occasionally (once every 5 successful cycles)
            import random
            if random.random() < 0.2:  # 20% chance
                logger.info(f"✅ Keep-alive: All {len(self.endpoints)} endpoints healthy")
        
        return results
    
    async def run(self):
        """Main keep-alive loop"""
        await self.initialize_client()
        self._is_running = True
        
        logger.info("🚀 Starting keep-alive service...")
        
        while self._is_running:
            try:
                await self.ping_all_endpoints()
                
                # Wait for next interval
                await asyncio.sleep(self.ping_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Keep-alive service cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in keep-alive loop: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def stop(self):
        """Stop the keep-alive service"""
        self._is_running = False
        if self.client:
            await self.client.aclose()
        logger.info("🛑 Keep-alive service stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        uptime = datetime.now() - self.stats["started_at"]
        
        success_rate = 0
        if self.stats["total_pings"] > 0:
            success_rate = (self.stats["successful_pings"] / self.stats["total_pings"]) * 100
        
        return {
            **self.stats,
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime),
            "success_rate": f"{success_rate:.1f}%",
            "is_running": self._is_running,
            "endpoints": self.endpoints,
            "base_url": self.base_url,
            "ping_interval": self.ping_interval
        }

    def start(self):
        """Start the keep-alive service"""
        if not self._is_running:
            self.task = asyncio.create_task(self.run())
            return True
        return False

# Global instance
keep_alive_service = KeepAliveService()

# Health check endpoints
async def get_keep_alive_status():
    """Get keep-alive service status"""
    return keep_alive_service.get_stats()

async def start_keep_alive_service():
    """Start the keep-alive service"""
    if keep_alive_service.start():
        logger.info("✓ Keep-alive service initialized")
    else:
        logger.info("✓ Keep-alive service already running")

async def stop_keep_alive_service():
    """Stop the keep-alive service"""
    await keep_alive_service.stop()