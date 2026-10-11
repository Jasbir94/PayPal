@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 (
  echo APP Shield project folder is unavailable. Check whether its drive is unlocked and accessible.
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_app.ps1" %*
exit /b %errorlevel%
