@echo off
title PREMEYFILES - Install
cd /d "%~dp0"
echo ============================================
echo   PREMEYFILES - installing (run this once)
echo ============================================
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo ERROR: Python was not found.
  echo Install Python from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during setup. Then run this again.
  pause
  exit /b 1
)
if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
echo Installing website + admin requirements...
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r website\requirements.txt -r admin_software\requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)
if not exist .env (
  copy .env.example .env >nul
  echo Created your .env settings file.
)
echo.
echo DONE. Next: double-click 2_CREATE_ADMIN.bat
pause
