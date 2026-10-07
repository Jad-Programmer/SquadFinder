@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SquadFinder Windows EXE Builder

echo.
echo ============================================================
echo              SquadFinder Windows EXE Builder
echo ============================================================
echo.
echo This builder downloads the latest Jad-Programmer/SquadFinder
echo source from GitHub and creates SquadFinder.exe on this PC.
echo.

set "BASE=%~dp0"
set "WORK=%BASE%_squadfinder_exe_build"
set "ZIP=%WORK%\squadfinder-main.zip"
set "REPOURL=https://github.com/Jad-Programmer/SquadFinder/archive/refs/heads/main.zip"

if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%" >nul 2>nul

echo [1/7] Finding Python...
set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -c "import sys; print(sys.version)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.13"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo.
    echo Python was not found.
    echo Install Python 3.13 for Windows from:
    echo https://www.python.org/downloads/windows/
    echo.
    echo IMPORTANT: During installation enable "Add python.exe to PATH".
    echo Then run this builder again.
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%

echo.
echo [2/7] Downloading the latest SquadFinder source...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri '%REPOURL%' -OutFile '%ZIP%'"
if errorlevel 1 goto :failed

echo.
echo [3/7] Extracting source...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%WORK%' -Force"
if errorlevel 1 goto :failed

set "SRC="
for /d %%D in ("%WORK%\SquadFinder-*") do (
    set "SRC=%%~fD"
)

if not defined SRC (
    echo Could not find extracted SquadFinder source.
    goto :failed
)

copy /y "%BASE%desktop_launcher.py" "%SRC%\desktop_launcher.py" >nul
if errorlevel 1 goto :failed

echo.
echo [4/7] Creating isolated build environment...
%PYTHON_CMD% -m venv "%WORK%\venv"
if errorlevel 1 goto :failed

call "%WORK%\venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo.
echo [5/7] Installing build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :failed

python -m pip install -r "%SRC%\requirements.txt"
if errorlevel 1 goto :failed

python -m pip install pyinstaller pywebview waitress
if errorlevel 1 goto :failed

echo.
echo [6/7] Building SquadFinder.exe...
cd /d "%SRC%"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name SquadFinder ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "schema_postgres.sql;." ^
  --collect-all webview ^
  --collect-all clr_loader ^
  --collect-all psycopg ^
  --collect-all psycopg_pool ^
  --hidden-import clr ^
  desktop_launcher.py

if errorlevel 1 goto :failed

if not exist "%SRC%\dist\SquadFinder.exe" (
    echo Build finished but SquadFinder.exe was not found.
    goto :failed
)

echo.
echo [7/7] Copying finished EXE...
copy /y "%SRC%\dist\SquadFinder.exe" "%BASE%SquadFinder.exe" >nul
if errorlevel 1 goto :failed

cd /d "%BASE%"
deactivate >nul 2>nul

echo.
echo ============================================================
echo SUCCESS
echo ============================================================
echo.
echo Your Windows app is here:
echo.
echo   %BASE%SquadFinder.exe
echo.
echo Double-click SquadFinder.exe.
echo On first launch it will ask for the user's own Supabase
echo Session Pooler Database URL.
echo.
echo NOTE: Because this EXE is not code-signed, Windows Defender or
echo SmartScreen may show an "Unknown publisher" warning.
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo BUILD FAILED
echo ============================================================
echo.
echo The builder could not create the EXE.
echo Keep this window open and send the error shown above to ChatGPT.
echo.
pause
exit /b 1
