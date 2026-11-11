@echo off
set "SERVER_URL=http://10.216.121.62:8080/widget"
echo Checking widget. If an error appears, copy it or take a screenshot.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0widget_window.ps1" -ServerUrl "%SERVER_URL%"
echo.
echo Diagnostic log: %%TEMP%%\ER_widget_error.log
pause
