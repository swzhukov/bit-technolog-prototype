@echo off
chcp 65001 >nul
REM ===========================================
REM  update.bat — обновление из GitHub + рестарт
REM  Использование: двойной клик или .\update.bat
REM ===========================================

cd /d C:\Projects\MiniMax\BIT_Tech

echo.
echo === 1/3 Останавливаю сервер ===
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo === 2/3 git pull ===
git pull
if errorlevel 1 (
    echo.
    echo *** git pull FAILED ***
    echo Проверь, что init-git.bat был запущен.
    echo.
    pause
    exit /b 1
)

echo.
echo === 3/3 Запускаю сервер ===
start "БИТ.Технолог" cmd /k "python app.py"
timeout /t 3 /nobreak >nul

echo.
echo === Открываю браузер ===
start http://localhost:8080

echo.
echo ===========================================
echo  Обновлено и запущено.
echo ===========================================
echo.
pause
