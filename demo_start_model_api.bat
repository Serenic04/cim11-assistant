@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set MODEL_API_KEY=demo-key-portfolio
REM Le modele (base + adaptateur LoRA) n'est charge qu'a la premiere requete /predict
REM (chargement differe) : le service demarre donc sans GPU, /health, /metrics et la
REM documentation /docs sont immediatement disponibles. Seul /predict exige un GPU.
start "model_api (uvicorn :8001)" cmd /k python -m uvicorn model_api.app.main:app --port 8001
timeout /t 8 /nobreak >nul
start http://localhost:8001/docs
