@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [!] .venv absent ou inutilisable sur ce poste : utilisation du Python systeme.
    echo     Si un module manque, lancer d abord demo_setup.bat
)
set MODEL_API_KEY=demo-key-portfolio
REM Chemin de l'adaptateur LoRA. Le defaut du code est relatif au dossier courant
REM (../Fine-Tuning/...) et pointerait donc HORS du depot depuis cette racine.
set ADAPTER_PATH=./Fine-Tuning/llama3_codage_cim11
REM Le modele (base + adaptateur LoRA) n'est charge qu'a la premiere requete /predict
REM (chargement differe) : le service demarre donc sans GPU, /health, /metrics et la
REM documentation /docs sont immediatement disponibles. Seul /predict exige un GPU.
start "model_api (uvicorn :8001)" cmd /k python -m uvicorn model_api.app.main:app --port 8001
timeout /t 8 /nobreak >nul
start http://localhost:8001/docs
