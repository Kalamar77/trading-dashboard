@echo off
cd /d "%~dp0"

cls
echo.
echo ========================================
echo  REYGON TRADING DASHBOARD
echo ========================================
echo.

REM Matar procesos Python anteriores
taskkill /F /IM python.exe >nul 2>&1

echo Iniciando servidor Flask...
start "Trading Dashboard Server" portable_python\python.exe app.py

echo.
echo Esperando a que el servidor responda...
echo.

:check_server
timeout /t 2 /nobreak >nul
portable_python\python.exe -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/', timeout=1)" >nul 2>&1

if errorlevel 1 (
    echo    Esperando servidor...
    goto check_server
)

echo.
echo ✓ Servidor listo!
echo.
echo Abriendo navegador...
start http://localhost:5000/

echo.
echo ========================================
echo  DASHBOARD INICIADO
echo ========================================
echo.
echo URL: http://localhost:5000/
echo.
pause