# OSINT Privacy Intelligence - Setup Guide

## Overview
This is a complete, locally-hosted OSINT Privacy Intelligence App that helps you monitor your personal digital footprint, check for data breaches, and discover social media accounts associated with your identity.

**⚠️ IMPORTANT: This tool is for PERSONAL USE ONLY. Only scan your own data.**

## Architecture

```
┌─────────────────────────────────────┐
│      Frontend (Streamlit)           │
│      Runs on localhost:8501         │
└────────────────┬────────────────────┘
                 │ REST API calls
┌────────────────▼────────────────────┐
│      Backend (FastAPI / Python)     │
│      Runs on localhost:8000         │
│  - Orchestrates all OSINT tools     │
│  - SQLite database                  │
│  - Neo4j graph integration          │
└────┬────┬────┬────┬────┬────────────┘
     │    │    │    │    │
   HIBP  Sherlock Holehe Maigret Neo4j
```

## Prerequisites

### System Requirements
- Python 3.9+
- Redis (for background tasks)
- Neo4j Desktop (optional, for graph visualization)

### External Tools (Optional but Recommended)
1. **Sherlock** - Social media username search
   ```bash
   git clone https://github.com/sherlock-project/sherlock.git
   cd sherlock && pip install -r requirements.txt
   ```

2. **Holehe** - Email registration checker
   ```bash
   pip install holehe
   ```

3. **Maigret** - Comprehensive username search
   ```bash
   pip install maigret
   ```

4. **ExifTool** - Metadata extraction
   - Linux: `apt install libimage-exiftool-perl`
   - macOS: `brew install exiftool`

## Installation

### Step 1: Install Python Dependencies
```bash
cd /workspace
pip install -r requirements.txt
```

### Step 2: Start Redis (Required for Celery)
```bash
redis-server
```

### Step 3: Start Neo4j (Optional)
Download and install Neo4j Desktop from [neo4j.com/download](https://neo4j.com/download/)
- Create a new DBMS instance
- Set password to "password" (or update in config.py)
- Start the instance

### Step 4: Configure Environment (Optional)
Create a `.env` file for sensitive configuration:
```bash
# .env
HIBP_API_KEY=your_hibp_api_key_here  # Get from haveibeenpwned.com/API/Key
NEO4J_PASSWORD=your_neo4j_password
SECRET_KEY=your-secret-key-here
```

To get a HIBP API key (required for breach lookup):
1. Visit [haveibeenpwned.com/API/Key](https://haveibeenpwned.com/API/Key)
2. Purchase an API key ($3.50/month)
3. Add it to your `.env` file

**Note:** Password exposure checking works WITHOUT an API key using the free HIBP Pwned Passwords API.

## Running the Application

### Option 1: Run Separately (Recommended for Development)

Terminal 1 - Start Backend:
```bash
cd /workspace
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 - Start Frontend:
```bash
cd /workspace
streamlit run dashboard.py
```

Access the application:
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Quick Test
```bash
# Test backend health
curl http://127.0.0.1:8000/api/health

# Test password check (no API key needed)
curl -X POST http://127.0.0.1:8000/api/password/check \
  -H "Content-Type: application/json" \
  -d '{"password": "test123"}'
```

## Features

### 🔐 Breach Analysis
- Check if your email appears in known data breaches
- Requires HIBP paid API key for full functionality
- Free password exposure checking (k-anonymity model)

### 🌐 Social Footprint Discovery
- Find social media accounts by username (Sherlock)
- Check email registrations across sites (Holehe)
- Comprehensive username search (Maigret)

### 📊 Privacy Dashboard
- Visual exposure score (0-100)
- Interactive charts and metrics
- Historical tracking

### 🕸️ Relationship Graph (Neo4j)
- Visualize connections between emails, usernames, and breaches
- Query relationships with Cypher
- Export graph data

### 🔔 Continuous Monitoring (Future)
- Scheduled re-scans with APScheduler
- Email/desktop alerts for new breaches
- Change detection

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scan` | POST | Perform comprehensive OSINT scan |
| `/api/password/check` | POST | Check password exposure (free) |
| `/api/breaches/{email}` | GET | Get breach records from database |
| `/api/social-accounts/{username}` | GET | Get discovered social accounts |
| `/api/exposure-score/{email}` | GET | Get privacy exposure score |
| `/api/health` | GET | Health check |

## Database Schema

The app uses SQLite with the following tables:
- `scan_targets` - People/entities being monitored
- `breach_records` - Data breach information
- `social_accounts` - Discovered social media accounts
- `exposure_scores` - Privacy score history
- `monitoring_jobs` - Scheduled monitoring tasks
- `alerts` - Security alerts

## Security Considerations

1. **Local Only**: Everything runs on localhost - nothing exposed externally
2. **Password Safety**: Password checks use k-anonymity (only first 5 chars of hash sent)
3. **Data Storage**: All data stored locally in SQLite
4. **Personal Use**: Only scan your own data - legal compliance is your responsibility

## Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill the process if needed
kill -9 <PID>
```

### Redis connection error
```bash
# Start Redis
redis-server

# Or check if running
redis-cli ping  # Should return PONG
```

### Neo4j connection error
```bash
# Verify Neo4j is running
# Check bolt://localhost:7687 is accessible
# Update credentials in config.py or .env
```

### Sherlock/Holehe/Maigret not found
```bash
# Install missing tools
git clone https://github.com/sherlock-project/sherlock.git
pip install holehe maigret
```

## Project Structure

```
/workspace
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.py             # Configuration settings
├── database.py           # SQLite models and setup
├── main.py               # FastAPI backend
├── dashboard.py          # Streamlit frontend
├── privacy_intelligence.db  # SQLite database (created on first run)
└── tools/
    ├── __init__.py
    ├── breacher.py       # HIBP integration
    ├── footprint.py      # Sherlock/Holehe/Maigret
    └── graph.py          # Neo4j operations
```

## Next Steps

### Phase 1 (Complete ✅)
- Core backend with FastAPI
- Streamlit dashboard
- HIBP password checking (free)
- SQLite database

### Phase 2 (Install tools)
- Install Sherlock, Holehe, Maigret
- Enable social footprint discovery

### Phase 3 (Optional)
- Set up Neo4j for graph visualization
- Configure HIBP paid API for breach lookup

### Phase 4 (Future Enhancements)
- Background monitoring with Celery
- Email alerts
- Data broker opt-out tracking
- Document metadata analysis

## Legal Disclaimer

This tool is provided for **educational and personal privacy assessment purposes only**. 

- Only use this tool on yourself or with explicit permission
- Respect terms of service of all platforms
- Comply with applicable laws and regulations
- The authors are not responsible for misuse

## Resources

- [Have I Been Pwned](https://haveibeenpwned.com)
- [Sherlock Project](https://github.com/sherlock-project/sherlock)
- [Holehe](https://github.com/megadose/holehe)
- [Maigret](https://github.com/soxoj/maigret)
- [Neo4j](https://neo4j.com)
- [FastAPI](https://fastapi.tiangolo.com)
- [Streamlit](https://streamlit.io)

---

**Built with ❤️ for personal privacy awareness**
