@echo off
cd /d "%~dp0"
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
echo Create a read-only account. Use letters and numbers for the account name.
.venv\Scripts\python manage_user.py
pause
