# app/main.py - UPDATED (add import and router)
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
import os
import logging
import datetime
import asyncio

# Import settings BEFORE setting up the app to verify config
from app.config import settings

# Init app
app = FastAPI(title="Marshal Core Backend")

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log configuration to verify settings are loaded correctly
logger.info("=" * 50)
logger.info("CONFIGURATION VERIFICATION")
logger.info("=" * 50)
logger.info(f"Database URL: {settings.DATABASE_URL[:50]}...")  # Show first 50 chars for security
logger.info(f"Access Token Expire Minutes: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
logger.info(f"Refresh Token Expire Days: {settings.REFRESH_TOKEN_EXPIRE_DAYS}")
logger.info(f"Resend From Email: {settings.RESEND_FROM_EMAIL}")
logger.info(f"Resend API Key Set: {'Yes' if settings.RESEND_API_KEY else 'No'}")
logger.info(f"Debug Mode: {settings.DEBUG}")
logger.info(f"Running on Render: {settings.RENDER}")
logger.info(f"Keep Alive Enabled: {settings.ENABLE_KEEP_ALIVE}")
logger.info(f"Immediate Transfers Enabled: {settings.ENABLE_IMMEDIATE_TRANSFERS}")
logger.info("=" * 50)

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
        description="Marshal Core API - Admin, Officer, and Applicant Management System with Immediate Payment Transfers",
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
from app.routes.privacy import router as privacy_router

# Include all routers
routers = [
    pre_register_router,
    payment_router,  # Includes immediate transfer endpoints
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
    health_router,
    privacy_router, 
]

for router in routers:
    app.include_router(router)
    logger.info(f"Included router: {router.prefix}")

# ==================== MIDDLEWARE FOR NORMALIZED FILE PATHS ====================

@app.middleware("http")
async def normalize_static_paths(request: Request, call_next):
    """
    Middleware to normalize static file paths for officer IDs with slashes
    
    This handles the case where officer IDs contain slashes (e.g., MCN/001B/001)
    and converts them to hyphens for file system compatibility.
    """
    path = request.url.path
    
    # Check if it's a static uploads path with existing_officers
    if '/static/uploads/existing_officers/' in path:
        logger.info(f"🔄 Processing static path: {path}")
        
        # Extract officer ID from path and normalize it
        parts = path.split('/')
        
        # Find the index of 'existing_officers' in the path
        try:
            existing_officers_index = parts.index('existing_officers')
            if existing_officers_index + 1 < len(parts):
                officer_id = parts[existing_officers_index + 1]
                
                # Check if officer ID has slashes (e.g., MCN/001B/001)
                if '/' in officer_id or '\\' in officer_id:
                    logger.info(f"🔄 Found officer ID with slashes: {officer_id}")
                    
                    # Normalize the officer ID (replace slashes with hyphens)
                    normalized_id = officer_id.replace('/', '-').replace('\\', '-')
                    parts[existing_officers_index + 1] = normalized_id
                    new_path = '/'.join(parts)
                    
                    # Construct the full file path for normalized version
                    normalized_relative_path = new_path.replace('/static/', '')
                    normalized_full_path = os.path.join(STATIC_DIR, normalized_relative_path)
                    
                    # Check if normalized file exists
                    if os.path.exists(normalized_full_path):
                        logger.info(f"✅ Serving normalized path: {new_path}")
                        logger.info(f"   File exists at: {normalized_full_path}")
                        
                        # Determine file extension for proper content type
                        if normalized_full_path.endswith('.jpg') or normalized_full_path.endswith('.jpeg'):
                            media_type = 'image/jpeg'
                        elif normalized_full_path.endswith('.png'):
                            media_type = 'image/png'
                        elif normalized_full_path.endswith('.pdf'):
                            media_type = 'application/pdf'
                        else:
                            media_type = 'application/octet-stream'
                        
                        # Return the file response directly
                        return FileResponse(
                            normalized_full_path,
                            media_type=media_type,
                            headers={
                                'Access-Control-Allow-Origin': '*',
                                'Cache-Control': 'public, max-age=3600'
                            }
                        )
                    else:
                        logger.warning(f"⚠️ Normalized file not found: {normalized_full_path}")
                        
                        # Try the original path as well (for backward compatibility)
                        original_relative_path = path.replace('/static/', '')
                        original_full_path = os.path.join(STATIC_DIR, original_relative_path)
                        
                        if os.path.exists(original_full_path):
                            logger.info(f"✅ Serving original path (backward compatibility): {path}")
                            response = await call_next(request)
                            return response
                        else:
                            logger.error(f"❌ Both normalized and original files not found")
                            logger.error(f"   Normalized: {normalized_full_path}")
                            logger.error(f"   Original: {original_full_path}")
        
        except ValueError:
            # 'existing_officers' not found in path
            pass
        except Exception as e:
            logger.error(f"❌ Error in normalize_static_paths middleware: {e}")
    
    # Continue with normal request processing
    response = await call_next(request)
    return response

# ==================== END MIDDLEWARE ====================

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
            "/api/payments/* - Payment processing with immediate transfers",
            "/pdf/* - PDF document download and management",
            "/health - System health check",
            "/api/health - Enhanced health check with keep-alive"
        ],
        "config_info": {
            "environment": "production" if not settings.DEBUG else "development",
            "token_expiry_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "running_on_render": settings.RENDER,
            "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS,
            "payment_amounts": {
                "regular": f"₦{settings.REGULAR_APPLICATION_FEE:,}",
                "vip": f"₦{settings.VIP_APPLICATION_FEE:,}"
            }
        }
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
    file_category = None
    
    for path in possible_paths:
        if os.path.isfile(path):
            pdf_path = path
            if "terms" in path:
                file_category = "terms"
            elif "applications" in path:
                file_category = "applications"
            else:
                file_category = "general"
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
                    if "terms" in path:
                        file_category = "terms"
                    elif "applications" in path:
                        file_category = "applications"
                    else:
                        file_category = "general"
                    break
    
    if not pdf_path:
        # Log the search for debugging
        logger.warning(f"PDF not found: {filename}. Searched in:")
        for path in possible_paths:
            exists = os.path.exists(path)
            logger.warning(f"  - {path}: {'Exists' if exists else 'Not found'}")
        
        # Create pdfs directory if it doesn't exist
        pdfs_dir = os.path.join(STATIC_DIR, "pdfs")
        os.makedirs(pdfs_dir, exist_ok=True)
        os.makedirs(os.path.join(STATIC_DIR, "pdfs", "terms"), exist_ok=True)
        os.makedirs(os.path.join(STATIC_DIR, "pdfs", "applications"), exist_ok=True)
        
        # Check one more time after creating directories
        possible_paths = [
            os.path.join(STATIC_DIR, "pdfs", filename),
            os.path.join(STATIC_DIR, "pdfs", "terms", filename),
            os.path.join(STATIC_DIR, "pdfs", "applications", filename),
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                pdf_path = path
                break
        
        if not pdf_path:
            # List available PDFs for debugging
            available_pdfs = []
            for category in ["", "terms", "applications"]:
                category_dir = os.path.join(STATIC_DIR, "pdfs", category)
                if os.path.exists(category_dir):
                    try:
                        files = [f for f in os.listdir(category_dir) if f.endswith('.pdf')]
                        available_pdfs.extend([f"{category}/{f}" if category else f for f in files])
                    except:
                        pass
            
            logger.error(f"PDF file not found: {filename}")
            logger.error(f"Available PDFs: {available_pdfs}")
            raise HTTPException(
                status_code=404, 
                detail=f"PDF file '{filename}' not found. Available files: {available_pdfs[:10]}..."
            )
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
    
    logger.info(f"Serving PDF: {filename} (from {file_category})")
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
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "Access-Control-Allow-Origin": "*"
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
        "config": {
            "environment": "production" if not settings.DEBUG else "development",
            "token_expiry_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expiry_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
            "running_on_render": settings.RENDER,
            "keep_alive_enabled": settings.ENABLE_KEEP_ALIVE,
            "paystack_test_mode": settings.PAYSTACK_TEST_MODE,
            "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS
        }
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
    logger.info(f"💰 Immediate Transfers: {'ENABLED' if settings.ENABLE_IMMEDIATE_TRANSFERS else 'DISABLED'}")
    logger.info(f"💰 Payment Amounts - Regular: ₦{settings.REGULAR_APPLICATION_FEE:,}, VIP: ₦{settings.VIP_APPLICATION_FEE:,}")
    
    # Create necessary directories - UPDATED FOR NORMALIZED PATHS
    directories_to_create = [
        # PDF directories
        os.path.join(STATIC_DIR, "pdfs"),
        os.path.join(STATIC_DIR, "pdfs", "terms"),
        os.path.join(STATIC_DIR, "pdfs", "applications"),
        
        # Upload directories for existing officers (with normalized structure)
        os.path.join(STATIC_DIR, "uploads", "existing_officers"),
        
        # Create nested directories for potential normalized officer IDs
        # This ensures directories exist for both formats
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MCN-001B-001", "passport"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MCN-001B-001", "consolidated_pdf"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MCN-001-031", "passport"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MCN-001-031", "consolidated_pdf"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MBT-A01-456", "passport"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MBT-A01-456", "consolidated_pdf"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MBC-123A-789", "passport"),
        os.path.join(STATIC_DIR, "uploads", "existing_officers", "MBC-123A-789", "consolidated_pdf"),
        
        # Template directories
        os.path.join(BASE_DIR, "templates", "pdf"),
        os.path.join(BASE_DIR, "templates", "email"),
        
        # Image directories
        os.path.join(STATIC_DIR, "images"),
        os.path.join(STATIC_DIR, "images", "logo"),
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
    
    # Log immediate transfer service status
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        transfer_service = ImmediateTransferService()
        logger.info("✓ Immediate transfer service initialized")
        logger.info(f"  Test Mode: {'Yes' if transfer_service.test_mode else 'No'}")
        logger.info(f"  DG Account: {settings.DG_ACCOUNT_NAME} - {settings.DG_ACCOUNT_NUMBER}")
        logger.info(f"  eSTech Account: {settings.ESTECH_IMMEDIATE_ACCOUNT_NAME} - {settings.ESTECH_IMMEDIATE_ACCOUNT_NUMBER}")
    except Exception as e:
        logger.warning(f"⚠ Immediate transfer service initialization failed: {e}")
    
    # Log normalized paths middleware status
    logger.info("✅ Normalized static paths middleware enabled")
    logger.info("   Officer IDs with slashes (MCN/001B/001) will be normalized to hyphens (MCN-001B-001)")
    logger.info("   This fixes passport photo 404 errors for existing officers")
    
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
            "config_info": {
                "keep_alive_enabled": settings.ENABLE_KEEP_ALIVE,
                "keep_alive_interval_seconds": settings.KEEP_ALIVE_INTERVAL,
                "running_on_render": settings.RENDER,
                "render_external_url": settings.RENDER_EXTERNAL_URL,
                "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS
            },
            "message": "Service is awake and responsive. Keep-alive service prevents sleeping on Render free tier."
        }
    
    # Add normalized paths test endpoint
    @app.get("/api/debug/normalized-paths", tags=["Debug"], include_in_schema=False)
    async def debug_normalized_paths():
        """
        Debug endpoint to test normalized path resolution
        """
        import glob
        
        test_officer_ids = ["MCN/001B/001", "MCN-001B-001", "MCN/001/031", "MCN-001-031"]
        
        results = {}
        for officer_id in test_officer_ids:
            normalized_id = officer_id.replace('/', '-').replace('\\', '-')
            
            # Check passport directories
            passport_path_pattern = os.path.join(STATIC_DIR, "uploads", "existing_officers", "*", "passport", "*")
            all_passport_files = glob.glob(passport_path_pattern)
            
            matching_passports = []
            for file_path in all_passport_files:
                if normalized_id in file_path or officer_id in file_path:
                    matching_passports.append(os.path.relpath(file_path, STATIC_DIR))
            
            # Check consolidated PDF directories
            pdf_path_pattern = os.path.join(STATIC_DIR, "uploads", "existing_officers", "*", "consolidated_pdf", "*")
            all_pdf_files = glob.glob(pdf_path_pattern)
            
            matching_pdfs = []
            for file_path in all_pdf_files:
                if normalized_id in file_path or officer_id in file_path:
                    matching_pdfs.append(os.path.relpath(file_path, STATIC_DIR))
            
            results[officer_id] = {
                "normalized_id": normalized_id,
                "passport_files": matching_passports,
                "pdf_files": matching_pdfs,
                "has_passport": len(matching_passports) > 0,
                "has_pdf": len(matching_pdfs) > 0
            }
        
        return {
            "normalized_paths_middleware": "enabled",
            "static_dir": STATIC_DIR,
            "test_results": results,
            "message": "Normalized paths middleware handles officer IDs with slashes"
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
        # ALWAYS start keep-alive on Render.com (check by URL or environment)
        render_url = settings.RENDER_EXTERNAL_URL or ""
        is_render = "render.com" in render_url or os.getenv("RENDER_EXTERNAL_URL", "").endswith(".onrender.com")
        
        if (settings.ENABLE_KEEP_ALIVE and is_render) or os.getenv("RENDER") == "true":
            from app.services.keep_alive import start_keep_alive_service
            await start_keep_alive_service()
            logger.info("✅ Keep-alive service started for Render.com")
            logger.info(f"⚠️  Render free tier: Services sleep after 15 minutes of inactivity")
            logger.info(f"✅ This service will ping every {settings.KEEP_ALIVE_INTERVAL} seconds to stay awake")
            logger.info(f"📊 External URL: {settings.RENDER_EXTERNAL_URL or 'https://backend-mcn-ltd.onrender.com'}")
        else:
            # Local development or keep-alive disabled
            logger.info(f"⏸️  Keep-alive service disabled or not running on Render")
            logger.info(f"   RENDER setting: {settings.RENDER}")
            logger.info(f"   ENABLE_KEEP_ALIVE: {settings.ENABLE_KEEP_ALIVE}")
            logger.info(f"   RENDER_EXTERNAL_URL: {settings.RENDER_EXTERNAL_URL}")
        
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

@app.get("/debug/pdf-files", include_in_schema=False)
async def debug_pdf_files():
    """
    Debug endpoint to see what PDF files exist on the server
    """
    pdf_files = []

    # Search for PDF files recursively
    for root, dirs, files in os.walk(STATIC_DIR):
        for file in files:
            if file.lower().endswith('.pdf'):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, STATIC_DIR)
                pdf_files.append({
                    "filename": file,
                    "path": relative_path,
                    "full_path": full_path,
                    "size": os.path.getsize(full_path),
                    "exists": True
                })

    return {
        "pdf_files_count": len(pdf_files),
        "pdf_files": pdf_files,
        "static_dir": STATIC_DIR
    }

@app.get("/debug/upload-files", include_in_schema=False)
async def debug_upload_files():
    """
    Debug endpoint to see what upload files exist on the server
    """
    import glob
    
    upload_files = []
    
    # Search for upload files recursively
    upload_pattern = os.path.join(STATIC_DIR, "uploads", "**", "*")
    
    for file_path in glob.glob(upload_pattern, recursive=True):
        if os.path.isfile(file_path):
            relative_path = os.path.relpath(file_path, STATIC_DIR)
            
            # Get file info
            try:
                file_size = os.path.getsize(file_path)
                file_ext = os.path.splitext(file_path)[1].lower()
                
                upload_files.append({
                    "filename": os.path.basename(file_path),
                    "path": relative_path,
                    "full_path": file_path,
                    "size": file_size,
                    "extension": file_ext,
                    "exists": True
                })
            except:
                pass
    
    # Group by officer ID for easier analysis
    officer_files = {}
    for file_info in upload_files:
        path = file_info['path']
        if 'existing_officers' in path:
            # Extract officer ID from path
            parts = path.split('/')
            try:
                officer_index = parts.index('existing_officers')
                if officer_index + 1 < len(parts):
                    officer_id = parts[officer_index + 1]
                    if officer_id not in officer_files:
                        officer_files[officer_id] = []
                    officer_files[officer_id].append(file_info)
            except ValueError:
                pass
    
    return {
        "upload_files_count": len(upload_files),
        "upload_files_sample": upload_files[:20],  # Limit to first 20 files
        "officer_files": officer_files,
        "static_dir": STATIC_DIR,
        "message": f"Found {len(upload_files)} upload files, {len(officer_files)} unique officer IDs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )