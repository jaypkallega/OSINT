# OSINT Privacy Intelligence App - Installation Guide

## Complete Implementation Status

✅ **Phase 1 - Core + Breach**: COMPLETE
- FastAPI backend with SQLite
- HIBP Pwned Passwords (FREE, no API key)
- Streamlit dashboard
- Exposure score algorithm

✅ **Phase 2 - Social Footprint**: COMPLETE  
- Sherlock integration (username search)
- Holehe integration (email registration check)
- Maigret integration (comprehensive username scan)
- Subprocess orchestration with timeout handling

✅ **Phase 3 - Graph Database**: COMPLETE
- Neo4j integration with py2neo
- Entity relationship mapping (emails, usernames, platforms, breaches)
- Graph population from scan results
- Visualization data export

✅ **Phase 4 - Document & Domain**: COMPLETE
- theHarvester integration (domain/email/subdomain discovery)
- Metagoofil integration (public document metadata)
- ExifTool integration (document/image metadata extraction)

⏳ **Phase 5 - Monitoring**: Ready for implementation
- APScheduler framework in place
- Alert system ready

⏳ **Phase 6 - Dashboard Polish**: Ready for implementation
- Exposure score algorithm implemented
- Opt-out tracker ready

---

## Installation Steps

### Step 1: Python Environment Setup

```powershell
# On Windows (PowerShell)
cd C:\Users\jayap\OSINT2

# Create virtual environment with Python 3.12
py -3.12 -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### Step 2: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Install OSINT Tools (Optional but Recommended)

#### Install Sherlock (Username Search)
```powershell
git clone https://github.com/sherlock-project/sherlock.git
cd sherlock
pip install -r requirements.txt
cd ..
```

#### Install Holehe (Email Registration Check)
```powershell
pip install holehe
```

#### Install Maigret (Comprehensive Username Search)
```powershell
pip install maigret
```

#### Install theHarvester (Domain/Email Discovery)
```powershell
git clone https://github.com/laramies/theHarvester.git
cd theHarvester
pip install -r requirements.txt
cd ..
```

#### Install Metagoofil (Document Metadata)
```powershell
git clone https://github.com/himanshubalakumbhar/metagoofil.git
cd metagoofil
pip install -r requirements.txt
cd ..
```

#### Install ExifTool (System Tool)
**Windows:** Download from https://exiftool.org/
1. Download `exiftool-12.XX.zip`
2. Extract and rename `exiftool(-k).exe` to `exiftool.exe`
3. Add to PATH or place in `C:\Windows\`

**Alternative with Chocolatey:**
```powershell
choco install exiftool
```

### Step 4: Setup Neo4j (Optional for Graph Features)

1. Download Neo4j Desktop from https://neo4j.com/download/
2. Install and create a new DBMS instance
3. Start the instance (default credentials: neo4j/password)
4. Default connection: `bolt://localhost:7687`

### Step 5: Run the Application

```powershell
# Make sure you're in the OSINT2 directory with venv activated
.\start.bat
```

Or manually:
```powershell
# Terminal 1 - Backend
.\venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 - Frontend  
.\venv\Scripts\activate
streamlit run dashboard.py --server.address=127.0.0.1 --server.port=8501
```

### Access Points
- **Frontend Dashboard**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## Tool Requirements Summary

| Tool | Required For | Install Method | Key Needed? |
|------|-------------|----------------|-------------|
| Sherlock | Username social media search | git clone + pip | No |
| Holehe | Email registration check | pip install | No |
| Maigret | Comprehensive username scan | pip install | No |
| theHarvester | Domain/email discovery | git clone + pip | No (basic) |
| Metagoofil | Document metadata | git clone + pip | No |
| ExifTool | File metadata extraction | System install | No |
| Neo4j Desktop | Graph visualization | Download installer | No |
| HIBP API | Detailed breach info | API key ($3.50/mo) | Yes (optional) |

---

## Testing Installation

Run these commands to verify tool installation:

```python
python -c "from tools.footprint import SocialFootprintScanner; s = SocialFootprintScanner(); print('Sherlock:', s.check_tool_installed('sherlock')); print('Holehe:', s.check_tool_installed('holehe')); print('Maigret:', s.check_tool_installed('maigret'))"

python -c "from tools.domain_doc import DomainDocumentScanner; s = DomainDocumentScanner(); print('theHarvester:', s.check_tool_installed('theharvester')); print('Metagoofil:', s.check_tool_installed('metagoofil')); print('ExifTool:', s.check_tool_installed('exiftool'))"

python -c "from tools.graph import Neo4jGraphManager; g = Neo4jGraphManager(); print('Neo4j Connected:', g.connect())"
```

---

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError: email_validator**
```powershell
pip install email-validator
```

**2. Neo4j Connection Failed**
- Ensure Neo4j Desktop is running
- Check credentials in config.py
- Verify port 7687 is not blocked

**3. Tool Not Found Errors**
- Ensure tools are installed in the same environment
- Check system PATH for external tools (ExifTool)
- Restart terminal after installation

**4. Port Already in Use**
```powershell
# Find and kill process on port 8000 or 8501
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## Next Steps

1. **Test Basic Functionality**: Enter an email and run password exposure check
2. **Install OSINT Tools**: Follow Step 3 for full functionality
3. **Setup Neo4j**: For graph visualization features
4. **Configure Monitoring**: Implement Phase 5 scheduled scans
5. **Customize**: Modify exposure score algorithm in main.py

For detailed usage, visit the dashboard at http://localhost:8501
