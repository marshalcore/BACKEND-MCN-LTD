# app/routes/__init__.py - UPDATED
from .payment import router as payment_router
from .application_form import router as application_form_router
from .application_access import router as application_access_router
from .privacy import router as privacy_router
from .pre_register import router as pre_register_router
from .officer_auth import router as officer_auth_router
from .image_upload import router as image_upload_router  # NEW

# All routers that should be included in main app
__all__ = [
    "payment_router",
    "application_form_router",
    "application_access_router", 
    "privacy_router",
    "pre_register_router",
    "officer_auth_router",
    "image_upload_router",  # NEW
]