@echo off
rem Business_Attribution_Analysis_System - start all services in 4 windows
rem First run auto-creates .venv and installs dependencies (needs network).

cd /d %~dp0

if not exist ".venv\Scripts\python.exe" (
    echo [setup] creating venv and installing backend deps, please wait...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
)

if not exist "frontend\node_modules" (
    echo [setup] installing frontend deps, please wait...
    cmd /c "cd frontend && npm install"
)

start "mock_auth 9001" cmd /k ".venv\Scripts\python.exe -m uvicorn mock_auth.main:app --app-dir backend --port 9001"
start "mock_llm 9002"  cmd /k ".venv\Scripts\python.exe -m uvicorn mock_llm.main:app --app-dir backend --port 9002"
start "backend 8000"   cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000 --reload"
start "frontend 5173"  cmd /k "cd frontend && npm run dev"

echo.
echo All services started:
echo   mock_auth  - http://127.0.0.1:9001
echo   mock_llm   - http://127.0.0.1:9002
echo   backend    - http://localhost:8000/docs
echo   frontend   - http://localhost:5173
echo.
echo Close the 4 new windows to stop the services.
pause
