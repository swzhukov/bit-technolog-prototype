@echo off
chcp 65001 >nul 2>&1
cd /d "C:\Projects\MiniMax\BIT_Tech"

echo.
echo Stopping old server on port 8080...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo   killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo Starting server...
start "BIT.Technolog" cmd /k "python app.py"
timeout /t 3 /nobreak >nul

echo.
echo Opening browser...
start http://localhost:8080

echo.
echo Server started in separate window. Close that window to stop.
pause
