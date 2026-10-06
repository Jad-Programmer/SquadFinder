@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python is required. Install Python 3.12 or newer, then run this file again.
  pause
  exit /b 1
)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\prepare_supabase.py
pause
