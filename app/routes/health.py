# app/routes/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import psutil
import datetime
import sys
import os
import logging
from typing import Dict, Any
from fastapi.responses import JSONResponse

from app.database import get_db
from app.services.keep_alive import get_keep_alive_status
from app.services.email_service import email_queue

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/health",
    tags=["Health Check"]
)

@router.get("/")  # REMOVED: methods=["GET", "HEAD"]
async def health_check(db: Session = Depends(get_db)):
    """
    Comprehensive health check with database connectivity
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "Marshal Core Backend API",
        "version": "1.0.0",
    }
    
    try:
        # 1. Database check
        try:
            db.execute(text("SELECT 1"))
            health_status["database"] = {
                "status": "connected",
                "type": "postgresql"
            }
        except Exception as e:
            health_status["database"] = {
                "status": "disconnected",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # 2. System resources
        health_status["system"] = {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else "N/A",
            "uptime_seconds": psutil.boot_time() if hasattr(psutil, 'boot_time') else "N/A"
        }
        
        # 3. Application-specific checks
        health_status["application"] = {
            "email_queue_size": email_queue.queue.qsize() if hasattr(email_queue, 'queue') else "N/A",
            "email_queue_processing": email_queue.is_processing if hasattr(email_queue, 'is_processing') else "N/A",
            "working_directory": os.getcwd(),
            "environment": os.getenv("ENVIRONMENT", "development")
        }
        
        # 4. External service status
        health_status["external_services"] = {
            "email_service": "operational",
            "payment_gateway": "operational",
            "pdf_generation": "operational"
        }
        
        # Log successful health check
        logger.info(f"Health check completed: {health_status['status']}")
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        logger.error(f"Health check failed: {e}")
    
    # For HEAD requests, return empty body with headers
    return JSONResponse(
        content=health_status,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Health-Check": "true"
        }
    )

@router.get("/detailed")  # REMOVED: methods=["GET"]
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check with more information
    """
    detailed = {
        "basic": await health_check(db),
        "keep_alive": await get_keep_alive_status(),
        "process_info": {}
    }
    
    try:
        # Process information
        process = psutil.Process()
        detailed["process_info"] = {
            "pid": process.pid,
            "name": process.name(),
            "status": process.status(),
            "create_time": datetime.datetime.fromtimestamp(process.create_time()).isoformat(),
            "cpu_times": process.cpu_times()._asdict() if hasattr(process.cpu_times(), '_asdict') else str(process.cpu_times()),
            "memory_info": process.memory_info()._asdict() if hasattr(process.memory_info(), '_asdict') else str(process.memory_info()),
            "num_threads": process.num_threads(),
        }
        
        # Network information
        detailed["network"] = {
            "hostname": os.uname().nodename if hasattr(os, 'uname') else "N/A",
        }
        
        # Directory checks
        directories_to_check = [
            "static/pdfs",
            "static/uploads",
            "templates/email",
            "templates/pdf"
        ]
        
        detailed["directories"] = {}
        for dir_path in directories_to_check:
            exists = os.path.exists(dir_path)
            writable = os.access(dir_path, os.W_OK) if exists else False
            detailed["directories"][dir_path] = {
                "exists": exists,
                "writable": writable,
                "size_mb": "N/A"
            }
            
            if exists and os.path.isdir(dir_path):
                try:
                    # Calculate directory size
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(dir_path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)
                    detailed["directories"][dir_path]["size_mb"] = f"{total_size / (1024*1024):.2f}"
                except:
                    detailed["directories"][dir_path]["size_mb"] = "error"
        
    except Exception as e:
        detailed["error"] = str(e)
        logger.error(f"Detailed health check failed: {e}")
    
    return detailed

@router.get("/ping")  # REMOVED: methods=["GET", "HEAD"]
async def ping():
    """
    Simple ping endpoint for keep-alive
    Returns minimal response
    """
    response_data = {
        "status": "pong",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "Marshal Core API"
    }
    
    return JSONResponse(
        content=response_data,
        headers={
            "Cache-Control": "no-cache",
            "X-Ping": "true"
        }
    )

@router.get("/readiness")  # REMOVED: methods=["GET", "HEAD"]
async def readiness_probe():
    """
    Readiness probe for load balancers
    """
    response_data = {
        "status": "ready",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return JSONResponse(
        content=response_data,
        headers={
            "Cache-Control": "no-cache",
            "X-Readiness": "true"
        }
    )

@router.get("/liveness")  # REMOVED: methods=["GET", "HEAD"]
async def liveness_probe():
    """
    Liveness probe for container orchestration
    """
    response_data = {
        "status": "alive",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return JSONResponse(
        content=response_data,
        headers={
            "Cache-Control": "no-cache",
            "X-Liveness": "true"
        }
    )

# If you need HEAD support, add separate HEAD methods:
@router.head("/")
async def health_check_head():
    """HEAD method for health check"""
    return JSONResponse(
        content=None,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Health-Check": "true"
        }
    )

@router.head("/ping")
async def ping_head():
    """HEAD method for ping"""
    return JSONResponse(
        content=None,
        headers={
            "Cache-Control": "no-cache",
            "X-Ping": "true"
        }
    )

@router.head("/readiness")
async def readiness_head():
    """HEAD method for readiness"""
    return JSONResponse(
        content=None,
        headers={
            "Cache-Control": "no-cache",
            "X-Readiness": "true"
        }
    )

@router.head("/liveness")
async def liveness_head():
    """HEAD method for liveness"""
    return JSONResponse(
        content=None,
        headers={
            "Cache-Control": "no-cache",
            "X-Liveness": "true"
        }
    )