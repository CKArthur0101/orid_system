@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

set "COMPOSE_PROJECT_NAME=orid-prod"
set "COMPOSE_FILE=docker-compose.prod.yml"
set "ENV_FILE=.env.prod"
set "CONFIRMED=0"
set "TMP_RESTORE_FILE=/tmp/orid_restore.dump"

if "%~1"=="" goto :usage

set "BACKUP_FILE=%~f1"

if /I "%~2"=="--yes" set "CONFIRMED=1"

if not exist "%BACKUP_FILE%" (
    echo Backup file not found: %BACKUP_FILE%
    popd
    exit /b 1
)

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

echo Validating production compose config...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" config >nul
if errorlevel 1 goto :fail

if "%CONFIRMED%"=="0" (
    echo This will stop the production app containers, take a fresh safety backup, and restore:
    echo   %BACKUP_FILE%
    set /p "RESTORE_CONFIRM=Type RESTORE to continue: "
    if /I not "%RESTORE_CONFIRM%"=="RESTORE" (
        echo Restore cancelled.
        popd
        exit /b 1
    )
)

call "%~dp0backup-db.bat"
if errorlevel 1 goto :fail

echo Ensuring the production database container is running...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d db
if errorlevel 1 goto :fail

call :wait_for_db || (
    echo Database did not become ready in time.
    goto :fail
)

echo Stopping backend and frontend before restore...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" stop backend frontend
if errorlevel 1 goto :fail

for /f %%I in ('docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" ps -q db') do set "DB_CONTAINER_ID=%%I"
if not defined DB_CONTAINER_ID (
    echo Could not determine the database container ID.
    goto :fail
)

echo Copying the selected backup into the database container...
docker cp "%BACKUP_FILE%" "%DB_CONTAINER_ID%:%TMP_RESTORE_FILE%"
if errorlevel 1 goto :fail

echo Restoring the production database...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" exec -T db pg_restore --clean --if-exists --no-owner --no-privileges -U "%POSTGRES_USER%" -d "%POSTGRES_DB%" "%TMP_RESTORE_FILE%"
if errorlevel 1 goto :restore_cleanup

echo Cleaning up the temporary restore artifact...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" exec -T db rm -f "%TMP_RESTORE_FILE%" >nul 2>&1

echo Restarting backend and frontend containers...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d backend frontend
if errorlevel 1 goto :fail

echo.
echo Current production container status:
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" ps
if errorlevel 1 goto :fail

echo.
echo Database restore completed successfully.
popd
exit /b 0

:restore_cleanup
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" exec -T db rm -f "%TMP_RESTORE_FILE%" >nul 2>&1
goto :fail

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

:usage
echo Usage: restore-db.bat path\to\backup.dump [--yes]
popd
exit /b 1

:fail
echo Database restore failed.
popd
exit /b 1
