"""
Social footprint discovery using Sherlock, Holehe, and Maigret.
Discovers social media accounts associated with usernames and emails.
"""
import subprocess
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path


class SocialFootprintScanner:
    """Scan for social media accounts using multiple OSINT tools"""
    
    def __init__(self):
        self.sherlock_path = self._find_sherlock()
        self.results = []
    
    def _find_sherlock(self) -> Optional[str]:
        """Find Sherlock installation - works on both Linux and Windows"""
        import sys
        import os
        
        # Try to find sherlock executable in PATH or venv Scripts directory
        if sys.platform == "win32":
            # On Windows, check venv Scripts directory first
            scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
            sherlock_exe = os.path.join(scripts_dir, "sherlock.exe")
            if os.path.exists(sherlock_exe):
                return sherlock_exe
            
            # Also try without .exe extension
            sherlock_exe_no_ext = os.path.join(scripts_dir, "sherlock")
            if os.path.exists(sherlock_exe_no_ext):
                return sherlock_exe_no_ext
        
        # Try system-wide installation (Linux/Mac/Windows)
        try:
            result = subprocess.run(
                ["which", "sherlock"] if sys.platform != "win32" else ["where", "sherlock"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        
        # Fallback to possible paths
        possible_paths = [
            Path("./sherlock/sherlock.py"),
            Path("../sherlock/sherlock.py"),
            Path("/opt/sherlock/sherlock.py"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def scan_username_sherlock(self, username: str, timeout: int = 60) -> List[Dict[str, Any]]:
        """
        Use Sherlock to find social media accounts by username.
        
        Returns list of found accounts with platform, URL, and status.
        """
        results = []
        
        if not self.sherlock_path:
            raise RuntimeError(
                "Sherlock not found. Install it with: pip install sherlock-project"
            )
        
        try:
            # Build command - use sherlock executable directly (works on Windows and Linux)
            import sys
            if sys.platform == "win32":
                cmd = [
                    self.sherlock_path,
                    username,
                    "--json",
                    "--timeout",
                    str(timeout),
                    "--no-color"
                ]
            else:
                # On Linux/Mac, run with python if it's a .py file
                if self.sherlock_path.endswith('.py'):
                    cmd = [
                        "python3",
                        self.sherlock_path,
                        username,
                        "--json",
                        "--timeout",
                        str(timeout),
                        "--no-color"
                    ]
                else:
                    cmd = [
                        self.sherlock_path,
                        username,
                        "--json",
                        "--timeout",
                        str(timeout),
                        "--no-color"
                    ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10
            )
            
            if result.returncode == 0 or result.stdout:
                try:
                    # Parse JSON output
                    data = json.loads(result.stdout)
                    
                    for platform, info in data.items():
                        if isinstance(info, dict) and info.get("status", {}).get("http_status") == 200:
                            results.append({
                                "username": username,
                                "platform": platform,
                                "url": info.get("url", ""),
                                "exists": True,
                                "http_status": info.get("status", {}).get("http_status"),
                                "source_tool": "Sherlock"
                            })
                except json.JSONDecodeError:
                    # Fallback: parse text output
                    results = self._parse_sherlock_text(result.stdout, username)
            
            return results
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Sherlock scan timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Sherlock error: {str(e)}")
    
    def _parse_sherlock_text(self, text: str, username: str) -> List[Dict[str, Any]]:
        """Parse Sherlock text output as fallback"""
        results = []
        
        # Simple pattern matching for found accounts
        patterns = [
            r'\[(\+)\] (\w+).*?https?://[^\s]+',
            r'(\w+):\s+https?://[^\s]+'
        ]
        
        for line in text.split('\n'):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    platform = match.group(1) if len(match.groups()) > 0 else "Unknown"
                    url_match = re.search(r'https?://[^\s]+', line)
                    url = url_match.group(0) if url_match else ""
                    
                    results.append({
                        "username": username,
                        "platform": platform,
                        "url": url,
                        "exists": True,
                        "http_status": 200,
                        "source_tool": "Sherlock"
                    })
                    break
        
        return results
    
    def scan_email_holehe(self, email: str, timeout: int = 120) -> List[Dict[str, Any]]:
        """
        Use Holehe to check which sites have the email registered.
        
        Returns list of sites where email is registered.
        """
        results = []
        
        try:
            cmd = [
                "holehe",
                email,
                "--json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    
                    for site_info in data:
                        if site_info.get("registered", False):
                            results.append({
                                "email": email,
                                "platform": site_info.get("name", "Unknown"),
                                "url": site_info.get("url", ""),
                                "exists": True,
                                "http_status": 200,
                                "source_tool": "Holehe"
                            })
                except json.JSONDecodeError:
                    pass
            
            return results
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Holehe scan timed out after {timeout} seconds")
        except FileNotFoundError:
            raise RuntimeError(
                "Holehe not found. Install it with: pip install holehe"
            )
        except Exception as e:
            raise RuntimeError(f"Holehe error: {str(e)}")
    
    def scan_email_maigret(self, username: str, timeout: int = 120) -> List[Dict[str, Any]]:
        """
        Use Maigret to find accounts by username across many sites.
        More comprehensive than Sherlock but slower.
        
        Returns list of found accounts.
        """
        results = []
        
        try:
            cmd = [
                "maigret",
                username,
                "--json",
                "--no-color",
                "--timeout",
                str(timeout),
                "--max-connections",
                "20"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 30
            )
            
            # Maigret creates a JSON file, try to read it
            json_file = Path(f"{username}.json")
            if json_file.exists():
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    if "urls" in data:
                        for url_info in data["urls"]:
                            results.append({
                                "username": username,
                                "platform": url_info.get("sitename", "Unknown"),
                                "url": url_info.get("url", ""),
                                "exists": url_info.get("status", {}).get("id") == "Valid",
                                "http_status": url_info.get("status", {}).get("http_status"),
                                "source_tool": "Maigret"
                            })
                    
                    # Clean up
                    json_file.unlink()
                    
                except (json.JSONDecodeError, IOError):
                    pass
            
            return results
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Maigret scan timed out after {timeout} seconds")
        except FileNotFoundError:
            raise RuntimeError(
                "Maigret not found. Install it with: pip install maigret"
            )
        except Exception as e:
            raise RuntimeError(f"Maigret error: {str(e)}")
    
    def scan_comprehensive(self, username: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all available scanners and aggregate results.
        
        Returns comprehensive report with all findings.
        """
        report = {
            "username": username,
            "email": email,
            "accounts": [],
            "summary": {
                "total_found": 0,
                "by_platform": {},
                "by_tool": {}
            }
        }
        
        # Scan with Sherlock
        try:
            sherlock_results = self.scan_username_sherlock(username)
            report["accounts"].extend(sherlock_results)
            report["summary"]["by_tool"]["Sherlock"] = len(sherlock_results)
        except Exception as e:
            report["errors"] = report.get("errors", [])
            report["errors"].append(f"Sherlock: {str(e)}")
        
        # Scan with Holehe if email provided
        if email:
            try:
                holehe_results = self.scan_email_holehe(email)
                report["accounts"].extend(holehe_results)
                report["summary"]["by_tool"]["Holehe"] = len(holehe_results)
            except Exception as e:
                report["errors"] = report.get("errors", [])
                report["errors"].append(f"Holehe: {str(e)}")
        
        # Scan with Maigret
        try:
            maigret_results = self.scan_email_maigret(username)
            report["accounts"].extend(maigret_results)
            report["summary"]["by_tool"]["Maigret"] = len(maigret_results)
        except Exception as e:
            report["errors"] = report.get("errors", [])
            report["errors"].append(f"Maigret: {str(e)}")
        
        # Calculate summary
        report["summary"]["total_found"] = len(report["accounts"])
        
        for account in report["accounts"]:
            platform = account.get("platform", "Unknown")
            report["summary"]["by_platform"][platform] = \
                report["summary"]["by_platform"].get(platform, 0) + 1
        
        return report


# Convenience functions
def scan_social_footprint(username: str, email: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to scan social footprint"""
    scanner = SocialFootprintScanner()
    return scanner.scan_comprehensive(username, email)
