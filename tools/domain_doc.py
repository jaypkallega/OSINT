"""
Phase 4: Document and Domain Analysis Tools
Integrates theHarvester, Metagoofil, and ExifTool for domain and document metadata extraction
"""
import subprocess
import json
import os
import tempfile
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime


class DomainDocumentScanner:
    """Scanner for domain information and document metadata"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "osint_scans"
        self.temp_dir.mkdir(exist_ok=True)
    
    def check_tool_installed(self, tool_name: str) -> bool:
        """Check if a tool is installed"""
        try:
            if tool_name == "theharvester":
                result = subprocess.run(
                    ["theHarvester", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode == 0
            elif tool_name == "metagoofil":
                result = subprocess.run(
                    ["metagoofil", "-h"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode == 0 or "usage" in result.stderr.lower()
            elif tool_name == "exiftool":
                result = subprocess.run(
                    ["exiftool", "-ver"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False
        return False
    
    def run_theharvester(self, domain: str, sources: List[str] = None, 
                         limit: int = 500) -> Dict:
        """
        Run theHarvester to gather emails, subdomains, and hosts for a domain
        """
        result = {
            "tool": "theHarvester",
            "domain": domain,
            "status": "success",
            "emails": [],
            "subdomains": [],
            "hosts": [],
            "error": None
        }
        
        if not self.check_tool_installed("theharvester"):
            result["status"] = "not_installed"
            result["error"] = "theHarvester not installed. Clone from GitHub"
            return result
        
        if sources is None:
            sources = ["bing", "duckduckgo", "google"]  # Free sources
        
        try:
            all_emails = set()
            all_subdomains = set()
            all_hosts = set()
            
            for source in sources:
                temp_file = self.temp_dir / f"harvest_{domain}_{source}.json"
                
                cmd = [
                    "theHarvester",
                    "-d", domain,
                    "-b", source,
                    "-l", str(limit),
                    "-f", str(temp_file)
                ]
                
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes per source
                )
                
                # Parse output file if exists
                if temp_file.exists():
                    try:
                        with open(temp_file, 'r') as f:
                            data = json.load(f)
                            
                            # Extract emails
                            if "emails" in data:
                                all_emails.update(data["emails"])
                            
                            # Extract subdomains
                            if "vhost" in data:
                                all_subdomains.update(data["vhost"])
                            
                            # Extract hosts
                            if "ip" in data:
                                all_hosts.update(data["ip"])
                        
                        temp_file.unlink()
                    except (json.JSONDecodeError, IOError):
                        pass
                
                # Also parse stdout for immediate results
                if "Emails found" in process.stdout:
                    # Simple parsing of text output
                    in_emails = False
                    for line in process.stdout.split('\n'):
                        if '@' in line and '.' in line:
                            all_emails.add(line.strip())
                        if line.startswith('[+] '):
                            parts = line[4:].split()
                            for part in parts:
                                if domain in part and part.count('.') >= 2:
                                    all_subdomains.add(part)
            
            result["emails"] = list(all_emails)
            result["subdomains"] = list(all_subdomains)
            result["hosts"] = list(all_hosts)
            result["summary"] = {
                "total_emails": len(all_emails),
                "total_subdomains": len(all_subdomains),
                "total_hosts": len(all_hosts)
            }
            
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = "theHarvester timed out"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def run_metagoofil(self, domain: str, file_types: List[str] = None,
                       limit: int = 50) -> Dict:
        """
        Run Metagoofil to find public documents and extract metadata
        """
        result = {
            "tool": "Metagoofil",
            "domain": domain,
            "status": "success",
            "documents": [],
            "metadata": {
                "users": set(),
                "software": set(),
                "emails": set(),
                "paths": set()
            },
            "error": None
        }
        
        if not self.check_tool_installed("metagoofil"):
            result["status"] = "not_installed"
            result["error"] = "Metagoofil not installed. Clone from GitHub"
            return result
        
        if file_types is None:
            file_types = ["pdf", "docx", "xlsx", "pptx"]
        
        try:
            work_dir = self.temp_dir / f"metagoofil_{domain}"
            work_dir.mkdir(exist_ok=True)
            
            all_docs = []
            
            for filetype in file_types:
                cmd = [
                    "metagoofil",
                    "-d", domain,
                    "-t", filetype,
                    "-l", str(limit),
                    "-o", str(work_dir),
                    "-w"  # Don't download files, just metadata
                ]
                
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                
                # Parse output for document info
                for line in process.stdout.split('\n'):
                    if '[+]' in line and '://' in line:
                        url = line.split('http')[1].strip()
                        all_docs.append({
                            "url": f"http{url}",
                            "type": filetype,
                            "domain": domain
                        })
                    
                    # Extract metadata from output
                    if 'User:' in line:
                        user = line.split('User:')[1].strip()
                        if user and user != '-':
                            result["metadata"]["users"].add(user)
                    
                    if 'Software:' in line:
                        software = line.split('Software:')[1].strip()
                        if software and software != '-':
                            result["metadata"]["software"].add(software)
                    
                    if '@' in line and '.' in line:
                        email = line.strip()
                        if email not in result["metadata"]["emails"]:
                            result["metadata"]["emails"].add(email)
            
            result["documents"] = all_docs
            result["metadata"]["users"] = list(result["metadata"]["users"])
            result["metadata"]["software"] = list(result["metadata"]["software"])
            result["metadata"]["emails"] = list(result["metadata"]["emails"])
            result["metadata"]["paths"] = list(result["metadata"]["paths"])
            
            result["summary"] = {
                "total_documents": len(all_docs),
                "total_users": len(result["metadata"]["users"]),
                "total_software": len(result["metadata"]["software"]),
                "total_emails_found": len(result["metadata"]["emails"])
            }
            
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = "Metagoofil timed out"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def extract_exif_metadata(self, file_path: str) -> Dict:
        """
        Extract EXIF/metadata from a document or image using ExifTool
        """
        result = {
            "tool": "ExifTool",
            "file": file_path,
            "status": "success",
            "metadata": {},
            "error": None
        }
        
        if not self.check_tool_installed("exiftool"):
            result["status"] = "not_installed"
            result["error"] = "ExifTool not installed. Install from exiftool.org"
            return result
        
        if not os.path.exists(file_path):
            result["status"] = "error"
            result["error"] = f"File not found: {file_path}"
            return result
        
        try:
            cmd = [
                "exiftool",
                "-json",
                file_path
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if process.stdout.strip():
                data = json.loads(process.stdout)
                if data:
                    result["metadata"] = data[0]
                    
                    # Extract key fields
                    result["extracted"] = {
                        "author": result["metadata"].get("Author", 
                                   result["metadata"].get("Creator", "")),
                        "created_date": result["metadata"].get("CreateDate", 
                                        result["metadata"].get("DateTimeOriginal", "")),
                        "modified_date": result["metadata"].get("ModifyDate", ""),
                        "software": result["metadata"].get("Software", 
                                     result["metadata"].get("Producer", "")),
                        "title": result["metadata"].get("Title", ""),
                        "subject": result["metadata"].get("Subject", ""),
                        "keywords": result["metadata"].get("Keywords", ""),
                        "company": result["metadata"].get("Company", ""),
                        "last_modified_by": result["metadata"].get("LastModifiedBy", "")
                    }
            
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = "ExifTool timed out"
        except json.JSONDecodeError:
            result["status"] = "parse_error"
            result["error"] = "Failed to parse ExifTool output"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def full_domain_scan(self, domain: str) -> Dict:
        """
        Run complete domain and document analysis
        """
        results = {
            "domain": domain,
            "scan_date": datetime.now().isoformat(),
            "theharvester": None,
            "metagoofil": None,
            "summary": {
                "total_emails": 0,
                "total_subdomains": 0,
                "total_documents": 0,
                "total_findings": 0
            }
        }
        
        # Run theHarvester
        results["theharvester"] = self.run_theharvester(domain)
        if results["theharvester"]["status"] == "success":
            results["summary"]["total_emails"] += results["theharvester"].get("summary", {}).get("total_emails", 0)
            results["summary"]["total_subdomains"] += results["theharvester"].get("summary", {}).get("total_subdomains", 0)
        
        # Run Metagoofil
        results["metagoofil"] = self.run_metagoofil(domain)
        if results["metagoofil"]["status"] == "success":
            results["summary"]["total_documents"] += results["metagoofil"].get("summary", {}).get("total_documents", 0)
            # Add emails from documents
            results["summary"]["total_emails"] += results["metagoofil"].get("metadata", {}).get("total_emails_found", 0)
        
        results["summary"]["total_findings"] = (
            results["summary"]["total_emails"] +
            results["summary"]["total_subdomains"] +
            results["summary"]["total_documents"]
        )
        
        return results


# Convenience function
def scan_domain(domain: str) -> Dict:
    """Scan domain for emails, subdomains, and documents"""
    scanner = DomainDocumentScanner()
    return scanner.full_domain_scan(domain)


if __name__ == "__main__":
    print("Testing Domain/Document Scanner...")
    scanner = DomainDocumentScanner()
    
    print("\nChecking tool installation:")
    print(f"theHarvester: {scanner.check_tool_installed('theharvester')}")
    print(f"Metagoofil: {scanner.check_tool_installed('metagoofil')}")
    print(f"ExifTool: {scanner.check_tool_installed('exiftool')}")
