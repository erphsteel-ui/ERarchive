@echo off
cd /d "%~dp0"
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
.venv\Scripts\python backup.py
pause
