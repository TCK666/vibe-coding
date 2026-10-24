@echo off
rem Business_Attribution_Analysis_System 一键启动（4 个窗口）
rem 首次使用前：python -m venv .venv && .venv\Scripts\pip install -r backend\requirements.txt
cd /d %~dp0

start "mock_auth(9001)" cmd /k ".venv\Scripts\python.exe -m uvicorn mock_auth.main:app --app-dir backend --port 9001"
start "mock_llm(9002)"  cmd /k ".venv\Scripts\python.exe -m uvicorn mock_llm.main:app --app-dir backend --port 9002"
start "backend(8000)"   cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000 --reload"
start "frontend(5173)"  cmd /k "cd frontend && npm run dev"

echo 全部服务已启动：mock_auth:9001 mock_llm:9002 backend:8000 frontend:5173
