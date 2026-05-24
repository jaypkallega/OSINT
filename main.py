"""
FastAPI Backend for OSINT Privacy Intelligence App.
Handles scanning logic using Sherlock, Holehe, Maigret, and HIBP.
"""
import os
import sys
import json
import subprocess
import re
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# --- Configuration ---
APP_VERSION = "1.0.0"
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")  # Optional: Set your HIBP API key here or in .env

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

# --- Helper Functions ---

def get_venv_script_path(script_name: str) -> str:
    """
    Constructs the full path to a script executable in the current virtual environment.
    Handles Windows (.exe) and Unix variations.
    """
    venv_path = os.environ.get("VIRTUAL_ENV")
    if not venv_path:
        return script_name  # Fallback to PATH if not in venv
    
    if os.name == 'nt':  # Windows
        scripts_dir = os.path.join(venv_path, "Scripts")
        # Check for .exe extension
        exe_path = os.path.join(scripts_dir, f"{script_name}.exe")
        if os.path.exists(exe_path):
            return exe_path
        # Fallback without extension (sometimes happens with symlinks)
        basic_path = os.path.join(scripts_dir, script_name)
        if os.path.exists(basic_path):
            return basic_path
        return exe_path # Return expected path even if missing to trigger error
    else:  # Linux/Mac
        return os.path.join(venv_path, "bin", script_name)

def run_sherlock(username: str) -> List[Dict[str, Any]]:
    """
    Runs Sherlock to find social media accounts by username.
    Returns a list of found accounts.
    """
    sherlock_cmd = get_venv_script_path("sherlock")
    results = []
    
    try:
        # Command: sherlock --json --timeout 30 <username>
        cmd = [sherlock_cmd, "--json", "--timeout", "30", "--no-color", username]
        
        print(f"🔍 Running Sherlock: {' '.join(cmd)}")
        
        # Run process
        # creationflags=subprocess.CREATE_NO_WINDOW prevents a console window from popping up on Windows
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode != 0 and not result.stdout:
            print(f"⚠️ Sherlock returned non-zero exit code: {result.stderr}")
            # Sherlock often returns non-zero if some sites fail, but still outputs JSON. 
            # We only care if there is NO output.
            if not result.stdout.strip():
                return [{"error": f"Sherlock failed: {result.stderr}"}]

        # Parse JSON output
        # Sherlock outputs one JSON object per line or a single JSON object depending on version
        # Modern versions with --json output a single JSON object at the end
        try:
            data = json.loads(result.stdout)
            for site, info in data.items():
                status = info.get("status", {})
                http_status = status.get("http_status", 0)
                
                if http_status == 200:
                    results.append({
                        "platform": site,
                        "username": username,
                        "url": info.get("url", ""),
                        "source_tool": "Sherlock",
                        "status": "Found"
                    })
        except json.JSONDecodeError:
            # Fallback: Try to parse line-by-line if it's NDJSON
            for line in result.stdout.splitlines():
                if line.strip():
                    try:
                        item = json.loads(line)
                        # Logic similar to above
                        for site, info in item.items():
                            if info.get("status", {}).get("http_status") == 200:
                                results.append({
                                    "platform": site,
                                    "username": username,
                                    "url": info.get("url", ""),
                                    "source_tool": "Sherlock",
                                    "status": "Found"
                                })
                    except json.JSONDecodeError:
                        continue
            
            if not results and result.stdout:
                print(f"⚠️ Could not parse Sherlock output: {result.stdout[:200]}")

    except FileNotFoundError:
        return [{"error": f"Sherlock executable not found at {sherlock_cmd}. Is it installed?"}]
    except subprocess.TimeoutExpired:
        return [{"error": "Sherlock scan timed out."}]
    except Exception as e:
        return [{"error": f"Sherlock error: {str(e)}"}]
    
    return results if results else [{"warning": f"No accounts found for username '{username}'"}]

def run_holehe(email: str) -> List[Dict[str, Any]]:
    """
    Runs Holehe to check if an email is registered on various sites.
    """
    holehe_cmd = get_venv_script_path("holehe")
    results = []
    
    try:
        # Command: holehe --json <email>
        cmd = [holehe_cmd, "--json", email]
        
        print(f"🔍 Running Holehe: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if not result.stdout:
            if result.stderr:
                return [{"error": f"Holehe error: {result.stderr}"}]
            return [{"warning": "No registrations found."}]

        # Holehe outputs NDJSON (one JSON object per line)
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("registered", False):
                    results.append({
                        "platform": data.get("name", "Unknown"),
                        "username": email.split('@')[0], # Holehe doesn't always return username
                        "url": data.get("url", ""),
                        "source_tool": "Holehe",
                        "status": "Registered"
                    })
            except json.JSONDecodeError:
                continue
                
    except FileNotFoundError:
        return [{"error": f"Holehe executable not found at {holehe_cmd}. Is it installed?"}]
    except subprocess.TimeoutExpired:
        return [{"error": "Holehe scan timed out."}]
    except Exception as e:
        return [{"error": f"Holehe error: {str(e)}"}]
    
    return results if results else [{"warning": "No registered accounts found."}]

def run_maigret(username_or_email: str) -> List[Dict[str, Any]]:
    """
    Runs Maigret for a comprehensive scan.
    Note: Maigret can be slow. We limit the number of sites or use a timeout.
    """
    maigret_cmd = get_venv_script_path("maigret")
    results = []
    
    try:
        # Command: maigret -j -n 100 --timeout 30 <query>
        # -j: JSON output
        # -n 100: Limit to top 100 sites for speed
        cmd = [maigret_cmd, "-j", "-n", "50", "--timeout", "20", "--no-progressbar", username_or_email]
        
        print(f"🔍 Running Maigret: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90, # Maigret can take longer
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if not result.stdout:
            if "not found" in result.stderr.lower():
                 return [{"warning": "Maigret found no results."}]
            return [{"error": f"Maigret error: {result.stderr}"}]

        # Maigret JSON output structure is complex. 
        # It usually wraps results in a dictionary where keys are the query.
        try:
            full_data = json.loads(result.stdout)
            # Extract the specific report for our query
            report = full_data.get(username_or_email, {})
            sites = report.get("sites", {})
            
            for site_name, site_data in sites.items():
                status = site_data.get("status", {})
                if status.get("id") == "claimed": # 'claimed' means found
                    results.append({
                        "platform": site_name,
                        "username": site_data.get("username", username_or_email),
                        "url": site_data.get("url", ""),
                        "source_tool": "Maigret",
                        "status": "Found"
                    })
        except json.JSONDecodeError:
            return [{"error": "Failed to parse Maigret JSON output."}]
            
    except FileNotFoundError:
        return [{"error": f"Maigret executable not found at {maigret_cmd}. Is it installed?"}]
    except subprocess.TimeoutExpired:
        return [{"warning": "Maigret scan timed out (partial results may exist)."}]
    except Exception as e:
        return [{"error": f"Maigret error: {str(e)}"}]
    
    return results if results else [{"warning": "No accounts found by Maigret."}]

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
        "User-Agent": "OSINT-Privacy-App/1.0"
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
                return [] # No breaches found
            elif response.status_code == 429:
                return [{"error": "HIBP rate limit exceeded."}]
            else:
                return [{"error": f"HIBP API error: {response.status_code}"}]
    except Exception as e:
        return [{"error": f"HIBP connection failed: {str(e)}"}]

# --- Pydantic Models ---

class ScanRequest(BaseModel):
    email: str
    username: Optional[str] = None
    password: Optional[str] = None
    check_breaches: bool = True
    check_social: bool = True

class PasswordCheckRequest(BaseModel):
    password: str

# --- API Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/api/scan")
async def perform_scan(request: ScanRequest):
    """
    Main scanning endpoint. Orchestrates Sherlock, Holehe, Maigret, and HIBP.
    """
    email = request.email
    username = request.username or email.split('@')[0] # Default to email prefix
    
    results = {
        "email": email,
        "username": username,
        "breaches": [],
        "social_accounts": [],
        "password_exposed": None,
        "exposure_score": 0
    }
    
    # 1. Check Breaches (HIBP)
    if request.check_breaches:
        print(f"Checking breaches for {email}...")
        results["breaches"] = await check_hibp(email)
    
    # 2. Check Social Accounts (Holehe - Email based)
    if request.check_social:
        print(f"Checking email registrations for {email}...")
        holehe_results = run_holehe(email)
        results["social_accounts"].extend(holehe_results)
        
        # 3. Check Username (Sherlock - Username based)
        print(f"Checking username '{username}' with Sherlock...")
        sherlock_results = run_sherlock(username)
        # Deduplicate slightly by checking platform names if needed, but for now just append
        results["social_accounts"].extend(sherlock_results)
        
        # 4. Deep Scan (Maigret - Optional, can be slow)
        # Uncomment if you want Maigret to run every time (adds significant time)
        # print(f"Running Maigret on {username}...")
        # maigret_results = run_maigret(username)
        # results["social_accounts"].extend(maigret_results)

    # 5. Calculate Simple Exposure Score
    breach_count = len([b for b in results["breaches"] if "error" not in b and "warning" not in b])
    account_count = len([a for a in results["social_accounts"] if "error" not in a and "warning" not in a])
    
    score = 0
    score += breach_count * 15
    score += account_count * 5
    if breach_count > 3: score += 20
    if account_count > 10: score += 10
    
    results["exposure_score"] = min(score, 100) # Cap at 100
    
    return results

@app.post("/api/password/check")
def check_password_endpoint(request: PasswordCheckRequest):
    """
    Checks if a password has been exposed using K-Anonymity model (PwnedPasswords).
    Does not send the full password over the network.
    """
    import hashlib
    import requests
    
    password = request.password
    sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]
    
    try:
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        response = requests.get(url) # Using sync requests for simplicity here, could be async
        
        if response.status_code != 200:
            return {"error": "Failed to connect to PwnedPasswords API"}
        
        # Check if suffix exists in response
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
    """
    Quick endpoint to get just the exposure score (placeholder logic).
    In a real app, this would query a database of previous scans.
    """
    # Placeholder: Random score for demo if no scan performed
    import random
    return {
        "email": email,
        "score": random.randint(10, 90),
        "breach_count": 0,
        "social_account_count": 0,
        "message": "Run a full scan for accurate data."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
