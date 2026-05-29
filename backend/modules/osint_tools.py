"""
OSINT Tools Module for OPIP.
Handles execution of Sherlock, Holehe, Maigret with robust error handling and JSON parsing.
"""
import os
import sys
import json
import subprocess
from typing import List, Dict, Any

def get_venv_script_path(script_name: str) -> str:
    """
    Constructs the full path to a script executable.
    Checks venv first, then global PATH.
    """
    import shutil
    
    # Check virtual environment first
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        if os.name == 'nt':  # Windows
            scripts_dir = os.path.join(venv_path, "Scripts")
            exe_path = os.path.join(scripts_dir, f"{script_name}.exe")
            if os.path.exists(exe_path):
                return exe_path
        else:  # Linux/Mac
            bin_path = os.path.join(venv_path, "bin", script_name)
            if os.path.exists(bin_path):
                return bin_path
    
    # Fallback to system PATH using shutil.which
    system_path = shutil.which(script_name)
    if system_path:
        return system_path
    
    # Last resort: return script name and let subprocess handle PATH lookup
    return script_name

def run_sherlock(username: str) -> List[Dict[str, Any]]:
    """
    Runs Sherlock to find social media accounts by username.
    Returns a list of found accounts.
    Directly uses --json <file> method for reliability on all Sherlock versions.
    """
    import tempfile
    
    sherlock_cmd = get_venv_script_path("sherlock")
    results = []
    
    # Verify executable exists
    if not os.path.exists(sherlock_cmd):
        return [{"error": f"Sherlock executable not found at {sherlock_cmd}. Install with: pip install sherlock-project"}]
    
    # Create a temporary file for JSON output
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
    os.close(temp_fd)
    
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    
    try:
        # Directly use --json <filename> which works on all Sherlock versions
        # Command: sherlock --json <tempfile> --timeout 30 <username>
        cmd = [sherlock_cmd, "--json", temp_path, "--timeout", "30", "--no-color", username]
        
        print(f"🔍 Running Sherlock (JSON mode): {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=creationflags
        )
        
        # Check for command-line errors (usage errors, argument errors, etc.)
        if result.returncode != 0 and result.stderr:
            err_msg = result.stderr.strip()
            if "usage" in err_msg.lower() or "error:" in err_msg.lower() or "expected one argument" in err_msg.lower():
                print(f"⚠️ Sherlock command error: {err_msg}")
                return [{"error": f"Sherlock command failed: {err_msg}"}]
        
        # Check if the JSON file was created and has content
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            if result.returncode != 0 and result.stderr:
                print(f"⚠️ Sherlock error (no output): {result.stderr}")
                return [{"error": f"Sherlock failed: {result.stderr}"}]
            return [{"warning": f"No accounts found for username '{username}'"}]

        # Parse the JSON file
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Sherlock JSON structure: { "username": { "site": { ... } } } or { "site": { ... } }
            user_data = {}
            if username in data:
                user_data = data[username]
            else:
                user_data = data
            
            for site, info in user_data.items():
                if isinstance(info, dict):
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
            
            return results if results else [{"warning": f"No accounts found for username '{username}'"}]
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parsing Sherlock JSON file: {e}")
            # Try to read raw content for debugging
            try:
                with open(temp_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                print(f"Raw JSON content: {raw_content[:500]}")
            except Exception:
                pass
            return [{"error": "Failed to parse Sherlock results."}]
        except Exception as e:
            print(f"⚠️ Error reading Sherlock results: {e}")
            return [{"error": f"Error reading results: {str(e)}"}]
            
    except subprocess.TimeoutExpired:
        return [{"error": "Sherlock scan timed out after 60 seconds."}]
    except Exception as e:
        return [{"error": f"Sherlock error: {str(e)}"}]
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
    
    return results if results else [{"warning": f"No accounts found for username '{username}'"}]

def run_holehe(email: str) -> List[Dict[str, Any]]:
    """
    Runs Holehe to check if an email is registered on various sites.
    Uses --csv flag for machine-readable output.
    """
    holehe_cmd = get_venv_script_path("holehe")
    results = []
    
    # Verify executable exists
    if not os.path.exists(holehe_cmd):
        return [{"error": f"Holehe executable not found at {holehe_cmd}. Install with: pip install holehe"}]
    
    try:
        # Command: holehe --timeout 10 <email>
        # We'll parse the text output for registered sites
        cmd = [holehe_cmd, "--timeout", "10", "--no-color", email]
        
        print(f"🔍 Running Holehe: {' '.join(cmd)}")
        
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=creationflags
        )
        
        if not result.stdout.strip():
            if result.stderr:
                return [{"error": f"Holehe error: {result.stderr.strip()}"}]
            return [{"warning": "No registrations found."}]

        # Parse Holehe output looking for registered sites
        # Format varies, but registered sites usually show with URL
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # Look for lines indicating registration
            if "http" in line or ("[" in line and "]" in line and "used" in line.lower()):
                # Extract site name and URL
                if "http" in line:
                    # Try to extract platform name from context
                    parts = line.split()
                    url = None
                    for part in parts:
                        if part.startswith("http"):
                            url = part
                            break
                    
                    if url:
                        # Extract domain as platform name
                        platform = url.split("//")[1].split("/")[0] if "//" in url else url.split("/")[0]
                        results.append({
                            "platform": platform,
                            "username": email.split('@')[0],
                            "url": url,
                            "source_tool": "Holehe",
                            "status": "Registered"
                        })
            
    except FileNotFoundError:
        return [{"error": f"Holehe executable not found at {holehe_cmd}"}]
    except subprocess.TimeoutExpired:
        return [{"error": "Holehe scan timed out after 60 seconds."}]
    except Exception as e:
        return [{"error": f"Holehe error: {str(e)}"}]
    
    return results if results else [{"warning": "No registered accounts found."}]

def run_maigret(username_or_email: str, max_sites: int = 50) -> List[Dict[str, Any]]:
    """
    Runs Maigret for a comprehensive scan.
    Limited to top N sites for speed.
    """
    maigret_cmd = get_venv_script_path("maigret")
    results = []
    
    # Verify executable exists
    if not os.path.exists(maigret_cmd):
        return [{"error": f"Maigret executable not found at {maigret_cmd}. Install with: pip install maigret"}]
    
    try:
        # Command: maigret -j -n 50 --timeout 20 --no-progressbar <query>
        cmd = [maigret_cmd, "-j", "-n", str(max_sites), "--timeout", "20", "--no-progressbar", username_or_email]
        
        print(f"🔍 Running Maigret: {' '.join(cmd)}")
        
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=creationflags
        )
        
        if not result.stdout.strip():
            if "not found" in result.stderr.lower():
                 return [{"warning": "Maigret found no results."}]
            if result.stderr:
                return [{"error": f"Maigret error: {result.stderr.strip()}"}]
            return [{"warning": "Maigret returned no output."}]

        # Maigret JSON output structure: {query: {sites: {...}}}
        try:
            full_data = json.loads(result.stdout)
            # Extract the specific report for our query
            report = full_data.get(username_or_email, {})
            sites = report.get("sites", {})
            
            for site_name, site_data in sites.items():
                status = site_data.get("status", {})
                # 'claimed' means found, 'available' means not found
                if status.get("id") == "claimed":
                    results.append({
                        "platform": site_name,
                        "username": site_data.get("username", username_or_email),
                        "url": site_data.get("url", ""),
                        "source_tool": "Maigret",
                        "status": "Found"
                    })
        except json.JSONDecodeError as e:
            print(f"⚠️ Could not parse Maigret JSON: {str(e)}")
            return [{"error": "Failed to parse Maigret JSON output."}]
            
    except FileNotFoundError:
        return [{"error": f"Maigret executable not found at {maigret_cmd}"}]
    except subprocess.TimeoutExpired:
        return [{"warning": "Maigret scan timed out after 90 seconds (partial results may exist)."}]
    except Exception as e:
        return [{"error": f"Maigret error: {str(e)}"}]
    
    return results if results else [{"warning": "No accounts found by Maigret."}]

def check_all_tools() -> Dict[str, bool]:
    """Check if all OSINT tools are installed and accessible."""
    tools = {
        "sherlock": os.path.exists(get_venv_script_path("sherlock")),
        "holehe": os.path.exists(get_venv_script_path("holehe")),
        "maigret": os.path.exists(get_venv_script_path("maigret"))
    }
    return tools

if __name__ == "__main__":
    # Test tool availability
    print("Checking OSINT tools...")
    status = check_all_tools()
    for tool, available in status.items():
        icon = "✅" if available else "❌"
        print(f"{icon} {tool}: {'Available' if available else 'NOT FOUND'}")
