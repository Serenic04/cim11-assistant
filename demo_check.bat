@echo off
REM Controle avant soutenance. Trouve un interpreteur Python utilisable,
REM puis delegue tous les controles a demo_check.py.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" demo_check.py
    if not errorlevel 9009 goto fin
)

python demo_check.py
if not errorlevel 9009 goto fin

py demo_check.py
if not errorlevel 9009 goto fin

echo.
echo [KO] Aucun interpreteur Python n a pu etre lance sur ce poste.
echo      Installer Python 3.12+ puis relancer demo_setup.bat

:fin
echo.
pause
