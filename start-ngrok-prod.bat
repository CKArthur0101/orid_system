@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

set "ENV_FILE=.env.prod"
set "PORT=3200"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PROD_FRONTEND_PORT=" "%ENV_FILE%"`) do (
        set "PORT=%%B"
    )
)

echo Starting ngrok for production frontend on http://localhost:%PORT%
echo (Must match PROD_FRONTEND_PORT in %ENV_FILE%)

where ngrok >nul 2>&1
if errorlevel 1 (
    echo ngrok not found in PATH. Install from https://ngrok.com/download
    popd
    exit /b 1
)

taskkill /IM ngrok.exe /F >nul 2>&1
ngrok http %PORT%

popd
