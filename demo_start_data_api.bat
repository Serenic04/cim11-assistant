@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set DATA_API_KEY=demo-key-portfolio
set DATABASE_URL=
start "data_api (uvicorn :8000)" cmd /k python -m uvicorn data_api.app.main:app --port 8000
timeout /t 6 /nobreak >nul
start http://localhost:8000/docs
