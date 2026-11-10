@echo off
cd /d "%~dp0"
set "ARCHIVE_DATA=%LOCALAPPDATA%\ERArchive\data"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
rem Install the optional PDF renderer once when it is missing.
.venv\Scripts\python -c "import pymupdf" >nul 2>&1
if errorlevel 1 (
  echo Preparing PDF support. This may require network access.
  .venv\Scripts\python -m pip install --only-binary=:all: --timeout 15 --retries 1 -r requirements-pdf.txt
  if errorlevel 1 echo PDF support unavailable. Image processing will continue; check network and install requirements-pdf.txt.
)
echo Open http://127.0.0.1:8080 in your browser. Keep this window open.
.venv\Scripts\python app.py --startup-sync
pause
