@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

echo Starting ORID production frontend tunnel...
echo This window waits for Docker and http://127.0.0.1:3200 before ngrok starts.
echo Do not close it while students are using the site.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-ngrok-prod.ps1"
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" (
    echo.
    echo Startup failed. Leave this window open and check the message above.
    pause
)

popd
exit /b %ERR%
