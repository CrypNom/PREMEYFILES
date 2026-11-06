@echo off
title PREMEYFILES - Create admin
cd /d "%~dp0website"
..\venv\Scripts\python create_admin.py
echo.
pause
