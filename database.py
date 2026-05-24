"""
Database models for SQLite storage.
Stores scan results, user data, and monitoring history.
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings

Base = declarative_base()

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ScanTarget(Base):
    """Person/entity being monitored"""
    __tablename__ = "scan_targets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    phone = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BreachRecord(Base):
    """Data breach records from HIBP"""
    __tablename__ = "breach_records"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    breach_name = Column(String)
    breach_date = Column(String)
    added_date = Column(String)
    description = Column(Text)
    data_classes = Column(JSON)  # List of compromised data types
    is_verified = Column(Boolean, default=True)
    is_fabricated = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    is_retired = Column(Boolean, default=False)
    is_spam_list = Column(Boolean, default=False)
    logo_path = Column(String, nullable=True)
    pwn_count = Column(Integer, nullable=True)
    domain = Column(String, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)


class SocialAccount(Base):
    """Discovered social media accounts"""
    __tablename__ = "social_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    platform = Column(String)  # Twitter, Facebook, Instagram, etc.
    url = Column(String)
    exists = Column(Boolean, default=True)
    http_status = Column(Integer, nullable=True)
    email_associated = Column(String, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    source_tool = Column(String)  # Sherlock, Holehe, Maigret


class DomainRecord(Base):
    """Domain information from theHarvester"""
    __tablename__ = "domain_records"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    subdomain = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    email = Column(String, nullable=True)
    virtual_host = Column(String, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    source_tool = Column(String)


class DataBroker(Base):
    """Data broker listings and opt-out tracking"""
    __tablename__ = "data_brokers"
    
    id = Column(Integer, primary_key=True, index=True)
    broker_name = Column(String)
    person_name = Column(String)
    url = Column(String)
    opt_out_url = Column(String, nullable=True)
    opt_out_submitted = Column(Boolean, default=False)
    opt_out_date = Column(DateTime, nullable=True)
    confirmed_removed = Column(Boolean, default=False)
    last_checked = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class ExposureScore(Base):
    """Privacy exposure score history"""
    __tablename__ = "exposure_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    score = Column(Float)  # 0-100
    breach_count = Column(Integer, default=0)
    social_account_count = Column(Integer, default=0)
    broker_listing_count = Column(Integer, default=0)
    password_compromised = Column(Boolean, default=False)
    calculated_at = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, nullable=True)  # Breakdown of scoring


class MonitoringJob(Base):
    """Scheduled monitoring jobs"""
    __tablename__ = "monitoring_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    target_email = Column(String, index=True)
    job_type = Column(String)  # 'breach', 'social', 'full'
    schedule = Column(String)  # cron expression or interval
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    last_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Security alerts"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String)  # 'new_breach', 'new_account', 'password_exposed'
    severity = Column(String)  # 'low', 'medium', 'high', 'critical'
    title = Column(String)
    message = Column(Text)
    related_email = Column(String, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
