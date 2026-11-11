@echo off
rem Change this address to the archive server internal IP and port.
set "SERVER_URL=http://10.216.121.62:8080/widget"
rem Put a shortcut in Win+R shell:startup to launch at sign-in.
start "" /b powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0widget_window.ps1" -ServerUrl "%SERVER_URL%"
exit /b
