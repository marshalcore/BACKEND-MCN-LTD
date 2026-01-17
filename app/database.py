# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging
import urllib.parse

# Set up logging
logger = logging.getLogger(__name__)

def get_database_url() -> str:
    """Get and validate database URL"""
    db_url = settings.DATABASE_URL.strip()
    
    # Remove any stray quotes or apostrophes
    db_url = db_url.strip("'").strip('"')
    
    logger.info(f"Database URL (cleaned): {db_url}")
    
    # Parse URL to check for Neon.tech
    parsed_url = urllib.parse.urlparse(db_url)
    
    # For Neon.tech, ensure SSL is configured properly
    if "neon.tech" in parsed_url.netloc:
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Add sslmode=require if not present
        if 'sslmode' not in query_params:
            if parsed_url.query:
                db_url += "&sslmode=require"
            else:
                db_url += "?sslmode=require"
            logger.info("Added sslmode=require to Neon database URL")
        
        # Ensure channel_binding is valid
        if 'channel_binding' in query_params:
            channel_value = query_params['channel_binding'][0]
            if not channel_value in ['require', 'prefer', 'disable']:
                logger.warning(f"Invalid channel_binding value: {channel_value}")
                # Remove invalid channel_binding
                db_url = db_url.replace(f"channel_binding={channel_value}", "channel_binding=require")
                logger.info("Fixed channel_binding to 'require'")
    
    return db_url

# Get cleaned database URL
DATABASE_URL = get_database_url()

try:
    engine = create_engine(
        DATABASE_URL,
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
    logger.error(f"Database URL being used: {DATABASE_URL}")
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