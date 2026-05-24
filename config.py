"""
Configuration settings for the OSINT Privacy Intelligence App.
All data stays local - no external exposure.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OSINT Privacy Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Backend
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./privacy_intelligence.db"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"  # Change this!
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # HIBP API (optional - paid key for breach lookup)
    HIBP_API_KEY: Optional[str] = None
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
