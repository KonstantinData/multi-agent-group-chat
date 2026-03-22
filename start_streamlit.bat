@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launcher.py
) else (
  echo Repository virtual environment not found at .venv\Scripts\python.exe
  exit /b 1
)
pause
