@echo off
title PREMEYFILES - Website (keep this window open)
cd /d "%~dp0website"
echo Website starting at http://127.0.0.1:5000   (press CTRL+C to stop)
..\venv\Scripts\python -m waitress --listen=127.0.0.1:5000 app:app
pause
