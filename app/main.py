from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
import os
import logging
import datetime
import asyncio

# Init app
app = FastAPI(title="Marshal Core Backend")

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS Setup - Enhanced Configuration
origins = [
    "http://localhost",
    "http://localhost:5500",
    "http://localhost:5501",
    "http://localhost:5502",
    "http://127.0.0.1",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5501",
    "http://127.0.0.1:5502",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://marshalcoreofnigeria.ng",
    "https://marshalcoreofnigeria.ng",
    "https://backend-mcn-ltd.onrender.com",  
    "https://marshalcoreofficer.netlify.app",
    "https://mcn-org.netlify.app",
    "https://marshalcoreofnigerialimited.netlify.app",
    "https://marshalcoreadmin.netlify.app", 
]

# Use ONLY FastAPI's CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)

# Static Files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Static files mounted at /static from {STATIC_DIR}")
else:
    logger.warning(f"Static directory not found at {STATIC_DIR}")
    os.makedirs(STATIC_DIR, exist_ok=True)
    logger.info(f"Created static directory at {STATIC_DIR}")

# Custom OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Marshal Core API - Admin, Officer, and Applicant Management System",
        routes=app.routes,
    )
    
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter JWT token in the format: Bearer <token>"
    }

    for path_name, path_item in openapi_schema["paths"].items():
        if any(public_path in path_name for public_path in ["/login", "/signup", "/health", "/docs", "/redoc", "/openapi.json"]):
            continue
            
        for method_name, method_item in path_item.items():
            if method_name in ["get", "post", "put", "delete", "patch"]:
                method_item.setdefault("security", []).append({"BearerAuth": []})

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Route Registrations - Import all routers
from app.routes.pre_register import router as pre_register_router
from app.routes.payment import router as payment_router
from app.routes.application_access import router as application_access_router
from app.routes.application_form import router as application_form_router
from app.routes.form_submission import router as form_submission_router
from app.routes.officer_auth import router as officer_auth_router
from app.routes.password_reset import router as password_reset_router
from app.routes.admin_auth import router as admin_router
from app.routes.officer_uploads import router as officer_uploads_router
from app.routes.officer_dashboard import router as officer_dashboard_router
from app.routes.existing_officer import router as existing_officer_router
from app.routes.existing_officer_dashboard import router as existing_officer_dashboard_router
from app.routes.pdf_download import router as pdf_download_router
from app.routes.health import router as health_router

# Include all routers
routers = [
    pre_register_router,
    payment_router,
    application_access_router,
    application_form_router,
    form_submission_router,
    officer_auth_router,
    password_reset_router,
    admin_router,
    officer_uploads_router,
    officer_dashboard_router,
    existing_officer_router,               
    existing_officer_dashboard_router,     
    pdf_download_router,
    health_router
]

for router in routers:
    app.include_router(router)
    logger.info(f"Included router: {router.prefix}")

# Root endpoint with HEAD support
@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
async def root():
    return {
        "status": "ok",
        "message": "Welcome to Marshal Core of Nigeria Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": [
            "/admin/* - Admin authentication and management",
            "/officer/* - Officer routes",
            "/api/existing-officers/* - Existing officers registration (no payment)",
            "/applicant/* - Applicant routes",
            "/payment/* - Payment processing",
            "/pdf/* - PDF document download and management",
            "/health - System health check",
            "/api/health - Enhanced health check with keep-alive"
        ]
    }

# File download route with CORS support
@app.get("/download/pdf/{filename}", tags=["Public Downloads"])
async def download_pdf(filename: str, request: Request):
    """
    Public endpoint to download PDF files
    """
    # Security check - prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Check in multiple directories
    possible_paths = [
        os.path.join(STATIC_DIR, "pdfs", filename),
        os.path.join(STATIC_DIR, "pdfs", "terms", filename),
        os.path.join(STATIC_DIR, "pdfs", "applications", filename),
    ]
    
    pdf_path = None
    for path in possible_paths:
        if os.path.isfile(path):
            pdf_path = path
            break
    
    if not pdf_path:
        # Try with .pdf extension if not provided
        if not filename.endswith('.pdf'):
            filename_with_pdf = f"{filename}.pdf"
            possible_paths = [
                os.path.join(STATIC_DIR, "pdfs", filename_with_pdf),
                os.path.join(STATIC_DIR, "pdfs", "terms", filename_with_pdf),
                os.path.join(STATIC_DIR, "pdfs", "applications", filename_with_pdf),
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    pdf_path = path
                    filename = filename_with_pdf
                    break
    
    if not pdf_path:
        # Create pdfs directory if it doesn't exist
        pdfs_dir = os.path.join(STATIC_DIR, "pdfs")
        os.makedirs(pdfs_dir, exist_ok=True)
        
        # Check again
        pdf_path = os.path.join(STATIC_DIR, "pdfs", filename)
        if not os.path.isfile(pdf_path):
            raise HTTPException(status_code=404, detail="PDF file not found")
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf"
    )
    
    logger.info(f"Serving PDF: {filename}")
    return response

# PDF Preview endpoint
@app.get("/preview/pdf/{filename}", tags=["Public Downloads"])
async def preview_pdf(filename: str, request: Request):
    """
    Preview PDF in browser (inline display)
    """
    # Security check - prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Check in multiple directories
    possible_paths = [
        os.path.join(STATIC_DIR, "pdfs", filename),
        os.path.join(STATIC_DIR, "pdfs", "terms", filename),
        os.path.join(STATIC_DIR, "pdfs", "applications", filename),
    ]
    
    pdf_path = None
    for path in possible_paths:
        if os.path.isfile(path):
            pdf_path = path
            break
    
    if not pdf_path:
        # Try with .pdf extension if not provided
        if not filename.endswith('.pdf'):
            filename_with_pdf = f"{filename}.pdf"
            possible_paths = [
                os.path.join(STATIC_DIR, "pdfs", filename_with_pdf),
                os.path.join(STATIC_DIR, "pdfs", "terms", filename_with_pdf),
                os.path.join(STATIC_DIR, "pdfs", "applications", filename_with_pdf),
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    pdf_path = path
                    filename = filename_with_pdf
                    break
    
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\""
        }
    )
    
    logger.info(f"Previewing PDF: {filename}")
    return response

# Health check endpoint with HEAD support
@app.get("/health", include_in_schema=False)
@app.head("/health", include_in_schema=False)
async def health_check():
    """
    Comprehensive health check endpoint
    """
    import psutil
    import datetime
    import sys
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "Marshal Core Backend API",
        "version": "1.0.0",
    }
    
    try:
        # System information
        health_status["system"] = {
            "python_version": sys.version,
            "platform": sys.platform,
            "uptime": psutil.boot_time() if hasattr(psutil, 'boot_time') else "N/A"
        }
        
        # Memory information
        if hasattr(psutil, 'virtual_memory'):
            memory = psutil.virtual_memory()
            health_status["memory"] = {
                "available": f"{memory.available / (1024**3):.2f} GB",
                "used": f"{memory.used / (1024**3):.2f} GB",
                "total": f"{memory.total / (1024**3):.2f} GB",
                "percent": f"{memory.percent}%"
            }
        
        # Disk information
        if hasattr(psutil, 'disk_usage'):
            try:
                disk = psutil.disk_usage('/')
                health_status["disk"] = {
                    "free": f"{disk.free / (1024**3):.2f} GB",
                    "used": f"{disk.used / (1024**3):.2f} GB",
                    "total": f"{disk.total / (1024**3):.2f} GB",
                    "percent": f"{disk.percent}%"
                }
            except:
                health_status["disk"] = "N/A"
        
        # Check PDF directories
        pdf_dirs = {
            "static_pdfs": os.path.join(STATIC_DIR, "pdfs"),
            "static_pdfs_terms": os.path.join(STATIC_DIR, "pdfs", "terms"),
            "static_pdfs_applications": os.path.join(STATIC_DIR, "pdfs", "applications"),
            "templates_pdf": os.path.join(BASE_DIR, "templates", "pdf")
        }
        
        health_status["directories"] = {}
        for name, path in pdf_dirs.items():
            exists = os.path.exists(path)
            health_status["directories"][name] = {
                "exists": exists,
                "path": path
            }
            if exists and os.path.isdir(path):
                try:
                    file_count = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
                    health_status["directories"][name]["file_count"] = file_count
                except:
                    health_status["directories"][name]["file_count"] = "N/A"
        
        # Check PDF generation capability
        try:
            import reportlab
            health_status["pdf_generation"] = {
                "status": "ready",
                "library": "reportlab",
                "version": getattr(reportlab, '__version__', 'unknown')
            }
        except ImportError:
            health_status["pdf_generation"] = {
                "status": "not_available",
                "message": "Install with: pip install reportlab pillow"
            }
            health_status["status"] = "degraded"
        
        logger.info("Health check completed successfully")
        
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["error"] = str(e)
        logger.error(f"Health check failed: {e}")
    
    return health_status

# PDF System Status endpoint with HEAD support
@app.get("/pdf/status", tags=["PDF System"])
@app.head("/pdf/status", tags=["PDF System"])
async def pdf_system_status():
    """
    Check PDF generation system status
    """
    status = {
        "pdf_system": "operational",
        "timestamp": datetime.datetime.now().isoformat(),
        "checks": {}
    }
    
    try:
        # Check if ReportLab is installed
        try:
            import reportlab
            status["checks"]["reportlab"] = {
                "status": "installed",
                "version": getattr(reportlab, '__version__', 'unknown')
            }
        except ImportError:
            status["checks"]["reportlab"] = {
                "status": "not_installed",
                "message": "Install with: pip install reportlab pillow"
            }
            status["pdf_system"] = "degraded"
        
        # Check if Pillow is installed (for image support)
        try:
            import PIL
            status["checks"]["pillow"] = {
                "status": "installed",
                "version": getattr(PIL, '__version__', 'unknown')
            }
        except ImportError:
            status["checks"]["pillow"] = {
                "status": "not_installed",
                "message": "Install with: pip install pillow"
            }
            # Not critical, just for image support
            status["checks"]["pillow"]["severity"] = "warning"
        
        # Check PDF storage directories
        pdf_dirs_to_check = [
            ("pdfs_root", os.path.join(STATIC_DIR, "pdfs")),
            ("pdfs_terms", os.path.join(STATIC_DIR, "pdfs", "terms")),
            ("pdfs_applications", os.path.join(STATIC_DIR, "pdfs", "applications"))
        ]
        
        dir_status = []
        for name, path in pdf_dirs_to_check:
            exists = os.path.exists(path)
            writable = False
            if exists:
                # Check if directory is writable
                test_file = os.path.join(path, ".test_write")
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                    writable = True
                except:
                    writable = False
            
            dir_status.append({
                "name": name,
                "path": path,
                "exists": exists,
                "writable": writable
            })
        
        status["checks"]["directories"] = {
            "status": "ready" if all(d["exists"] and d["writable"] for d in dir_status) else "issues",
            "directories": dir_status
        }
        
        if not all(d["exists"] and d["writable"] for d in dir_status):
            status["pdf_system"] = "degraded"
        
        # Check if PDF utility can be imported
        try:
            from app.utils.pdf import PDFGenerator
            status["checks"]["pdf_utility"] = {
                "status": "importable",
                "class": "PDFGenerator"
            }
            
            # Test PDF generation
            try:
                pdf_gen = PDFGenerator()
                status["checks"]["pdf_utility"]["instantiation"] = "success"
            except Exception as e:
                status["checks"]["pdf_utility"]["instantiation"] = f"failed: {str(e)}"
                status["pdf_system"] = "error"
                
        except ImportError as e:
            status["checks"]["pdf_utility"] = {
                "status": "import_failed",
                "error": str(e)
            }
            status["pdf_system"] = "error"
        
        logger.info("PDF system status check completed")
        
    except Exception as e:
        status["pdf_system"] = "error"
        status["error"] = str(e)
        logger.error(f"PDF system status check failed: {e}")
    
    return status

# Test PDF Generation endpoint (for debugging)
@app.post("/pdf/test/generate", tags=["PDF System"])
async def test_pdf_generation():
    """
    Test PDF generation endpoint (for debugging)
    """
    try:
        from app.utils.pdf import pdf_generator
        
        # Sample test data
        test_data = {
            "full_name": "Test Officer",
            "nin_number": "12345678901",
            "residential_address": "123 Test Street, Abuja, Nigeria",
            "rank": "Security Officer",
            "position": "Field Operations",
            "email": "test@example.com",
            "phone": "+2348012345678",
            "mobile_number": "+2348012345678",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "marital_status": "Single",
            "nationality": "Nigerian",
            "religion": "Christian",
            "place_of_birth": "Lagos",
            "state_of_residence": "Abuja",
            "local_government_residence": "Municipal Area Council",
            "country_of_residence": "Nigeria",
            "state_of_origin": "Lagos",
            "local_government_origin": "Ikeja",
            "years_of_service": "3",
            "service_number": "TEST-001",
            "additional_skills": "First Aid, Communication",
            "bank_name": "Test Bank",
            "account_number": "1234567890",
            "unique_id": "TEST001"
        }
        
        # Generate test PDFs
        result = pdf_generator.generate_both_pdfs(test_data, "test001")
        
        return {
            "status": "success",
            "message": "Test PDFs generated successfully",
            "data": result,
            "download_links": {
                "terms": f"/download/pdf/{os.path.basename(result['terms_pdf_path'])}",
                "application": f"/download/pdf/{os.path.basename(result['application_pdf_path'])}"
            }
        }
        
    except Exception as e:
        logger.error(f"Test PDF generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Test PDF generation failed: {str(e)}"
        )

# Global exception handler
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return Response(
        status_code=404,
        content=f"Endpoint {request.url} not found"
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    logger.error(f"Internal server error: {exc}")
    return Response(
        status_code=500,
        content="Internal server error"
    )
# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Initialize application on startup
    """
    logger.info("🚀 Marshal Core Backend starting up...")
    logger.info(f"📁 Static directory: {STATIC_DIR}")
    logger.info(f"🌐 CORS enabled for origins: {origins}")
    
    # Create necessary directories
    directories_to_create = [
        os.path.join(STATIC_DIR, "pdfs"),
        os.path.join(STATIC_DIR, "pdfs", "terms"),
        os.path.join(STATIC_DIR, "pdfs", "applications"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers"),
        os.path.join(BASE_DIR, "templates", "pdf"),
        os.path.join(BASE_DIR, "templates", "email")
    ]
    
    for directory in directories_to_create:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"✓ Created/verified directory: {directory}")
        except Exception as e:
            logger.warning(f"⚠ Could not create directory {directory}: {e}")
    
    # Start background services
    try:
        # Start email queue processor
        from app.services.email_service import start_email_queue
        await start_email_queue()
        logger.info("✓ Email queue processor started")
        
    except Exception as e:
        logger.warning(f"⚠ Email service initialization failed: {e}")
    
    # Log PDF system status
    try:
        import reportlab
        logger.info("✓ ReportLab is installed for PDF generation")
    except ImportError:
        logger.warning("⚠ ReportLab is not installed. PDF generation will fail.")
        logger.info("  Install with: pip install reportlab pillow")
    
    # Add Render status endpoint
    @app.get("/api/health/render-status", tags=["Health Check"], include_in_schema=False)
    async def render_status():
        """
        Special endpoint for Render.com status monitoring
        """
        import time
        
        return {
            "status": "awake",
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "Marshal Core API",
            "render": {
                "free_tier": True,
                "sleep_after_minutes": 15,
                "wake_time_seconds": 30,
                "keep_alive_active": True,
                "last_activity": time.time(),
                "recommended_ping_interval": "Every 10 minutes",
                "safety_margin_minutes": 5,
                "next_wake_check": "Continuous via keep-alive service"
            },
            "message": "Service is awake and responsive. Keep-alive service prevents sleeping on Render free tier."
        }
    
    # Log loaded routers
    logger.info("✅ Server is ready to handle requests")

# Start keep-alive service AFTER server is fully started
@app.on_event("startup")
async def delayed_startup():
    """
    Start keep-alive service after a delay to ensure server is running
    """
    # Wait 5 seconds for server to fully start
    await asyncio.sleep(5)
    
    try:
        # Check if we're running on Render.com
        is_render = os.getenv("RENDER") == "true" or "render.com" in os.getenv("RENDER_EXTERNAL_URL", "")
        
        if is_render:
            from app.services.keep_alive import start_keep_alive_service
            await start_keep_alive_service()
            logger.info("✅ Keep-alive service started for Render.com")
            logger.info("⚠️  Render free tier: Services sleep after 15 minutes of inactivity")
            logger.info("✅ This service will ping every 10 minutes (600 seconds) to stay awake")
            logger.info("📊 Safety margin: 5 minutes before Render's 15-minute sleep timer")
        else:
            # Local development - start with delay
            try:
                await asyncio.sleep(10)  # Wait longer for local
                from app.services.keep_alive import start_keep_alive_service
                await start_keep_alive_service()
                logger.info("✓ Keep-alive service started (local development - delayed start)")
            except Exception as e:
                logger.info(f"⏸️  Keep-alive service skipped locally: {e}")
        
    except Exception as e:
        logger.warning(f"⚠ Keep-alive service initialization failed: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of services"""
    logger.info("🛑 Marshal Core Backend shutting down...")
    
    # Stop keep-alive service
    try:
        from app.services.keep_alive import stop_keep_alive_service
        await stop_keep_alive_service()
    except Exception as e:
        logger.error(f"Error stopping keep-alive: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )