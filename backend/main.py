"""
FastAPI Backend for OSINT Privacy Intelligence App (OPIP).
Handles scanning logic using Sherlock, Holehe, Maigret, HIBP with SQLite persistence and Neo4j graph integration.
"""
import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Import local modules
sys.path.insert(0, os.path.dirname(__file__))
from database import init_db, create_user, create_scan, save_breach_records, save_social_accounts, get_scan_details
from graph_db import init_neo4j, close_neo4j, neo4j_manager
from modules.osint_tools import run_sherlock, run_holehe, run_maigret, check_all_tools

# --- Configuration ---
APP_VERSION = "2.0.0"
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")

# Initialize FastAPI app
app = FastAPI(title="OSINT Privacy Intelligence API", version=APP_VERSION)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Startup/Shutdown Events ---

@app.on_event("startup")
async def startup_event():
    """Initialize database and Neo4j on startup."""
    print("🚀 Starting OPIP Backend v2.0...")
    init_db()
    init_neo4j()
    
    # Check tools
    tools_status = check_all_tools()
    for tool, available in tools_status.items():
        icon = "✅" if available else "❌"
        print(f"{icon} {tool}: {'Available' if available else 'NOT FOUND'}")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown."""
    close_neo4j()
    print("👋 Backend shutdown complete.")

# --- Pydantic Models ---

class ScanRequest(BaseModel):
    email: str
    username: Optional[str] = None
    password: Optional[str] = None
    check_breaches: bool = True
    check_social: bool = True
    run_maigret: bool = False  # Optional deep scan

class PasswordCheckRequest(BaseModel):
    password: str

class PhoneScanRequest(BaseModel):
    phone_number: str
    owner_confirmed: bool = False

class BrokerOptOutRequest(BaseModel):
    broker_name: str
    profile_url: Optional[str] = None
    optout_url: Optional[str] = None

# --- Helper Functions ---

async def check_hibp(email: str) -> List[Dict[str, Any]]:
    """
    Checks Have I Been Pwned API for breaches.
    Requires an API key.
    """
    if not HIBP_API_KEY:
        return [{"warning": "HIBP API key not configured. Breach check skipped."}]
    
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    headers = {
        "hibp-api-key": HIBP_API_KEY,
        "User-Agent": "OPIP/2.0"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                breaches = response.json()
                formatted_breaches = []
                for b in breaches:
                    formatted_breaches.append({
                        "Name": b.get("Name"),
                        "BreachDate": b.get("BreachDate"),
                        "Description": b.get("Description"),
                        "DataClasses": b.get("DataClasses", []),
                        "PwnCount": b.get("PwnCount"),
                        "IsVerified": b.get("IsVerified")
                    })
                return formatted_breaches
            elif response.status_code == 404:
                return []  # No breaches found
            elif response.status_code == 429:
                return [{"error": "HIBP rate limit exceeded."}]
            else:
                return [{"error": f"HIBP API error: {response.status_code}"}]
    except Exception as e:
        return [{"error": f"HIBP connection failed: {str(e)}"}]

def calculate_exposure_score(breaches: List, social_accounts: List, password_compromised: bool = False) -> float:
    """Calculate exposure score based on findings."""
    score = 0.0
    
    # Breach component (max 35 points)
    valid_breaches = [b for b in breaches if 'error' not in b and 'warning' not in b]
    score += min(len(valid_breaches) * 5, 35)
    
    # Sensitive breach bonus (max 15 points)
    sensitive_keywords = ['password', 'ssn', 'credit', 'address', 'phone']
    sensitive_count = 0
    for b in valid_breaches:
        data_classes = b.get('DataClasses', [])
        if any(keyword in str(dc).lower() for keyword in sensitive_keywords for dc in data_classes):
            sensitive_count += 1
    score += min(sensitive_count * 7, 15)
    
    # Password compromise (max 10 points)
    if password_compromised:
        score += 10
    
    # Social footprint (max 15 points)
    valid_accounts = [a for a in social_accounts if 'error' not in a and 'warning' not in a]
    score += min(len(valid_accounts) * 2, 15)
    
    # Large footprint bonus (max 10 points)
    if len(valid_accounts) > 10:
        score += 10
    
    # Large breach count bonus (max 15 points)
    if len(valid_breaches) > 3:
        score += 15
    
    return min(score, 100)

# --- API Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/api/scan")
async def perform_scan(request: ScanRequest):
    """
    Main scanning endpoint. Orchestrates Sherlock, Holehe, Maigret, and HIBP.
    Stores results in SQLite and Neo4j.
    """
    email = request.email
    username = request.username or email.split('@')[0]
    
    # Create scan record
    scan_id = create_scan(user_id=None, query=email, query_type='email')
    
    results = {
        "email": email,
        "username": username,
        "scan_id": scan_id,
        "breaches": [],
        "social_accounts": [],
        "password_exposed": None,
        "exposure_score": 0
    }
    
    # 1. Check Breaches (HIBP)
    if request.check_breaches:
        print(f"Checking breaches for {email}...")
        results["breaches"] = await check_hibp(email)
    
    # 2. Check Email Registrations (Holehe)
    if request.check_social:
        print(f"Checking email registrations for {email}...")
        holehe_results = run_holehe(email)
        results["social_accounts"].extend(holehe_results)
        
        # 3. Check Username (Sherlock)
        print(f"Checking username '{username}' with Sherlock...")
        sherlock_results = run_sherlock(username)
        results["social_accounts"].extend(sherlock_results)
        
        # 4. Deep Scan (Maigret) - Optional
        if request.run_maigret:
            print(f"Running Maigret on {username}...")
            maigret_results = run_maigret(username, max_sites=50)
            results["social_accounts"].extend(maigret_results)
    
    # 5. Calculate Exposure Score
    results["exposure_score"] = calculate_exposure_score(
        results["breaches"], 
        results["social_accounts"],
        False  # Password not checked here
    )
    
    # 6. Save to Database
    save_breach_records(scan_id, email, results["breaches"])
    save_social_accounts(scan_id, results["social_accounts"], email)
    
    # 7. Build Neo4j Graph
    neo4j_manager.build_graph_from_scan(
        email, 
        username, 
        results["breaches"], 
        results["social_accounts"]
    )
    
    return results

@app.post("/api/password/check")
def check_password_endpoint(request: PasswordCheckRequest):
    """
    Checks if a password has been exposed using K-Anonymity model (PwnedPasswords).
    """
    import hashlib
    import requests
    
    password = request.password
    sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]
    
    try:
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"error": "Failed to connect to PwnedPasswords API"}
        
        for line in response.text.splitlines():
            hash_suffix, count = line.split(':')
            if hash_suffix == suffix:
                return {
                    "found": True,
                    "count": int(count),
                    "message": "This password has been seen in breaches!"
                }
        
        return {"found": False, "count": 0, "message": "Password not found in breaches."}
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/exposure-score/{email}")
def get_exposure_score(email: str):
    """Get exposure score from last scan or calculate placeholder."""
    # In production, query DB for last scan
    return {
        "email": email,
        "score": 0,
        "breach_count": 0,
        "social_account_count": 0,
        "message": "Run a full scan for accurate data."
    }

@app.get("/api/scan/history/{scan_id}")
def get_scan_history(scan_id: int):
    """Get detailed results of a previous scan."""
    scan_data = get_scan_details(scan_id)
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan_data

@app.post("/api/phone/scan")
def scan_phone(request: PhoneScanRequest):
    """
    Guarded phone number scan. Requires owner confirmation.
    """
    if not request.owner_confirmed:
        return {
            "error": "Ownership confirmation required",
            "message": "Please confirm this is your own phone number before scanning."
        }
    
    # Placeholder - implement PhoneInfoga integration
    return {
        "phone_number": request.phone_number,
        "valid": True,
        "carrier": "Unknown",
        "country": "Unknown",
        "line_type": "Unknown",
        "owner_confirmed": True
    }

@app.post("/api/broker/optout")
def add_broker_optout(request: BrokerOptOutRequest, user_id: int = 1):
    """Add a new data broker opt-out request."""
    # Placeholder - integrate with database module
    return {
        "status": "pending",
        "broker_name": request.broker_name,
        "message": f"Opt-out request added for {request.broker_name}"
    }

@app.get("/api/broker/list")
def list_brokers():
    """List all supported data brokers with opt-out URLs."""
    BROKERS = {
        "Spokeo": "https://www.spokeo.com/optout",
        "WhitePages": "https://www.whitepages.com/suppression-requests",
        "Intelius": "https://www.intelius.com/opt-out/submit/",
        "BeenVerified": "https://www.beenverified.com/app/optout/search",
        "MyLife": "https://www.mylife.com/ccpa/index.pubview",
        "Radaris": "https://radaris.com/control/privacy",
        "PeopleFinder": "https://www.peoplefinders.com/opt-out",
        "TruthFinder": "https://www.truthfinder.com/opt-out/",
        "FamilyTreeNow": "https://www.familytreenow.com/optout",
        "Pipl": "https://pipl.com/personal-information-removal-request/"
    }
    return BROKERS

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
