@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" || exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup-with-research.ps1"
set "ERR=%ERRORLEVEL%"
popd
exit /b %ERR%
