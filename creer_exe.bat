@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Lancez d abord installer.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller --noconfirm --clean FMAssistant27.spec
if errorlevel 1 (
  echo La creation du .exe a echoue.
  pause
  exit /b 1
)
echo.
echo Termine : dist\FM Assistant 27\FM Assistant 27.exe
pause
