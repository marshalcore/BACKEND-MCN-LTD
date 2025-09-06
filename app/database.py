from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Debug: Log the database URL (useful for troubleshooting)
logger.info(f"Database URL: {settings.DATABASE_URL}")

# For Neon.tech, ensure SSL is configured
if settings.DATABASE_URL and "neon.tech" in settings.DATABASE_URL:
    if "sslmode" not in settings.DATABASE_URL:
        if "?" in settings.DATABASE_URL:
            settings.DATABASE_URL += "&sslmode=require"
        else:
            settings.DATABASE_URL += "?sslmode=require"
        logger.info("Added sslmode=require to Neon database URL")

try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,  # Auto-reconnect on broken connections
        pool_size=5,         # Adjust pool size for Render
        max_overflow=10,     # Allow some overflow connections
        pool_timeout=30,     # Connection timeout in seconds
        pool_recycle=1800,   # Recycle connections after 30 minutes
    )
    
    # Test the connection immediately
    with engine.connect() as conn:
        logger.info("✅ Database connection successful!")
        
except Exception as e:
    logger.error(f"❌ Database connection failed: {e}")
    logger.error(f"Database URL: {settings.DATABASE_URL}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ This line ensures models are registered before Alembic autogenerate
from app import models
