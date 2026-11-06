@echo off
title PREMEYFILES - Backup
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set STAMP=%%i
if not exist backups mkdir backups
echo Backing up database and uploaded files...
powershell -NoProfile -Command "Compress-Archive -Path 'database','website\uploads' -DestinationPath 'backups\premeyfiles_%STAMP%.zip' -Force"
if errorlevel 1 ( echo Backup FAILED. & pause & exit /b 1 )
echo Done: backups\premeyfiles_%STAMP%.zip
pause
