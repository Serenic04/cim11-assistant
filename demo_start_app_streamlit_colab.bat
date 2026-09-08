@echo off
REM Lance app_streamlit en pointant model_api vers le tunnel Colab (GPU distant).
REM Le script d origine (demo_start_app_streamlit.bat) reste intact : en cas de
REM probleme, on y revient et on retombe sur le PLAN B.
REM
REM Usage :  demo_start_app_streamlit_colab.bat https://xxxx.trycloudflare.com
cd /d "%~dp0"

if "%~1"=="" (
    echo.
    echo Usage : demo_start_app_streamlit_colab.bat ^<URL du tunnel^>
    echo Exemple : demo_start_app_streamlit_colab.bat https://abc-def.trycloudflare.com
    echo.
    echo L URL est affichee par la cellule 7 du notebook colab_model_api.ipynb.
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [!] .venv absent : utilisation du Python systeme.
)

set MODEL_API_URL=%~1
set DATA_API_URL=http://localhost:8000
set MODEL_API_KEY=demo-key-portfolio
set DATA_API_KEY=demo-key-portfolio
REM Le GPU distant et le tunnel demandent plus que les 30 s prevues en local.
set MODEL_API_TIMEOUT_S=180
set MONITORING_TIMEOUT_S=15

echo.
echo   model_api distant : %MODEL_API_URL%
echo   data_api local    : %DATA_API_URL%
echo.
start "app_streamlit (:8501) - model_api via Colab" cmd /k streamlit run app_streamlit\app.py --server.port 8501
