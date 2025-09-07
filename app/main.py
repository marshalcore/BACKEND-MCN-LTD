from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
import os
import logging

# Init app
app = FastAPI(title="Marshal Core Backend")

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS Setup - Enhanced Configuration with frontend ports
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
    "https://backend-mcn-ltd.onrender.com",  
    "https://marshalcoreofficer.netlify.app",
    "https://marshalcoreofnigerialimited.netlify.app",
    "https://marshalcoreadmin.netlify.app", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)

# Add explicit OPTIONS handler middleware
@app.middleware("http")
async def options_handler(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", "Content-Type, Authorization, Accept"),
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "600",
                "Access-Control-Expose-Headers": "*"
            }
        )
        return response
    
    response = await call_next(request)
    
    origin = request.headers.get("origin")
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

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
# FIXED: Removed duplicate officer_auth_router import
from app.routes.pre_register import router as pre_register_router
from app.routes.payment import router as payment_router
from app.routes.application_access import router as application_access_router
from app.routes.application_form import router as application_form_router
from app.routes.form_submission import router as form_submission_router
from app.routes.officer_auth import router as officer_auth_router  # ✅ Only one import
from app.routes.password_reset import router as password_reset_router
from app.routes.admin_auth import router as admin_router
from app.routes.officer_uploads import router as officer_uploads_router
from app.routes.officer_dashboard import router as officer_dashboard_router
# REMOVED: Duplicate officer_auth_router import

# Include all routers - FIXED: Removed duplicate router
routers = [
    pre_register_router,
    payment_router,
    application_access_router,
    application_form_router,
    form_submission_router,
    officer_auth_router,  # ✅ Only one instance
    password_reset_router,
    admin_router,
    officer_uploads_router,
    officer_dashboard_router
]

for router in routers:
    app.include_router(router)
    logger.info(f"Included router: {router.prefix}")

# Root endpoint with CORS headers
@app.get("/", include_in_schema=False)
async def root():
    return {
        "status": "ok",
        "message": "Welcome to Marshal Core Of Nigeria Limited Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": [
            "/admin/* - Admin authentication and management",
            "/officer/* - Officer routes",
            "/applicant/* - Applicant routes",
            "/payment/* - Payment processing",
            "/health - System health check"
        ]
    }

# File download route with CORS support
@app.get("/download/pdf/{filename}", tags=["Public Downloads"])
async def download_pdf(filename: str, request: Request):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    pdf_path = os.path.join(STATIC_DIR, "pdfs", filename)
    
    pdfs_dir = os.path.join(STATIC_DIR, "pdfs")
    os.makedirs(pdfs_dir, exist_ok=True)
    
    if not os.path.isfile(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    response = FileResponse(
        pdf_path,
        filename=filename,
        media_type="application/pdf"
    )
    
    origin = request.headers.get("origin")
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# Health check endpoint with detailed information
@app.get("/health", include_in_schema=False)
async def health_check():
    import psutil
    import datetime
    
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "server": {
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "uptime": psutil.boot_time() if hasattr(psutil, 'boot_time') else "N/A"
        },
        "memory": {
            "available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
            "used": f"{psutil.virtual_memory().used / (1024**3):.2f} GB",
            "total": f"{psutil.virtual_memory().total / (1024**3):.2f} GB"
        } if hasattr(psutil, 'virtual_memory') else "N/A"
    }

# Global exception handler
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return Response(
        status_code=404,
        content=f"Endpoint {request.url} not found",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    logger.error(f"Internal server error: {exc}")
    return Response(
        status_code=500,
        content="Internal server error",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true"
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Marshal Core Backend starting up...")
    logger.info(f"📁 Static directory: {STATIC_DIR}")
    logger.info(f"🌐 CORS enabled for origins: {origins}")
    logger.info("✅ Server is ready to handle requests")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Marshal Core Backend shutting down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )