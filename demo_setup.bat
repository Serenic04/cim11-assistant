@echo off
REM Recree l environnement Python sur un poste autre que celui de developpement.
REM Le dossier .venv livre est lie en dur a C:\Users\mohan et ne fonctionne pas ailleurs.
cd /d "%~dp0"
echo Creation de l environnement virtuel...
python -m venv .venv || py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r data_api\requirements.txt
pip install -r app_streamlit\requirements.txt
pip install -r requirements-dev.txt
echo.
echo Termine. data_api, app_streamlit et pytest sont operationnels.
echo (model_api /predict necessite en plus torch + un GPU : voir model_api\requirements.txt)
pause
