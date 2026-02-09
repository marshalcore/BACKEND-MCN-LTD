# app/database.py - COMPLETE PRODUCTION VERSION
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings
import logging
import os
import urllib.parse

# Set up logging
logger = logging.getLogger(__name__)

# Get database URL from settings
DATABASE_URL = settings.DATABASE_URL.strip().strip("'").strip('"')

# Log the URL (mask password for security)
def mask_database_url(url: str) -> str:
    """Mask password in database URL for logging"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.password:
            # Replace password with ***
            netloc = parsed.netloc.replace(f":{parsed.password}", ":***")
            masked = urllib.parse.urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return masked
        return url
    except:
        return url

logger.info(f"Database URL: {mask_database_url(DATABASE_URL)}")

# Database connection configuration for production
def create_database_engine(database_url: str = None):
    """Create database engine with production settings"""
    
    # Use provided URL or default from settings
    if database_url is None:
        database_url = DATABASE_URL
    
    # Parse the database URL
    parsed_url = urllib.parse.urlparse(database_url)
    
    # Check if we're using Neon PostgreSQL
    is_neon = "neon.tech" in database_url
    is_production = settings.ENVIRONMENT == "production"
    
    # SSL configuration for production
    ssl_params = {}
    
    if is_production:
        # Production SSL settings
        if is_neon:
            # For Neon, use require SSL
            if "sslmode=" not in database_url:
                if "?" in database_url:
                    database_url += "&sslmode=require"
                else:
                    database_url += "?sslmode=require"
        else:
            # For other production databases, use verify-full
            if "sslmode=" not in database_url:
                if "?" in database_url:
                    database_url += "&sslmode=verify-full"
                else:
                    database_url += "?sslmode=verify-full"
    
    # Pool configuration
    pool_config = {
        "poolclass": QueuePool,
        "pool_size": 20,  # Increased for production
        "max_overflow": 30,  # Allow more overflow connections
        "pool_timeout": 30,  # 30 seconds timeout
        "pool_recycle": 3600,  # Recycle connections every hour
        "pool_pre_ping": True,  # Test connections before use
        "echo": settings.DEBUG,  # Log SQL only in debug mode
        "connect_args": {}
    }
    
    # Add SSL parameters if needed
    if ssl_params:
        pool_config["connect_args"].update(ssl_params)
    
    try:
        logger.info("Creating database engine with production settings...")
        
        engine = create_engine(
            database_url,
            **pool_config
        )
        
        # Test the connection
        logger.info("Testing database connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()")).scalar()
            logger.info(f"✅ Database connection successful!")
            logger.info(f"📊 Database version: {result.split(',')[0]}")
            
            # Check if immediate_transfers table exists
            try:
                check_table = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'immediate_transfers'
                    )
                """)).scalar()
                
                if check_table:
                    logger.info("✅ Immediate transfers table exists")
                else:
                    logger.warning("⚠️ Immediate transfers table not found - run migrations")
                    
            except Exception as table_error:
                logger.warning(f"Could not check immediate_transfers table: {table_error}")
        
        return engine
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        
        # Try alternative configurations
        logger.info("Trying alternative SSL configurations...")
        
        # Try with simpler SSL configuration
        try:
            base_url = database_url.split("?")[0]
            alt_url = f"{base_url}?sslmode=require"
            
            logger.info(f"Trying with sslmode=require...")
            
            alt_engine = create_engine(
                alt_url,
                pool_size=10,
                max_overflow=20,
                pool_recycle=1800,
                pool_pre_ping=True,
                echo=settings.DEBUG
            )
            
            with alt_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Connection successful with sslmode=require")
                return alt_engine
                
        except Exception as e1:
            logger.error(f"❌ Alternative connection failed: {e1}")
            
            # Last resort: try without SSL (not recommended for production)
            if not is_production:
                try:
                    base_url = database_url.split("?")[0]
                    alt_url = f"{base_url}?sslmode=disable"
                    
                    logger.warning(f"⚠️ Trying without SSL (development only)...")
                    
                    alt_engine = create_engine(
                        alt_url,
                        pool_size=5,
                        max_overflow=10,
                        pool_recycle=900,
                        pool_pre_ping=True,
                        echo=settings.DEBUG
                    )
                    
                    with alt_engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                        logger.warning("✅ Connection successful without SSL (NOT FOR PRODUCTION)")
                        return alt_engine
                        
                except Exception as e2:
                    logger.error(f"❌ All connection attempts failed: {e2}")
            
            # Create a mock engine for development if all else fails
            if not is_production:
                logger.warning("⚠️ Creating mock SQLite engine for development...")
                return create_engine("sqlite:///:memory:")
            else:
                raise Exception("Cannot connect to production database")

# Create engine
engine = create_database_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Important for production
)

# Create declarative base
Base = declarative_base()

def get_db():
    """
    Get database session with automatic cleanup
    Optimized for production
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Health check endpoint for database
def check_database_health():
    """Check if database is healthy"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True, "Database is healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False, str(e)

# Initialize tables if needed
def initialize_database():
    """Initialize database tables"""
    try:
        # Import models to ensure they're registered
        from app.models.payment import Payment
        from app.models.immediate_transfer import ImmediateTransfer
        from app.models.applicant import Applicant
        from app.models.pre_applicant import PreApplicant
        from app.models.officer import Officer
        from app.models.existing_officer import ExistingOfficer
        
        # Create tables (in development only - use migrations in production)
        if settings.ENVIRONMENT == "development":
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created")
        else:
            logger.info("Using existing database tables (migrations should handle this)")
            
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

# Call initialization
if __name__ != "__main__":
    initialize_database()