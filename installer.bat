@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Installation de FM Assistant 27 ===
where py >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installez Python 3.12 depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH", puis relancez ce fichier.
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo L installation a echoue. Verifiez votre connexion Internet et relancez.
  pause
  exit /b 1
)
echo.
echo Installation terminee. Double-cliquez sur lancer.bat pour demarrer.
pause
