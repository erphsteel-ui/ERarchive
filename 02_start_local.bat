@echo off
cd /d "%~dp0"
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
echo Open http://127.0.0.1:8080 in your browser. Keep this window open.
.venv\Scripts\python app.py
pause
