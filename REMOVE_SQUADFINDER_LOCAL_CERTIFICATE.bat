@echo off
setlocal
cd /d "%~dp0"
title Remove SquadFinder Local Certificate
if not exist ".venv\Scripts\python.exe" (
  echo The SquadFinder Python environment was not found.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python secure_https.py --uninstall-trust
if errorlevel 1 (
  echo The certificate could not be removed automatically.
) else (
  echo The SquadFinder certificate is no longer trusted by this Windows user.
)
pause
