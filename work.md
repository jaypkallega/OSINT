# OSINT Privacy Intelligence Platform (OPIP) - Technical Implementation Log

## Project Overview
**Project Name:** OSINT Privacy Intelligence Platform (OPIP)  
**Version:** 2.0.0 (Refactored)  
**Architecture:** Localhost-only, Single-user, FastAPI + Streamlit  
**Date:** May 2026  
**Status:** Core Scanning Engine Stabilized, Persistence Layer Implemented

---

## 1. Executive Summary of Accomplishments

This document details the technical remediation and feature implementation performed on the OPIP codebase to resolve critical execution errors, implement data persistence, and align the prototype with the v1.0.0 Design Document. The primary focus was stabilizing the orchestration of external OSINT binaries (Sherlock, Holehe, Maigret) within a Windows virtual environment, resolving argument parsing conflicts, and establishing a SQLite/Neo4j hybrid storage backend.

---

## 2. Critical Bug Fixes & Stability Improvements

### 2.1 Sherlock Binary Argument Parsing Resolution
**Issue:** The `sherlock` executable (v0.16.0) installed via `pip` in the Windows virtual environment expects a filename argument for the `--json` flag (`--json output.json`), whereas the initial implementation passed it as a stdout flag (`--json`), causing `ArgumentParser` errors and non-zero exit codes.
**Resolution:**
- Implemented a **dual-mode execution strategy** in `backend/main.py`:
  1. **Primary Mode:** Attempts execution using `--print-found` (stdout compatible).
  2. **Fallback Mode:** If primary fails or returns empty, dynamically generates a temporary JSON file path, executes `--json <temp_path>`, parses the file, and cleans up.
- Added robust `subprocess` error handling to distinguish between CLI usage errors and "no results" scenarios.
- Enforced absolute path resolution for `sherlock.exe` using `os.environ.get("VIRTUAL_ENV")` to prevent `FileNotFoundError` in subprocess contexts.

### 2.2 Streamlit Element Key Collision
**Issue:** `StreamlitDuplicateElementKey` errors occurred when rendering the "View Graph" button multiple times during script reruns or when scanning identical emails.
**Resolution:**
- Refactored button key generation to include a unique instance identifier: `f"view_graph_btn_{email}_{id(result)}"`.
- Removed duplicate function calls in `dashboard.py` that caused multiple renders of the same component tree.

### 2.3 Virtual Environment Path Resolution
**Issue:** Backend subprocesses failed to locate installed binaries (`sherlock`, `holehe`, `maigret`) due to reliance on system `PATH` rather than the active virtual environment's `Scripts/` directory.
**Resolution:**
- Created a unified helper function `get_venv_script_path(script_name)` in `backend/main.py`.
- Logic:
  ```python
  if os.name == 'nt':
      return os.path.join(venv_path, "Scripts", f"{script_name}.exe")
  else:
      return os.path.join(venv_path, "bin", script_name)
  ```
- Ensures binary execution works regardless of how the backend process is spawned (e.g., via batch files or IDEs).

---

## 3. Backend Architecture Enhancements (`backend/main.py`)

### 3.1 Orchestrator Refactoring
- **Synchronous to Hybrid Execution:** While full Celery integration is pending, the orchestrator now handles long-running tools with explicit timeouts (`timeout=60s` for Sherlock/Holehe, `timeout=90s` for Maigret) to prevent API gateway timeouts.
- **Tool Integration:**
  - **Sherlock:** Configured for username-based scanning with JSON output parsing.
  - **Holehe:** Configured for email-based registration checking with NDJSON (Newline Delimited JSON) parsing logic.
  - **Maigret:** Configured with site limits (`-n 50`) and timeouts to balance depth vs. performance.
  - **HIBP (Have I Been Pwned):** Async implementation using `httpx` for breach lookup.
  - **PwnedPasswords:** Implemented K-Anonymity SHA-1 hash prefix/suffix comparison for password exposure checks without transmitting plaintext passwords.

### 3.2 Data Normalization
- Standardized output schemas for all tools into a unified `Dict[str, Any]` format:
  ```python
  {
      "platform": str,
      "username": str,
      "url": str,
      "source_tool": str,
      "status": "Found" | "Registered" | "Error"
  }
  ```
- Implemented error wrapping to ensure UI stability even when individual tools fail (e.g., returning `{"warning": "..."}` instead of crashing).

---

## 4. Data Persistence Implementation (SQLite)

### 4.1 Schema Design
Implemented a local SQLite database (`data/osint.db`) to replace ephemeral session storage.
**Tables Created:**
1.  **`users`**: Stores profile metadata (name, email, photo path).
2.  **`scans`**: Records scan metadata (timestamp, target input, scan type).
3.  **`breaches`**: Links scans to HIBP breach data (Name, Date, DataClasses).
4.  **`social_accounts`**: Stores discovered accounts (Platform, URL, Source Tool).
5.  **`broker_optouts`**: Tracks opt-out workflow status (Broker Name, Status, Submitted At).

### 4.2 Implementation Details
- Used Python's built-in `sqlite3` module with context managers for connection safety.
- Added `init_db()` function to auto-create tables on startup if missing.
- Modified `/api/scan` endpoint to persist results immediately after tool execution.
- Added `/api/history` endpoint to retrieve past scans from SQLite.

---

## 5. Graph Database Integration (Neo4j)

### 5.1 Connection Strategy
- Integrated `neo4j` Python driver.
- Implemented graceful degradation: If Neo4j is unreachable (port 7687), the system logs a warning and continues in "Lite Mode" (SQLite only).
- Configuration via environment variables: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.

### 5.2 Graph Population Logic
- **Nodes:** Created dynamic node labels for `Email`, `Username`, `Breach`, `SocialAccount`, `Phone`.
- **Relationships:** Defined edges based on scan results:
  - `(Email)-[:FOUND_IN]->(Breach)`
  - `(Username)-[:REGISTERED_ON]->(SocialAccount)`
  - `(Email)-[:ASSOCIATED_WITH]->(Username)`
- **Visualization:** Updated `show_relationship_graph()` in `dashboard.py` to query Neo4j Cypher statements if available, falling back to local Plotly generation if not.

---

## 6. Security & Guarded Features

### 6.1 Input Validation
- Enforced strict regex validation for emails and phone numbers before tool invocation.
- Implemented "Self-Discovery" confirmation dialogs for sensitive scans (Phone, Data Brokers) in the UI layer.

### 6.2 Password Handling
- **K-Anonymity:** Implemented SHA-1 hashing for password checks. Only the first 5 characters of the hash are sent to the PwnedPasswords API; suffix matching is performed locally.
- **No Plaintext Storage:** Passwords are never logged or stored in SQLite/Neo4j.

### 6.3 Broker Opt-Out Workflow
- Populated `BROKER_OPTOUT_URLS` dictionary with 15+ major data brokers (Spokeo, WhitePages, etc.).
- Implemented state machine for opt-out tracking: `pending` → `submitted` → `confirmed`.

---

## 7. Deployment & Operations

### 7.1 Windows Batch Automation
Created `restart.bat` to automate the full stack restart sequence:
1.  Stop Neo4j service.
2.  Kill lingering Python/Uvicorn/Streamlit processes.
3.  Start Neo4j.
4.  Launch Backend (Uvicorn) and Frontend (Streamlit) in separate terminal windows.

### 7.2 Environment Configuration
- Standardized `.env` usage for API keys (HIBP) and Database credentials.
- Ensured virtual environment activation is handled correctly within batch scripts.

---

## 8. Current System State

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Frontend (Streamlit)** | ✅ Operational | Graph visualization fixed, duplicate key errors resolved. |
| **Backend API (FastAPI)** | ✅ Operational | v2.0.0, robust error handling, dual-mode Sherlock. |
| **Sherlock Integration** | ✅ Fixed | Dual-mode execution resolves CLI arg errors. |
| **Holehe Integration** | ✅ Operational | NDJSON parsing implemented. |
| **Maigret Integration** | ✅ Operational | Timeout and limit constraints applied. |
| **SQLite Persistence** | ✅ Implemented | Scan history and results persisted locally. |
| **Neo4j Graph DB** | ⚠️ Optional | Functional if running; graceful fallback if offline. |
| **Celery/Redis Queue** | 🚧 Pending | Currently synchronous; async queue architecture designed but not yet deployed. |
| **Data Broker Workflow** | ✅ Implemented | URLs and DB schema ready; UI guards in place. |

---

## 9. Known Limitations & Next Steps

1.  **Synchronous Blocking:** Heavy scans (Maigret full run) still block the API thread. **Next Step:** Deploy Celery workers with Redis broker.
2.  **Inference Engine:** Rule-based email inference (F-060) is designed but not fully coded.
3.  **Metadata Extraction:** Metagoofil/ExifTool integration is pending implementation in the module layer.
4.  **Alerting:** Apprise integration for desktop/Telegram alerts is pending.

---

## 10. Technical Debt Addressed

- Removed hardcoded paths; now uses dynamic `VIRTUAL_ENV` detection.
- Eliminated `st.session_state` dependency for critical data; now relies on DB.
- Resolved race conditions in Streamlit widget rendering.
- Fixed JSON parsing failures for tools with non-standard output formats.

---

*End of Technical Implementation Log*
