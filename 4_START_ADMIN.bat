@echo off
title PREMEYFILES ADMIN
cd /d "%~dp0admin_software"
..\venv\Scripts\python main.py
if errorlevel 1 pause
