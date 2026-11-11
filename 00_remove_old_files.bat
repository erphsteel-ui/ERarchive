@echo off
cd /d "%~dp0"
echo Removing retired program files only. Data and .venv are not touched.
for %%F in (news.py news_filter.py news_grouping.py news_preview.py steel_press.py run_widget.bat widget_window.ps1 pin_to_desktop.ps1 pin_widget.py desktop_widget.py memos.py precision.py vl_adapter.py vl_worker.py 07_check_vl.bat) do if exist "%%F" del /q "%%F"
for %%F in (news.js widget.js widget.css memos.js precision.js) do if exist "static\%%F" del /q "static\%%F"
if exist "templates\widget.html" del /q "templates\widget.html"
echo Done. Start the server and refresh the browser.
pause
