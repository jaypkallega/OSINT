# OSINT Privacy Intelligence Platform (OPIP)
## Complete Technical Design & Architecture Document
**Version:** 2.0.0  
**Date:** October 2023  
**Classification:** Private / Local-Only Deployment  

---

## 1. Executive Summary

The OSINT Privacy Intelligence Platform (OPIP) is a locally-hosted, single-user aggregation engine designed to audit personal digital footprints. It orchestrates over 30 open-source intelligence (OSINT) tools via a unified FastAPI backend and Streamlit frontend. The system performs breach detection, social account discovery, metadata extraction, and relationship graph mapping without exposing user data to external clouds. All processing, storage, and visualization occur strictly on the user's local machine (`localhost`).

**Core Value Proposition:**
- **Unified Orchestration:** Replaces manual CLI tool usage with a single API-driven workflow.
- **Privacy-First:** Zero data leaves the local environment except for necessary API queries (HIBP, Sherlock targets) which are ephemeral.
- **Persistent Intelligence:** Transition from ephemeral scans to a persistent knowledge graph (SQLite + Neo4j) for historical tracking and relationship mapping.

---

## 2. System Architecture

### 2.1 High-Level Topology

The system follows a **Local-First Microservices** pattern, containerized logically within a single Python Virtual Environment.

```
┌──────────────────────────────────────────────────────────┐
│                  LAPTOP (localhost only)                  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │           Streamlit Frontend :8501               │    │
│  │  Dashboard | Breach | Graph | Monitor | Broker   │    │
│  └────────────────────┬────────────────────────────┘    │
│                       │ HTTP REST                        │
│  ┌────────────────────▼────────────────────────────┐    │
│  │           FastAPI Backend :8000                  │    │
│  │  ┌──────────────┐  ┌──────────────────────────┐ │    │
│  │  │  API Routes  │  │  Orchestrator Engine     │ │    │
│  │  └──────┬───────┘  └────────────┬─────────────┘ │    │
│  │         │                       │               │    │
│  │  ┌──────▼───────────────────────▼─────────────┐ │    │
│  │  │          Module Layer (30+ tools)          │ │    │
│  │  │  breach | social | domain | phone | graph  │ │    │
│  │  │  metadata | ip | secrets | threat | broker │ │    │
│  │  └────────────────────────────────────────────┘ │    │
│  │                                                  │    │
│  │  ┌──────────────┐  ┌──────────────────────────┐ │    │
│  │  │   Celery     │  │     APScheduler          │ │    │
│  │  │   + Redis    │  │  (24hr monitoring jobs)  │ │    │
│  │  └──────────────┘  └──────────────────────────┘ │    │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  SQLite    │  │  Neo4j :7687 │  │  Redis :6379    │  │
│  │  (osint.db)│  │  (Graph DB)  │  │  (Task Queue)   │  │
│  └────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Component Inventory

| Component | Technology | Port | Role | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | Streamlit | 8501 | Interactive Dashboard, Graph Viz, Forms | ✅ Active |
| **Backend API** | FastAPI + Uvicorn | 8000 | Request Routing, Tool Orchestration, Validation | ✅ Active |
| **Relational DB** | SQLite (`osint.db`) | N/A | User profiles, scan logs, breach records, broker status | ✅ Active |
| **Graph DB** | Neo4j Community | 7687 (Bolt) | Entity resolution, relationship mapping, pathfinding | 🟡 Integrated |
| **Scanner: Username** | Sherlock | CLI | Social media discovery by username | ✅ Fixed |
| **Scanner: Email** | Holehe | CLI | Site registration check by email | ✅ Active |
| **Scanner: Deep** | Maigret | CLI | Comprehensive profile analysis | ✅ Active |
| **Breach Data** | HIBP API | HTTPS | Breach database lookup (Requires API Key) | ✅ Active |
| **Password Check** | PwnedPasswords | HTTPS | K-Anonymity password exposure check | ✅ Active |
| **Task Queue** | Celery + Redis | 6379 | Async background scanning (Planned) | ⏳ Pending |

---

## 3. Data Model & Persistence

### 3.1 Relational Schema (SQLite)

The system uses a normalized SQLite schema to store historical scan data, allowing for trend analysis and exposure scoring over time.

**Tables:**

1.  **`users`**: Stores target profiles.
    *   `id` (INTEGER PK), `name`, `primary_email`, `created_at`.
2.  **`scans`**: Log of every execution.
    *   `id` (INTEGER PK), `user_id` (FK), `target_query` (email/username), `scan_type`, `timestamp`, `status`.
3.  **`breaches`**: Results from HIBP.
    *   `id`, `scan_id` (FK), `breach_name`, `breach_date`, `data_classes` (JSON), `pwn_count`.
4.  **`social_accounts`**: Results from Sherlock/Holehe/Maigret.
    *   `id`, `scan_id` (FK), `platform`, `username`, `url`, `source_tool`, `status` (found/not_found).
5.  **`broker_optouts`**: Tracking for data broker removal.
    *   `id`, `user_id` (FK), `broker_name`, `status` (pending/submitted/confirmed), `optout_url`.

### 3.2 Graph Schema (Neo4j)

The Graph DB models the **Entity-Relationship** structure of the digital footprint.

**Node Labels:**
*   `(:Person {email, name})`
*   `(:Username {value})`
*   `(:Breach {name, date})`
*   `(:Platform {name})`
*   `(:Phone {number})`

**Relationship Types:**
*   `(:Person)-[:OWNS]->(:Username)`
*   `(:Person)-[:EMAIL_ADDRESS]->(:Email)`
*   `(:Username)-[:REGISTERED_ON]->(:Platform)`
*   `(:Person)-[:FOUND_IN]->(:Breach)`
*   `(:Person)-[:ASSOCIATED_WITH]->(:Phone)`

**Population Logic:**
Upon successful scan completion, the backend executes Cypher queries to upsert nodes and create relationships, ensuring the graph remains current with the latest scan data.

---

## 4. Module Specifications

### 4.1 Tool Orchestration Layer (`osint_tools.py`)

This module handles the execution of external CLI tools, managing paths, arguments, and output parsing.

**Key Features:**
*   **Virtual Environment Awareness:** Dynamically resolves executable paths (`sherlock.exe`, `holehe.exe`) within the active venv `Scripts/` directory.
*   **Dual-Mode Sherlock Execution:**
    *   *Primary:* Attempts `--print-found` for stdout parsing.
    *   *Fallback:* Uses `--json <tempfile>` if stdout parsing fails or arguments differ.
*   **Timeout Management:** Enforces strict timeouts (30s-90s) to prevent UI hanging.
*   **Error Normalization:** Converts diverse CLI errors into standardized JSON responses (`{error: "...", source: "..."}`).

**Execution Flow:**
1.  Validate input (email/username).
2.  Construct command list with absolute paths.
3.  Spawn subprocess with `CREATE_NO_WINDOW` (Windows) to hide console popups.
4.  Capture `stdout`/`stderr`.
5.  Parse output (Regex for text, `json.loads` for structured data).
6.  Return normalized list of findings.

### 4.2 Security & Breach Module

*   **HIBP Integration:** Uses `httpx` async client to query `haveibeenpwned.com/api/v3/breachedaccount/{email}`. Requires `HIBP_API_KEY` in environment.
*   **Password K-Anonymity:**
    1.  Hash password (SHA1).
    2.  Split hash: `Prefix` (5 chars) + `Suffix`.
    3.  Query `api.pwnedpasswords.com/range/{Prefix}`.
    4.  **Local Match:** Compare Suffix locally. Full hash never leaves the machine.

### 4.3 Guarded Features

To prevent misuse, specific modules require explicit user confirmation flags stored in the session or DB.

*   **Phone Scanning (F-030):** Before executing `PhoneInfoga`, the UI prompts: *"Confirm this is your own number."* Execution is blocked until confirmed.
*   **Broker Opt-Out (F-041):** Provides direct links to opt-out pages but requires manual user completion. Status is tracked in `broker_optouts` table.

---

## 5. API Interface Specification

The backend exposes a RESTful API consumed by the Streamlit frontend.

### 5.1 Endpoints

| Method | Endpoint | Description | Payload | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System health check | None | `{status: "healthy", version: "2.0.0"}` |
| `POST` | `/api/scan` | **Main Orchestrator** | `{email, username, check_breaches, check_social}` | `{breaches: [], social_accounts: [], score: int}` |
| `POST` | `/api/password/check` | Password exposure | `{password: "secret"}` | `{found: bool, count: int}` |
| `GET` | `/api/exposure-score/{email}` | Quick score lookup | None | `{score: int, history: []}` |
| `POST` | `/api/graph/rebuild` | Force Neo4j sync | `{user_id}` | `{nodes_created: int, rels_created: int}` |

### 5.2 Data Flow: Scan Request

1.  **Request:** User submits `email` via Streamlit.
2.  **Validation:** FastAPI validates email format.
3.  **Parallel Execution:**
    *   Thread A: Calls `run_holehe(email)`.
    *   Thread B: Extracts username, calls `run_sherlock(username)`.
    *   Thread C: Calls `check_hibp(email)` (Async).
4.  **Aggregation:** Results merged into a unified dictionary.
5.  **Persistence:**
    *   Insert record into `scans` table (SQLite).
    *   Insert findings into `breaches`/`social_accounts` tables.
    *   Upsert nodes/relationships in Neo4j.
6.  **Scoring:** Calculate `exposure_score` based on weighted factors.
7.  **Response:** JSON returned to Frontend for rendering.

---

## 6. Implementation Details & Fixes

### 6.1 Critical Resolutions (v2.0.0)

1.  **Sherlock Argument Error:**
    *   *Issue:* `--json` flag required a filename argument in newer versions, causing `ArgumentParser` errors.
    *   *Fix:* Implemented `run_sherlock()` with `--print-found` flag for stdout streaming. Added fallback logic to use temporary files if structured JSON is strictly required.
2.  **Streamlit Key Collisions:**
    *   *Issue:* `StreamlitDuplicateElementKey` when re-rendering graphs.
    *   *Fix:* Dynamic key generation using `f"view_graph_btn_{email}_{id(result)}"`.
3.  **Path Resolution:**
    *   *Issue:* Tools not found in Windows PATH.
    *   *Fix:* `get_venv_script_path()` helper resolves absolute paths to `venv/Scripts/*.exe` dynamically.

### 6.2 Exposure Score Algorithm

```python
def calculate_exposure_score(breaches: list, accounts: list) -> int:
    score = 0
    # Weight: Breaches (High Impact)
    score += len(breaches) * 15
    # Weight: Social Footprint (Medium Impact)
    score += len(accounts) * 5
    # Penalty: High Volume
    if len(breaches) > 3: score += 20
    if len(accounts) > 10: score += 10
    return min(score, 100)
```

---

## 7. Deployment & Operations

### 7.1 Prerequisites
*   Python 3.10+
*   Neo4j Desktop (Running local DB on port 7687)
*   Virtual Environment (`venv`)
*   Dependencies: `fastapi`, `uvicorn`, `streamlit`, `sherlock-project`, `holehe`, `maigret`, `py2neo`, `sqlite3`

### 7.2 Startup Sequence
1.  **Neo4j:** Start via Neo4j Desktop or `neo4j start`.
2.  **Backend:** `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
3.  **Frontend:** `streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501`

### 7.3 Automation
*   **`restart.bat`**: Windows batch script to kill processes, start Neo4j, and launch both servers sequentially.

---

## 8. Future Roadmap

1.  **Async Task Queue (Celery):** Offload long-running scans (Maigret) to background workers to prevent HTTP timeouts.
2.  **Inference Engine:** Implement rules to suggest related emails/usernames based on pattern matching across breaches.
3.  **Automated Alerts:** Integrate `Apprise` to send desktop notifications when new breaches are detected in scheduled scans.
4.  **Report Generation:** Export PDF/HTML reports of the digital footprint for offline records.

---

## 9. Security Considerations

*   **Data Locality:** All databases (`.db`, `neo4j`) reside on the local filesystem. No cloud sync.
*   **Secrets Management:** API keys (HIBP) loaded from Environment Variables, never hardcoded.
*   **Input Sanitization:** All user inputs validated via Pydantic models before processing.
*   **Network Isolation:** Services bind strictly to `127.0.0.1`, preventing external LAN access.
