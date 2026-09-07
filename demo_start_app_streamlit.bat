@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set MODEL_API_URL=http://localhost:8001
set DATA_API_URL=http://localhost:8000
set MODEL_API_KEY=dev-only-change-me
start "app_streamlit (:8501)" cmd /k streamlit run app_streamlit\app.py --server.port 8501
