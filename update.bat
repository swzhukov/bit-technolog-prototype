@echo off
chcp 65001 >nul 2>&1
cd /d "C:\Projects\MiniMax\BIT_Tech"

echo.
echo Stopping server on port 8080...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo git pull...
git pull
if errorlevel 1 (
    echo.
    echo git pull FAILED. Run init-git.bat first.
    pause
    exit /b 1
)

echo.
echo Starting server...
start "BIT.Technolog" cmd /k "python app.py"
timeout /t 3 /nobreak >nul

echo.
echo Opening browser...
start http://localhost:8080

echo.
echo Updated and started.
pause
