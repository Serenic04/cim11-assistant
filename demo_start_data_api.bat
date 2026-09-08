@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [!] .venv absent ou inutilisable sur ce poste : utilisation du Python systeme.
    echo     Si un module manque, lancer d abord demo_setup.bat
)
set DATA_API_KEY=demo-key-portfolio
REM Base peuplee par l'ETL (34 663 codes, 509 214 codes post-coordonnes, 150 CRH).
REM Sans cette ligne, uvicorn demarre depuis la racine du depot et ouvre le fichier
REM .\data-api-local.db, qui existe mais est VIDE : /codes et /crh renverraient [].
set DATABASE_URL=sqlite:///./data_api/data-api-local.db
start "data_api (uvicorn :8000)" cmd /k python -m uvicorn data_api.app.main:app --port 8000
timeout /t 6 /nobreak >nul
start http://localhost:8000/docs
