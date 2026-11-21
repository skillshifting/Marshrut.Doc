@echo off
cd /d "%~dp0backend" || exit /b 1
if not exist ".venv-win\Scripts\python.exe" (
  echo Run setup-windows.cmd first.
  exit /b 1
)
".venv-win\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
