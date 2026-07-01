# app/main.py - PRODUCTION LIVE MODE VERSION - UPDATED
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
logger.info(f"Immediate Transfers Enabled: {settings.ENABLE_IMMEDIATE_TRANSFERS}")
logger.info(f"Paystack Mode: {'LIVE' if not settings.PAYSTACK_TEST_MODE else 'TEST'} - CHANGED TO LIVE")
logger.info("=" * 50)

# ==================== FIXED CORS CONFIGURATION ====================
# Define specific allowed origins
allowed_origins = [
    "https://marshalcoreofnigeria.ng",
    "http://marshalcoreofnigeria.ng",
    "https://backend-mcn-ltd.onrender.com",
    "https://officer.marshalcoreofnigeria.ng",
    "https://portal.marshalcoreofnigeria.ng",
    "https://verify.marshalcoreofnigeria.ng",
    "https://marshalcoreadmin.netlify.app",
    "https://recruitment.marshalcoreofnigeria.ng",
    "https://directoradmin.netlify.app",
    "https://mcnadmin.marshalcoreofnigeria.ng",
]

# For local development
if settings.DEBUG:
    allowed_origins.extend([
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
    ])

# Use ONLY FastAPI's CORSMiddleware with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Specific origins instead of wildcard
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
from app.routes.email_verification import router as email_verification_router
from app.routes.image_upload import router as image_upload_router  # NEW

# Include all routers
routers = [
    pre_register_router,
    payment_router,  # Includes immediate transfer endpoints
    application_access_router,
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
    email_verification_router,
    image_upload_router,  # NEW
]

for router in routers:
    app.include_router(router)

# ==================== MIDDLEWARE FOR NORMALIZED FILE PATHS ====================

@app.middleware("http")
async def normalize_static_paths(request: Request, call_next):
    """
    Middleware to normalize static file paths for officer IDs with slashes
    """
    path = request.url.path
    
    # Silent path normalization
    if '/static/uploads/existing_officers/' in path and ('/' in path or '\\' in path):
        parts = path.split('/')
        try:
            idx = parts.index('existing_officers')
            if idx + 1 < len(parts) and ('/' in parts[idx + 1] or '\\' in parts[idx + 1]):
                normalized = parts[idx + 1].replace('/', '-').replace('\\', '-')
                normalized_relative_path = '/'.join(parts[:idx+1]) + '/' + normalized + '/'.join(parts[idx+2:])
                normalized_full_path = os.path.join(STATIC_DIR, normalized_relative_path)
                
                if os.path.exists(normalized_full_path):
                    ext = '.jpg' if normalized_full_path.endswith(('.jpg', '.jpeg')) else '.png' if normalized_full_path.endswith('.png') else '.pdf' if normalized_full_path.endswith('.pdf') else ''
                    media_type = {
                        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.pdf': 'application/pdf'
                    }.get(ext, 'application/octet-stream')
                    
                    return FileResponse(normalized_full_path, media_type=media_type,
                        headers={'Access-Control-Allow-Origin': 'https://marshalcoreofnigeria.ng',
                                'Cache-Control': 'public, max-age=3600'})
        except (ValueError, IndexError):
            pass
        except Exception:
            pass
    
    # Continue with normal request processing
    response = await call_next(request)
    
    # Add proper CORS headers to all responses
    origin = request.headers.get("origin")
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        # Fallback to the main domain if origin not in list
        response.headers["Access-Control-Allow-Origin"] = "https://marshalcoreofnigeria.ng"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

# ==================== CORS FIX MIDDLEWARE FOR FORM SUBMISSIONS ====================

@app.middleware("http")
async def cors_fix_middleware(request: Request, call_next):
    """
    Fix CORS headers for form submission endpoints
    """
    response = await call_next(request)
    
    # Check if origin is in allowed list
    origin = request.headers.get("origin")
    
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        # Default to main domain
        response.headers["Access-Control-Allow-Origin"] = "https://marshalcoreofnigeria.ng"
    
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = "*"
    
    # Special handling for OPTIONS requests
    if request.method == "OPTIONS":
        response.status_code = 200
    
    return response

# ==================== END MIDDLEWARE ====================

# Root endpoint with HEAD support
@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
async def root():
    return {
        "status": "ok",
        "message": "Welcome to Marshal Core of Nigeria Backend API - PRODUCTION LIVE MODE",
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
            "/api/admin/image-to-pdf/* - Admin image to PDF conversion (NEW)",
            "/health - System health check",
            "/api/health - Health check endpoint"
        ],
        "config_info": {
            "environment": "PRODUCTION LIVE",
            "token_expiry_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "running_on_render": settings.RENDER,
            "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS,
            "payment_amounts": {
                "regular": f"₦{settings.REGULAR_APPLICATION_FEE:,}",
                "vip": f"₦{settings.VIP_APPLICATION_FEE:,}"
            },
            "paystack_mode": "LIVE",
            "transfers_live": "YES - Real money transfers active"
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
        os.path.join(STATIC_DIR, "pdfs", "guarantor_form", filename),
        os.path.join(STATIC_DIR, "image_to_pdf", filename),  # NEW
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
            elif "image_to_pdf" in path:
                file_category = "image_to_pdf"
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
                os.path.join(STATIC_DIR, "pdfs", "guarantor_form", filename_with_pdf),
                os.path.join(STATIC_DIR, "image_to_pdf", filename_with_pdf),  # NEW
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    pdf_path = path
                    filename = filename_with_pdf
                    if "terms" in path:
                        file_category = "terms"
                    elif "applications" in path:
                        file_category = "applications"
                    elif "image_to_pdf" in path:
                        file_category = "image_to_pdf"
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
        os.makedirs(os.path.join(STATIC_DIR, "pdfs", "guarantor_form"), exist_ok=True)
        os.makedirs(os.path.join(STATIC_DIR, "image_to_pdf"), exist_ok=True)  # NEW
        
        # Check one more time after creating directories
        possible_paths = [
            os.path.join(STATIC_DIR, "pdfs", filename),
            os.path.join(STATIC_DIR, "pdfs", "terms", filename),
            os.path.join(STATIC_DIR, "pdfs", "applications", filename),
            os.path.join(STATIC_DIR, "pdfs", "guarantor_form", filename),
            os.path.join(STATIC_DIR, "image_to_pdf", filename),  # NEW
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                pdf_path = path
                break
        
        if not pdf_path:
            # List available PDFs for debugging
            available_pdfs = []
            for category in ["", "terms", "applications", "image_to_pdf"]:
                category_dir = os.path.join(STATIC_DIR, "pdfs", category) if category != "image_to_pdf" else os.path.join(STATIC_DIR, "image_to_pdf")
                if os.path.exists(category_dir):
                    try:
                        files = [f for f in os.listdir(category_dir) if f.endswith('.pdf')]
                        available_pdfs.extend([f"{category}/{f}" if category else f for f in files])
                    except:
                        pass
            
            logger.error(f"PDF file not found: {filename}")
            logger.error(f"Available PDFs: {available_pdfs[:10]}...")
            raise HTTPException(
                status_code=404, 
                detail=f"PDF file '{filename}' not found. Available files: {available_pdfs[:10]}..."
            )
    
    # Get the origin from request
    origin = request.headers.get("origin")
    allowed_origin = origin if origin in allowed_origins else "https://marshalcoreofnigeria.ng"
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Credentials": "true",
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
        os.path.join(STATIC_DIR, "pdfs", "guarantor_form", filename),
        os.path.join(STATIC_DIR, "image_to_pdf", filename),  # NEW
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
                os.path.join(STATIC_DIR, "pdfs", "guarantor_form", filename_with_pdf),
                os.path.join(STATIC_DIR, "image_to_pdf", filename_with_pdf),  # NEW
            ]
            
            for path in possible_paths:
                if os.path.isfile(path):
                    pdf_path = path
                    filename = filename_with_pdf
                    break
    
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Get the origin from request
    origin = request.headers.get("origin")
    allowed_origin = origin if origin in allowed_origins else "https://marshalcoreofnigeria.ng"
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Credentials": "true"
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
        "service": "Marshal Core Backend API - PRODUCTION",
        "version": "1.0.0",
        "config": {
            "environment": "PRODUCTION LIVE",
            "token_expiry_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expiry_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
            "running_on_render": settings.RENDER,
            "paystack_mode": "LIVE",
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
            "image_to_pdf": os.path.join(STATIC_DIR, "image_to_pdf"),  # NEW
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
            ("pdfs_applications", os.path.join(STATIC_DIR, "pdfs", "applications")),
            ("pdfs_guarantor_form", os.path.join(STATIC_DIR, "pdfs", "guarantor_form")),
            ("image_to_pdf", os.path.join(STATIC_DIR, "image_to_pdf")),  # NEW
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
    logger.info("Starting up...")
    logger.debug(f"Static dir: {STATIC_DIR}")
    logger.debug(f"CORS: {len(allowed_origins)} origins")
    logger.info(f"Transfers: {'ENABLED' if settings.ENABLE_IMMEDIATE_TRANSFERS else 'DISABLED'}")
    logger.info(f"Payment: ₦{settings.REGULAR_APPLICATION_FEE:,}, VIP: ₦{settings.VIP_APPLICATION_FEE:,}")
    logger.info("PAYSTACK: LIVE - Real money active")
    
    # Create necessary directories - UPDATED FOR NORMALIZED PATHS
    directories_to_create = [
        # PDF directories
        os.path.join(STATIC_DIR, "pdfs"),
        os.path.join(STATIC_DIR, "pdfs", "terms"),
        os.path.join(STATIC_DIR, "pdfs", "applications"),
        os.path.join(STATIC_DIR, "image_to_pdf"),  # NEW
        
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
    
    # Create all directories silently
    for directory in directories_to_create:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception:
            pass
    
    # Start background services
    try:
        # Start email queue processor
        from app.services.email_service import start_email_queue
        await start_email_queue()
        logger.debug("Email queue ready")
        
    except Exception as e:
        logger.warning(f"⚠ Email service initialization failed: {e}")
    
    # Log PDF system status
    try:
        import reportlab
        logger.debug("PDF system ready")
    except ImportError:
        logger.warning("⚠ ReportLab is not installed. PDF generation will fail.")
        logger.debug("PDF system ready")
    
    # Log immediate transfer service status - FIXED: No test_mode attribute
    try:
        from app.services.immediate_transfer import ImmediateTransferService
        transfer_service = ImmediateTransferService()
        logger.debug("Transfer service ready")
        logger.debug(f"Mode: {'LIVE' if transfer_service.is_live_mode else 'TEST'}")
        logger.debug(f"Transfers: {transfer_service.enable_transfers}")
        logger.info(f"MarshalCore: {settings.MARSHAL_CORE_BANK_ACCOUNT_NAME} - {settings.MARSHAL_CORE_ACCOUNT_NUMBER} ({settings.MARSHAL_CORE_SHARE_PERCENTAGE}%)")
        logger.info(f"SystemsMaintainance: {settings.SYSTEMS_MAINTAINANCE_ACCOUNT_NAME} - {settings.SYSTEMS_MAINTAINANCE_ACCOUNT_NUMBER} ({settings.SYSTEMS_MAINTAINANCE_SHARE_PERCENTAGE}%)")
        logger.info(f"eSTech: {settings.ESTECH_BANK_NAME} ({settings.ESTECH_BANK_CODE}) - {settings.ESTECH_BANK_ACCOUNT_NUMBER} ({settings.ESTECH_COMMISSION_PERCENTAGE}%)")
        logger.debug("Paystack split enabled")
    except Exception as e:
        logger.warning(f"⚠ Immediate transfer service initialization failed: {e}")
    
    # Log normalized paths middleware status
    logger.debug("Path normalization ready")
    
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
            "service": "Marshal Core API - PRODUCTION LIVE",
            "render": {
                "free_tier": True,
                "note": "Neon PostgreSQL auto-sleep enabled - database wakes automatically"
            },
            "config_info": {
                "running_on_render": settings.RENDER,
                "immediate_transfers_enabled": settings.ENABLE_IMMEDIATE_TRANSFERS,
                "paystack_mode": "LIVE - Real money"
            },
            "message": "Service is running. Neon PostgreSQL handles auto-sleep automatically."
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
            all_passport_files = glob.glob(passport_path_pattern, recursive=True)
            
            matching_passports = []
            for file_path in all_passport_files:
                if normalized_id in file_path or officer_id in file_path:
                    matching_passports.append(os.path.relpath(file_path, STATIC_DIR))
            
            # Check consolidated PDF directories
            pdf_path_pattern = os.path.join(STATIC_DIR, "uploads", "existing_officers", "*", "consolidated_pdf", "*")
            all_pdf_files = glob.glob(pdf_path_pattern, recursive=True)
            
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
    
    # Add image-to-pdf test endpoint
    @app.get("/api/debug/image-to-pdf", tags=["Debug"], include_in_schema=False)
    async def debug_image_to_pdf():
        """
        Debug endpoint to check image-to-pdf service status
        """
        from app.services.image_to_pdf_service import image_to_pdf_service, IMAGE_TO_PDF_DIR
        
        # Check directory
        dir_exists = IMAGE_TO_PDF_DIR.exists()
        dir_writable = False
        file_count = 0
        
        if dir_exists:
            try:
                test_file = IMAGE_TO_PDF_DIR / ".test_write"
                test_file.touch()
                test_file.unlink()
                dir_writable = True
                
                # Count existing PDFs
                file_count = len(list(IMAGE_TO_PDF_DIR.glob("*.pdf")))
            except:
                dir_writable = False
        
        return {
            "service_initialized": True,
            "image_to_pdf_dir": {
                "path": str(IMAGE_TO_PDF_DIR),
                "exists": dir_exists,
                "writable": dir_writable,
                "pdf_count": file_count
            },
            "max_pdf_size_mb": image_to_pdf_service.max_pdf_size_bytes / (1024 * 1024),
            "endpoints": {
                "upload": "/api/admin/image-to-pdf/upload",
                "history": "/api/admin/image-to-pdf/history",
                "download": "/api/admin/image-to-pdf/download/{record_id}"
            },
            "note": "This is an admin-only feature. Requires authentication."
        }
    
    # Log loaded routers
    logger.info("✅ Server is ready to handle requests")

# Keep-alive service REMOVED - using Neon PostgreSQL's auto-sleep feature
# Neon free tier: database sleeps after 5 minutes of inactivity, wakes automatically

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
        "pdf_files": pdf_files[:50],  # Limit to 50 files
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