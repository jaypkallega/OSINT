"""
HIBP (Have I Been Pwned) integration for breach and password lookup.
Supports both free (password) and paid (breach) API endpoints.
"""
import requests
import hashlib
from typing import List, Dict, Optional, Any
from config import settings


class HIBPClient:
    """Client for Have I Been Pwned API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.HIBP_API_KEY
        self.breach_api_base = "https://haveibeenpwned.com/api/v3"
        self.password_api_base = "https://api.pwnedpasswords.com/range"
        self.user_agent = "OSINT-Privacy-App/1.0"
    
    def check_breached_account(self, email: str) -> List[Dict[str, Any]]:
        """
        Check if an email has been involved in data breaches.
        Requires paid API key.
        
        Returns list of breach objects or empty list if none found.
        """
        if not self.api_key:
            raise ValueError("HIBP API key required for breach lookup. Get one at haveibeenpwned.com/API/Key")
        
        url = f"{self.breach_api_base}/breachedaccount/{email}"
        params = {
            "truncateResponse": "false"
        }
        headers = {
            "hibp-api-key": self.api_key,
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return []  # No breaches found
            elif response.status_code == 401:
                raise ValueError("Invalid HIBP API key")
            elif response.status_code == 429:
                raise ValueError("Rate limit exceeded")
            else:
                response.raise_for_status()
                
        except requests.RequestException as e:
            raise Exception(f"HIBP API error: {str(e)}")
    
    def check_password(self, password: str) -> Dict[str, Any]:
        """
        Check if a password has been exposed in data breaches.
        Uses k-anonymity model - password never leaves your device.
        Free to use, no API key required.
        
        Returns dict with:
        - found: bool
        - count: int (number of times seen in breaches)
        - sha1_hash: str (full hash of the password)
        """
        # Hash the password locally using SHA1
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]
        
        # Query only the first 5 characters
        url = f"{self.password_api_base}/{prefix}"
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse the response
            hashes = {}
            for line in response.text.splitlines():
                hash_suffix, count = line.split(':')
                hashes[hash_suffix] = int(count)
            
            # Check if our suffix is in the results
            if suffix in hashes:
                return {
                    "found": True,
                    "count": hashes[suffix],
                    "sha1_hash": sha1_hash,
                    "message": f"Password found in {hashes[suffix]} breaches!"
                }
            else:
                return {
                    "found": False,
                    "count": 0,
                    "sha1_hash": sha1_hash,
                    "message": "Password not found in any known breaches."
                }
                
        except requests.RequestException as e:
            raise Exception(f"HIBP Password API error: {str(e)}")
    
    def get_breach_details(self, breach_name: str) -> Dict[str, Any]:
        """
        Get details about a specific breach.
        Requires paid API key.
        """
        if not self.api_key:
            raise ValueError("HIBP API key required")
        
        url = f"{self.breach_api_base}/breach/{breach_name}"
        headers = {
            "hibp-api-key": self.api_key,
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise ValueError(f"Breach '{breach_name}' not found")
            else:
                response.raise_for_status()
                
        except requests.RequestException as e:
            raise Exception(f"HIBP API error: {str(e)}")
    
    def get_all_breaches(self) -> List[Dict[str, Any]]:
        """
        Get all breaches in the HIBP database.
        Requires paid API key.
        """
        if not self.api_key:
            raise ValueError("HIBP API key required")
        
        url = f"{self.breach_api_base}/breaches"
        headers = {
            "hibp-api-key": self.api_key,
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise Exception(f"HIBP API error: {str(e)}")


# Convenience functions
def check_email_breaches(email: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Check email for breaches"""
    client = HIBPClient(api_key)
    return client.check_breached_account(email)


def check_password_exposure(password: str) -> Dict[str, Any]:
    """Check password exposure (free, no API key needed)"""
    client = HIBPClient()
    return client.check_password(password)
