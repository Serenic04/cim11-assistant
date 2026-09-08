@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [!] .venv absent ou inutilisable sur ce poste : utilisation du Python systeme.
    echo     Si un module manque, lancer d abord demo_setup.bat
)
set MODEL_API_URL=http://localhost:8001
set DATA_API_URL=http://localhost:8000
set MODEL_API_KEY=demo-key-portfolio
REM Doit correspondre a la cle definie dans demo_start_data_api.bat : sans elle,
REM le recoupement du libelle officiel au referentiel echoue en 401 (US2).
set DATA_API_KEY=demo-key-portfolio
start "app_streamlit (:8501)" cmd /k streamlit run app_streamlit\app.py --server.port 8501
