# app/database.py - COMPLETELY FIXED VERSION
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging
import os

# Set up logging
logger = logging.getLogger(__name__)

# Get database URL from settings
DATABASE_URL = settings.DATABASE_URL.strip().strip("'").strip('"')

# Log the URL (mask password for security)
masked_url = DATABASE_URL
if "@" in masked_url:
    parts = masked_url.split("@")
    if ":" in parts[0]:
        user_pass = parts[0].split(":")
        if len(user_pass) > 1:
            user_pass[1] = "***"  # Mask password
            parts[0] = ":".join(user_pass)
            masked_url = "@".join(parts)

logger.info(f"Database URL: {masked_url}")

# For Neon PostgreSQL - use verify-full or remove sslrootcert
if "neon.tech" in DATABASE_URL:
    # Check if URL already has sslmode
    if "sslmode=" not in DATABASE_URL:
        # Add sslmode=require (simplest for Neon)
        if "?" in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
        else:
            DATABASE_URL += "?sslmode=require"
    elif "sslmode=require" in DATABASE_URL and "sslrootcert=system" in DATABASE_URL:
        # FIX: Change to verify-full when using sslrootcert
        DATABASE_URL = DATABASE_URL.replace("sslmode=require", "sslmode=verify-full")
    elif "sslmode=require" in DATABASE_URL and "sslrootcert=" in DATABASE_URL:
        # Remove sslrootcert parameter when using require
        import urllib.parse
        parsed = urllib.parse.urlparse(DATABASE_URL)
        query_params = urllib.parse.parse_qs(parsed.query)
        if 'sslrootcert' in query_params:
            del query_params['sslrootcert']
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        DATABASE_URL = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

logger.info(f"Final Database URL: {DATABASE_URL.split('?')[0]}...")

try:
    # Create engine with minimal configuration first
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Test connection before use
        pool_recycle=300,        # Recycle connections every 5 minutes
        pool_size=5,             # Number of connections to keep
        max_overflow=10,         # Allow overflow connections
        echo=False,              # Don't log SQL (set to True for debugging)
    )
    
    # Test the connection
    logger.info("Testing database connection...")
    with engine.connect() as conn:
        # FIXED: Use text() wrapper for raw SQL
        result = conn.execute(text("SELECT version()")).scalar()
        logger.info(f"✅ Database connection successful!")
        logger.info(f"📊 Database version: {result.split(',')[0]}")
        
except Exception as e:
    logger.error(f"❌ Database connection failed: {e}")
    
    # Try alternative SSL configurations
    logger.info("Trying alternative SSL configurations...")
    
    # Try 1: Use require without sslrootcert
    try:
        # Remove any sslrootcert parameter
        base_url = DATABASE_URL.split("?")[0]
        alt_url = f"{base_url}?sslmode=require"
        
        logger.info(f"Trying URL: {base_url.split('@')[0]}@***")
        
        alt_engine = create_engine(
            alt_url,
            pool_pre_ping=True,
            pool_recycle=300
        )
        
        with alt_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✅ Connection successful with sslmode=require")
            engine = alt_engine
            DATABASE_URL = alt_url
            
    except Exception as e1:
        logger.error(f"❌ Attempt 1 failed: {e1}")
        
        # Try 2: Use verify-full
        try:
            base_url = DATABASE_URL.split("?")[0]
            alt_url = f"{base_url}?sslmode=verify-full"
            
            alt_engine = create_engine(
                alt_url,
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            with alt_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Connection successful with sslmode=verify-full")
                engine = alt_engine
                DATABASE_URL = alt_url
                
        except Exception as e2:
            logger.error(f"❌ Attempt 2 failed: {e2}")
            
            # Try 3: No SSL (should work locally or with trusted networks)
            try:
                base_url = DATABASE_URL.split("?")[0]
                alt_url = f"{base_url}?sslmode=disable"
                
                alt_engine = create_engine(
                    alt_url,
                    pool_pre_ping=True,
                    pool_recycle=300
                )
                
                with alt_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    logger.info("✅ Connection successful with sslmode=disable")
                    engine = alt_engine
                    DATABASE_URL = alt_url
                    
            except Exception as e3:
                logger.error(f"❌ All connection attempts failed")
                logger.error("Last error: %s", e3)
                logger.error("Please check:")
                logger.error("1. Database is running and accessible")
                logger.error("2. Credentials are correct")
                logger.error("3. Network/firewall allows connections")
                logger.error("4. SSL certificates are properly configured")
                
                # Create a mock engine for development (will fail on actual DB operations)
                logger.warning("⚠ Creating mock engine for development (DB operations will fail)")
                engine = create_engine("sqlite:///:memory:")
                with engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS mock (id INTEGER)"))
                    logger.warning("⚠ Using SQLite mock database - real PostgreSQL operations will fail!")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Get database session with automatic cleanup
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# ✅ This line ensures models are registered before Alembic autogenerate