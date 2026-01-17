# app/services/keep_alive.py
import asyncio
import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any
import os
import time

logger = logging.getLogger(__name__)

class KeepAliveService:
    """
    Keep-alive service to prevent Render.com from sleeping
    Pings endpoints every 10 minutes (600 seconds) - SAFER than 15 minutes
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
            # Determine if we're on Render.com or local
            is_render = os.getenv("RENDER") == "true" or "render.com" in os.getenv("RENDER_EXTERNAL_URL", "")
            
            if is_render:
                # Use Render's external URL
                self.base_url = os.getenv("RENDER_EXTERNAL_URL", "https://backend-mcn-ltd.onrender.com")
                logger.info(f"🌐 Render.com deployment detected: {self.base_url}")
            else:
                # Local development
                self.base_url = "http://localhost:8000"
                logger.info(f"💻 Local development: {self.base_url}")
            
            # Ping multiple endpoints to ensure activity
            self.endpoints = [
                "/",  # Root endpoint
                "/health",  # Health check
                "/api/health",  # API health
                "/pdf/status",  # PDF status
                "/api/health/ping",  # Simple ping endpoint
            ]
            
            # CRITICAL: Ping every 10 minutes (600 seconds) for Render.com
            # Render sleeps after 15 minutes, so 10 minutes gives us 5-minute safety margin
            self.ping_interval = 600  # 10 minutes
            
            self.timeout = 30  # Longer timeout for cold starts
            self.task = None
            self.client = None
            self._initialized = True
            self.stats = {
                "total_pings": 0,
                "successful_pings": 0,
                "failed_pings": 0,
                "last_ping": None,
                "started_at": datetime.now(),
                "next_ping": None,
                "is_render": is_render
            }
    
    async def initialize_client(self):
        """Initialize HTTP client with longer timeout for cold starts"""
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "MarshalCore-KeepAlive/1.0",
                    "Accept": "application/json",
                    "X-Keep-Alive": "true"
                }
            )
    
    async def ping_endpoint(self, endpoint: str):
        """Ping a single endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            await self.initialize_client()
            
            # Use GET - most reliable
            start_time = time.time()
            response = await self.client.get(url)
            elapsed = time.time() - start_time
            
            if response.status_code < 400:
                return {
                    "endpoint": endpoint,
                    "status": "success",
                    "status_code": response.status_code,
                    "response_time": elapsed,
                    "timestamp": datetime.now()
                }
            else:
                logger.warning(f"⚠️ Ping warning: {endpoint} - Status {response.status_code}")
                return {
                    "endpoint": endpoint,
                    "status": "warning",
                    "status_code": response.status_code,
                    "response_time": elapsed,
                    "timestamp": datetime.now()
                }
                
        except httpx.ConnectError:
            logger.error(f"🌐 Connection error: {endpoint}")
            return {
                "endpoint": endpoint,
                "status": "connection_error",
                "timestamp": datetime.now()
            }
        except httpx.TimeoutException:
            logger.error(f"⏱️ Timeout: {endpoint}")
            return {
                "endpoint": endpoint,
                "status": "timeout",
                "timestamp": datetime.now()
            }
        except Exception as e:
            logger.error(f"❌ Error pinging {endpoint}: {str(e)}")
            return {
                "endpoint": endpoint,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    async def ping_all_endpoints(self):
        """Ping all endpoints with timing information"""
        self.stats["last_ping"] = datetime.now()
        next_ping_time = datetime.now().timestamp() + self.ping_interval
        self.stats["next_ping"] = datetime.fromtimestamp(next_ping_time)
        
        if self.stats["is_render"]:
            logger.info(f"🔔 RENDER KEEP-ALIVE: Pinging {len(self.endpoints)} endpoints...")
            logger.info(f"⏰ Next ping at: {self.stats['next_ping'].strftime('%H:%M:%S')}")
        else:
            logger.debug(f"Pinging {len(self.endpoints)} endpoints...")
        
        tasks = [self.ping_endpoint(endpoint) for endpoint in self.endpoints]
        results = await asyncio.gather(*tasks)
        
        # Count successes
        successes = sum(1 for r in results if r["status"] == "success")
        total = len(results)
        
        # Update stats
        self.stats["total_pings"] += total
        self.stats["successful_pings"] += successes
        self.stats["failed_pings"] += (total - successes)
        
        # Log results for Render
        if self.stats["is_render"]:
            if successes == total:
                logger.info(f"✅ RENDER: All {total} endpoints responded successfully")
                logger.info(f"📊 Successful pings: {self.stats['successful_pings']}, Failed: {self.stats['failed_pings']}")
            else:
                failed = [r for r in results if r["status"] != "success"]
                logger.warning(f"⚠️ RENDER: {successes}/{total} endpoints successful")
                for f in failed:
                    logger.warning(f"  ❌ {f['endpoint']}: {f.get('status', 'unknown')}")
        
        return results
    
    async def run(self):
        """Main keep-alive loop with precise timing"""
        await self.initialize_client()
        self._is_running = True
        
        if self.stats["is_render"]:
            logger.info("🚀 STARTING RENDER.COM KEEP-ALIVE SERVICE")
            logger.info(f"🎯 Target URL: {self.base_url}")
            logger.info(f"⏰ Ping interval: {self.ping_interval/60} minutes")
            logger.info(f"⚠️  Render sleeps after: 15 minutes of inactivity")
            logger.info(f"✅ Safety margin: {15 - self.ping_interval/60} minutes")
            logger.info(f"📈 Endpoints to ping: {len(self.endpoints)}")
        else:
            logger.info("🚀 Starting local keep-alive service")
        
        # Initial delay to let server fully start
        await asyncio.sleep(30)
        
        while self._is_running:
            try:
                results = await self.ping_all_endpoints()
                
                # Calculate exact sleep time
                now = datetime.now()
                if self.stats["next_ping"]:
                    sleep_seconds = max(1, (self.stats["next_ping"] - now).total_seconds())
                    
                    if self.stats["is_render"] and sleep_seconds > 60:
                        minutes = sleep_seconds / 60
                        logger.info(f"💤 Sleeping for {minutes:.1f} minutes until next ping...")
                    
                    await asyncio.sleep(sleep_seconds)
                else:
                    # Fallback
                    await asyncio.sleep(self.ping_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Keep-alive service cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Keep-alive loop error: {str(e)}")
                # Wait 1 minute before retrying on error
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the keep-alive service"""
        self._is_running = False
        if self.client:
            await self.client.aclose()
        logger.info("🛑 Keep-alive service stopped")
    
    def get_stats(self):
        """Get service statistics"""
        if not self.stats["last_ping"]:
            return {"status": "not_started"}
        
        uptime = datetime.now() - self.stats["started_at"]
        
        success_rate = 0
        if self.stats["total_pings"] > 0:
            success_rate = (self.stats["successful_pings"] / self.stats["total_pings"]) * 100
        
        # Calculate time until next ping
        next_ping_in = 0
        if self.stats["next_ping"]:
            next_ping_in = max(0, (self.stats["next_ping"] - datetime.now()).total_seconds())
        
        stats = {
            **self.stats,
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime),
            "success_rate": f"{success_rate:.1f}%",
            "is_running": self._is_running,
            "endpoints": self.endpoints,
            "base_url": self.base_url,
            "ping_interval_seconds": self.ping_interval,
            "ping_interval_minutes": self.ping_interval / 60,
            "next_ping_in_seconds": next_ping_in,
            "next_ping_in_minutes": next_ping_in / 60,
        }
        
        if self.stats["is_render"]:
            stats["render_info"] = {
                "sleep_after_minutes": 15,
                "safety_margin_minutes": 15 - (self.ping_interval / 60),
                "status": "active" if self._is_running else "inactive",
                "last_activity": self.stats["last_ping"].isoformat() if self.stats["last_ping"] else None
            }
        
        return stats

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
        return True
    return False

async def stop_keep_alive_service():
    """Stop the keep-alive service"""
    await keep_alive_service.stop()