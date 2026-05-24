"""
FastAPI backend for OSINT Privacy Intelligence App.
Provides REST API endpoints for all OSINT operations.
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime
import uvicorn

from config import settings
from database import init_db, get_db, SessionLocal
from database import (
    ScanTarget, BreachRecord, SocialAccount, ExposureScore, Alert
)
from tools.breacher import HIBPClient, check_email_breaches, check_password_exposure
from tools.footprint import SocialFootprintScanner, scan_social_footprint
from tools.graph import get_graph

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Personal OSINT Privacy Intelligence Platform"
)

# CORS middleware (for local frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class ScanRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    check_breaches: bool = True
    check_social: bool = True
    password: Optional[str] = None  # For password exposure check


class ScanResponse(BaseModel):
    email: str
    username: Optional[str] = None
    breaches: List[Dict[str, Any]] = []
    social_accounts: List[Dict[str, Any]] = []
    password_exposed: Optional[Dict[str, Any]] = None
    exposure_score: float = 0.0
    graph_updated: bool = False


class PasswordCheckRequest(BaseModel):
    password: str


class PasswordCheckResponse(BaseModel):
    found: bool
    count: int
    message: str


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"📍 Backend running on http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}")


# Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "backend": "ok",
        "database": "ok",
        "neo4j": "connected" if get_graph().driver else "disconnected"
    }


@app.post("/api/scan", response_model=ScanResponse)
async def perform_scan(request: ScanRequest):
    """
    Perform comprehensive OSINT scan on email/username.
    
    This endpoint:
    1. Checks email breaches via HIBP
    2. Checks password exposure (if provided)
    3. Discovers social media accounts
    4. Updates Neo4j graph
    5. Calculates exposure score
    """
    db = SessionLocal()
    
    try:
        result = ScanResponse(email=request.email, username=request.username)
        
        # 1. Check breaches (requires HIBP API key)
        if request.check_breaches:
            try:
                if settings.HIBP_API_KEY:
                    breaches = check_email_breaches(request.email, settings.HIBP_API_KEY)
                    result.breaches = breaches
                    
                    # Store in database
                    for breach in breaches:
                        db_record = BreachRecord(
                            email=request.email,
                            breach_name=breach.get("Name", "Unknown"),
                            breach_date=breach.get("BreachDate", ""),
                            description=breach.get("Description", ""),
                            data_classes=breach.get("DataClasses", []),
                            is_verified=breach.get("IsVerified", True),
                            domain=breach.get("Domain", "")
                        )
                        db.add(db_record)
                    
                    db.commit()
                else:
                    result.breaches = [{"warning": "HIBP API key not configured"}]
            except Exception as e:
                result.breaches.append({"error": str(e)})
        
        # 2. Check password exposure (free, no API key needed)
        if request.password:
            try:
                password_result = check_password_exposure(request.password)
                result.password_exposed = password_result
            except Exception as e:
                result.password_exposed = {"error": str(e)}
        
        # 3. Discover social accounts
        if request.check_social and request.username:
            try:
                scanner = SocialFootprintScanner()
                footprint_results = scanner.scan_comprehensive(request.username, request.email)
                result.social_accounts = footprint_results.get("accounts", [])
                
                # Store in database
                for account in result.social_accounts:
                    db_record = SocialAccount(
                        username=account.get("username", request.username),
                        platform=account.get("platform", "Unknown"),
                        url=account.get("url", ""),
                        exists=account.get("exists", True),
                        http_status=account.get("http_status"),
                        email_associated=request.email,
                        source_tool=account.get("source_tool", "Unknown")
                    )
                    db.add(db_record)
                
                db.commit()
            except Exception as e:
                result.social_accounts.append({"error": str(e)})
        
        # 4. Update Neo4j graph
        try:
            graph = get_graph()
            if graph.driver:
                graph.populate_from_scan_results(
                    email=request.email,
                    username=request.username,
                    breaches=result.breaches if result.breaches and "error" not in result.breaches[0] else None,
                    social_accounts=result.social_accounts if result.social_accounts and "error" not in result.social_accounts[0] else None
                )
                result.graph_updated = True
        except Exception as e:
            pass  # Graph update is optional
        
        # 5. Calculate exposure score
        password_compromised = False
        if result.password_exposed and isinstance(result.password_exposed, dict):
            password_compromised = result.password_exposed.get("found", False)
        
        result.exposure_score = calculate_exposure_score(
            breach_count=len([b for b in result.breaches if "error" not in b and "warning" not in b]),
            social_count=len([s for s in result.social_accounts if "error" not in s]),
            password_compromised=password_compromised
        )
        
        # Store exposure score
        password_compromised = False
        if result.password_exposed and isinstance(result.password_exposed, dict):
            password_compromised = result.password_exposed.get("found", False)
        
        score_record = ExposureScore(
            email=request.email,
            score=result.exposure_score,
            breach_count=len(result.breaches),
            social_account_count=len(result.social_accounts),
            password_compromised=password_compromised,
            details={
                "breaches": len(result.breaches),
                "social_accounts": len(result.social_accounts),
                "password_exposed": result.password_exposed
            }
        )
        db.add(score_record)
        db.commit()
        
        return result
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/password/check", response_model=PasswordCheckResponse)
async def check_password(request: PasswordCheckRequest):
    """
    Check if a password has been exposed in data breaches.
    Uses k-anonymity - password never leaves your device.
    Free to use, no API key required.
    """
    try:
        result = check_password_exposure(request.password)
        return PasswordCheckResponse(
            found=result["found"],
            count=result["count"],
            message=result["message"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/breaches/{email}")
async def get_breaches(email: str):
    """Get breach records for an email from database"""
    db = SessionLocal()
    try:
        breaches = db.query(BreachRecord).filter(BreachRecord.email == email).all()
        return [
            {
                "id": b.id,
                "breach_name": b.breach_name,
                "breach_date": b.breach_date,
                "description": b.description,
                "data_classes": b.data_classes,
                "discovered_at": b.discovered_at.isoformat()
            }
            for b in breaches
        ]
    finally:
        db.close()


@app.get("/api/social-accounts/{username}")
async def get_social_accounts(username: str):
    """Get discovered social accounts for a username"""
    db = SessionLocal()
    try:
        accounts = db.query(SocialAccount).filter(
            SocialAccount.username == username
        ).all()
        return [
            {
                "id": a.id,
                "platform": a.platform,
                "url": a.url,
                "exists": a.exists,
                "source_tool": a.source_tool,
                "discovered_at": a.discovered_at.isoformat()
            }
            for a in accounts
        ]
    finally:
        db.close()


@app.get("/api/exposure-score/{email}")
async def get_exposure_score(email: str):
    """Get latest exposure score for an email"""
    db = SessionLocal()
    try:
        scores = db.query(ExposureScore).filter(
            ExposureScore.email == email
        ).order_by(ExposureScore.calculated_at.desc()).limit(1).all()
        
        if scores:
            score = scores[0]
            return {
                "email": score.email,
                "score": score.score,
                "breach_count": score.breach_count,
                "social_account_count": score.social_account_count,
                "password_compromised": score.password_compromised,
                "calculated_at": score.calculated_at.isoformat(),
                "details": score.details
            }
        else:
            return {"error": "No score found for this email"}
    finally:
        db.close()


def calculate_exposure_score(
    breach_count: int,
    social_count: int,
    password_compromised: bool
) -> float:
    """
    Calculate privacy exposure score (0-100).
    
    Higher score = more exposed
    
    Weights:
    - Each breach: +15 points
    - Each social account: +5 points
    - Password compromised: +25 points
    """
    score = 0.0
    
    # Breach impact
    score += min(breach_count * 15, 50)  # Max 50 from breaches
    
    # Social footprint
    score += min(social_count * 5, 25)  # Max 25 from social
    
    # Password compromise
    if password_compromised:
        score += 25
    
    return min(score, 100)  # Cap at 100


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
