@echo off
echo ========================================
echo   OSINT Dashboard - Restart Script
echo ========================================
echo.

:: Step 1: Stop Neo4j
echo [1/3] Stopping Neo4j...
cd /d "%~dp0neo4j-community-5.28.1\bin"
call neo4j stop
if %errorlevel% neq 0 (
    echo Warning: Neo4j may not have been running or failed to stop.
)
timeout /t 3 /nobreak >nul

:: Step 2: Kill any running Python processes related to the dashboard
echo [2/3] Stopping backend and dashboard processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *dashboard*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *backend*" 2>nul
taskkill /F /FI "WINDOWTITLE eq *streamlit*" 2>nul
taskkill /F /FI "WINDOWTITLE eq *uvicorn*" 2>nul
timeout /t 2 /nobreak >nul

:: Step 3: Start Neo4j
echo [3/3] Starting Neo4j...
call neo4j start
if %errorlevel% neq 0 (
    echo Error: Failed to start Neo4j. Please check installation.
    pause
    exit /b 1
)

:: Wait for Neo4j to initialize
echo.
echo Waiting for Neo4j to initialize (15 seconds)...
timeout /t 15 /nobreak >nul

:: Step 4: Start Backend
echo.
echo ========================================
echo   Starting Backend Server...
echo ========================================
start "OSINT Backend" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate && uvicorn backend:app --reload --host 127.0.0.1 --port 8000"

:: Small delay to ensure backend starts first
timeout /t 3 /nobreak >nul

:: Step 5: Start Dashboard
echo.
echo ========================================
echo   Starting Streamlit Dashboard...
echo ========================================
start "OSINT Dashboard" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate && streamlit run dashboard.py"

echo.
echo ========================================
echo   Restart Complete!
echo ========================================
echo   - Neo4j is starting (wait ~30s for full readiness)
echo   - Backend: http://127.0.0.1:8000
echo   - Dashboard: http://localhost:8501
echo.
echo Press any key to exit this window...
pause >nul
