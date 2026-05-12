@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

set "COMPOSE_PROJECT_NAME=orid-prod"
set "COMPOSE_FILE=docker-compose.prod.yml"
set "ENV_FILE=.env.prod"

if not exist "%ENV_FILE%" (
    echo Missing %ENV_FILE%. Copy .env.prod.example and fill in real production values first.
    popd
    exit /b 1
)

if not exist "%COMPOSE_FILE%" (
    echo Missing %COMPOSE_FILE%.
    popd
    exit /b 1
)

call :load_env || goto :fail

if not defined POSTGRES_USER (
    echo POSTGRES_USER is not set in %ENV_FILE%.
    goto :fail
)

if not defined POSTGRES_DB (
    echo POSTGRES_DB is not set in %ENV_FILE%.
    goto :fail
)

if not defined BACKUP_DIR (
    set "BACKUP_DIR=runtime\backups\postgres"
)

echo Validating production compose config...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" config >nul
if errorlevel 1 goto :fail

if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    if errorlevel 1 goto :fail
)

echo Ensuring the production database container is running...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d db
if errorlevel 1 goto :fail

call :wait_for_db || (
    echo Database did not become ready in time.
    goto :fail
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TIMESTAMP=%%I"
if not defined TIMESTAMP goto :fail

set "BACKUP_FILE=%BACKUP_DIR%\orid_prod_%TIMESTAMP%.dump"

echo Creating backup "%BACKUP_FILE%"...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" exec -T db pg_dump -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" -Fc > "%BACKUP_FILE%"
if errorlevel 1 (
    if exist "%BACKUP_FILE%" del "%BACKUP_FILE%" >nul 2>&1
    goto :fail
)

for %%F in ("%BACKUP_FILE%") do (
    if %%~zF EQU 0 (
        echo Backup file was created but is empty.
        del "%BACKUP_FILE%" >nul 2>&1
        goto :fail
    )
)

echo Backup created successfully:
echo   %BACKUP_FILE%
popd
exit /b 0

:load_env
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if not "%%~A"=="" call set "%%~A=%%~B"
)
exit /b 0

:wait_for_db
set "DB_READY_ATTEMPTS=0"
:wait_for_db_loop
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" exec -T db pg_isready -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a DB_READY_ATTEMPTS+=1
if %DB_READY_ATTEMPTS% GEQ 30 exit /b 1
echo Waiting for database readiness... (%DB_READY_ATTEMPTS%/30)
timeout /t 2 /nobreak >nul
goto :wait_for_db_loop

:fail
echo Backup failed.
popd
exit /b 1
