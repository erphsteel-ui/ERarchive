@echo off
rem Change this address to the archive server's internal IP and port.
set "SERVER_URL=http://10.216.121.62:8080/widget"
rem Optional: Win+R, type shell:startup, and place a shortcut to this file there.
start "" msedge --app="%SERVER_URL%" --window-size=380,650 --window-position=1500,50
exit /b
