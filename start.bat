@echo off
echo ================================================
echo  OSINT Privacy Intelligence App - Startup Script
echo ================================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: py -3.12 -m venv venv
    echo Then install requirements: venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Get local IP address
echo [INFO] Detecting local IP addresses...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    for %%b in (%%a) do set LOCAL_IP=%%b
)
if defined LOCAL_IP (
    echo [+] Local IP Address: %LOCAL_IP%
) else (
    echo [+] Local IP Address: 127.0.0.1 (localhost)
)
echo.

REM Display port information
echo [INFO] Application will be available at:
echo   - Backend API:    http://127.0.0.1:8000
echo   - Frontend Dashboard: http://127.0.0.1:8501
echo   - API Docs:       http://127.0.0.1:8000/docs
echo.

REM Start backend in a new window
echo [INFO] Starting backend server (FastAPI on port 8000)...
start "OSINT Backend" cmd /k "title OSINT Backend Server && echo Backend starting on http://127.0.0.1:8000 && echo API Docs available at http://127.0.0.1:8000/docs && echo. && uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

REM Wait for backend to initialize
echo [INFO] Waiting for backend to initialize (5 seconds)...
timeout /t 5 /nobreak >nul

REM Start frontend in a new window
echo [INFO] Starting frontend dashboard (Streamlit on port 8501)...
start "OSINT Frontend" cmd /k "title OSINT Frontend Dashboard && echo Frontend starting on http://127.0.0.1:8501 && echo. && streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501"

echo.
echo ================================================
echo  Startup Complete!
echo ================================================
echo.
echo  Services running:
echo    [*] Backend:  http://127.0.0.1:8000
echo    [*] Frontend: http://127.0.0.1:8501
echo    [*] API Docs: http://127.0.0.1:8000/docs
echo.
echo  Two new windows have opened:
echo    - OSINT Backend (showing live logs)
echo    - OSINT Frontend (Streamlit dashboard)
echo.
echo  To stop the services, close the two windows or press Ctrl+C in each.
echo ================================================
echo.
pause
