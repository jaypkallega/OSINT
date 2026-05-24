@echo off
echo ============================================
echo    OPIP - OSINT Privacy Intelligence Platform
echo    Restart Script
echo ============================================
echo.

echo [1/5] Stopping Neo4j...
cd /d "neo4j-community-5.28.1\bin"
call neo4j stop
timeout /t 5 /nobreak >nul

echo [2/5] Killing existing Python processes...
taskkill /f /im python.exe 2>nul
taskkill /f /im uvicorn.exe 2>nul
taskkill /f /im streamlit.exe 2>nul
timeout /t 2 /nobreak >nul

echo [3/5] Starting Neo4j...
call neo4j start
echo       Waiting for Neo4j to initialize (10 seconds)...
timeout /t 10 /nobreak >nul

echo [4/5] Starting Backend Server (Port 8000)...
start cmd /k "title OPIP Backend && cd /d ..\..\backend && echo Starting OPIP Backend v2.0... && uvicorn main:app --host 127.0.0.1 --port 8000"

echo [5/5] Starting Dashboard (Port 8501)...
start cmd /k "title OPIP Dashboard && cd /d ..\..\dashboard && echo Starting OPIP Dashboard... && streamlit run dashboard.py --server.address=127.0.0.1 --server.port=8501"

echo.
echo ============================================
echo    ✅ OPIP Restart Complete!
echo.
echo    Backend:  http://127.0.0.1:8000
echo    Dashboard: http://127.0.0.1:8501
echo    Neo4j:    http://localhost:7474
echo ============================================
echo.
pause
