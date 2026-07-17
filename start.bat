@echo off
chcp 65001 >nul
REM ===========================================
REM  start.bat — запуск БИТ.Технолог
REM  Использование: двойной клик или .\start.bat
REM ===========================================

cd /d C:\Projects\MiniMax\BIT_Tech

echo.
echo === Останавливаю старый сервер (если есть) ===
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8080 ^| findstr LISTENING') do (
    echo   kill PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo === Запускаю сервер ===
start "БИТ.Технолог" cmd /k "python app.py"

echo Жду запуска (3 сек)...
timeout /t 3 /nobreak >nul

echo.
echo === Открываю браузер ===
start http://localhost:8080

echo.
echo ===========================================
echo  Сервер запущен в отдельном окне.
echo  Чтобы остановить — закрой то окно.
echo ===========================================
echo.
pause
