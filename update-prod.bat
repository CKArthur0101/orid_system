@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

set "COMPOSE_PROJECT_NAME=orid-prod"
set "COMPOSE_FILE=docker-compose.prod.yml"
set "ENV_FILE=.env.prod"
set "SKIP_BACKUP=0"
set "SKIP_PULL=0"

for %%A in (%*) do (
    if /I "%%~A"=="--skip-backup" set "SKIP_BACKUP=1"
    if /I "%%~A"=="--skip-pull" set "SKIP_PULL=1"
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

if "%SKIP_BACKUP%"=="0" (
    call "%~dp0backup-db.bat"
    if errorlevel 1 goto :fail
) else (
    echo Skipping backup because --skip-backup was provided.
)

if "%SKIP_PULL%"=="0" (
    echo Pulling the latest committed changes...
    git pull --ff-only
    if errorlevel 1 goto :fail
) else (
    echo Skipping git pull because --skip-pull was provided.
)

echo Building production backend and frontend images...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" build backend frontend
if errorlevel 1 goto :fail

echo Ensuring the production database container is running...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d db
if errorlevel 1 goto :fail

call :wait_for_db || (
    echo Database did not become ready in time.
    goto :fail
)

echo Running Alembic migrations...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" run --rm backend alembic upgrade head
if errorlevel 1 goto :fail

echo Starting backend and frontend containers...
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d backend frontend
if errorlevel 1 goto :fail

echo.
echo Current production container status:
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" ps
if errorlevel 1 goto :fail

echo.
echo Recent production logs:
docker compose -p "%COMPOSE_PROJECT_NAME%" -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" logs --tail=50 backend frontend db
if errorlevel 1 goto :fail

echo.
echo Production update completed successfully.
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
echo Production update failed.
popd
exit /b 1
