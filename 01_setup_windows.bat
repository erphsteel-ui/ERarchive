@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install --no-index --find-links offline-wheels-windows -r requirements.txt
if errorlevel 1 goto fail
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
.venv\Scripts\python app.py --user admin --role admin
pause
exit /b
:fail
echo Setup failed. Check Python 3.12 x64 and company installation permissions.
pause
