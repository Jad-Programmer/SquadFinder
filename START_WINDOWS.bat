@echo off
setlocal
cd /d "%~dp0"
title MetaVerse SquadFinder - Trusted HTTPS

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the private Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto :failed
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :failed
pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Preparing a trusted HTTPS certificate for this Windows account...
python secure_https.py --install-trust
if errorlevel 1 (
  echo.
  echo SquadFinder could not add its certificate to your Windows trust store.
  echo Close this window, right-click REPAIR_TRUSTED_HTTPS.bat, and choose Run as administrator.
  pause
  exit /b 1
)

set SQUADFINDER_HTTPS=1
set SQUADFINDER_FORCE_HTTPS=1
set SQUADFINDER_SSL_CERT=%LOCALAPPDATA%\MetaVerseSquadFinder\trusted_https\squadfinder_server.crt
set SQUADFINDER_SSL_KEY=%LOCALAPPDATA%\MetaVerseSquadFinder\trusted_https\squadfinder_server_key.pem
set PORT=5443

echo.
echo ============================================================
echo  MetaVerse SquadFinder is starting with trusted HTTPS
echo  Open: https://localhost:5443
echo ============================================================
echo.
echo Use the localhost address above on this computer.
echo Do not use the old http://127.0.0.1:5000 address.
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul & start https://localhost:5443"
python app.py
goto :end

:failed
echo.
echo SquadFinder setup failed. Review the error above.
pause
exit /b 1

:end
pause
