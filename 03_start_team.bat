@echo off
cd /d "%~dp0"
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
echo Team mode: use this PC's INTERNAL IP and port 8080. Requires permitted inbound access.
echo Do not run local and team modes together. Keep this window open.
.venv\Scripts\python app.py --host 0.0.0.0
pause
