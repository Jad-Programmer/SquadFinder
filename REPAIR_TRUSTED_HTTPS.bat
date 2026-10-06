@echo off
setlocal
cd /d "%~dp0"
title Repair SquadFinder Trusted HTTPS
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python secure_https.py --install-trust
if errorlevel 1 (
  echo.
  echo Automatic trust installation failed.
  echo Try right-clicking this file and choosing Run as administrator.
  pause
  exit /b 1
)
echo.
echo Trusted HTTPS is repaired for the current Windows user.
echo Completely close and reopen the browser, then use:
echo https://localhost:5443
pause
