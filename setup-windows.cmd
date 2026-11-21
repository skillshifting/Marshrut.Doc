@echo off
setlocal
cd /d "%~dp0backend" || exit /b 1
python --version || exit /b 1
if not exist ".venv-win\Scripts\python.exe" (
  python -m venv .venv-win || exit /b 1
)
".venv-win\Scripts\python.exe" -m pip install --upgrade pip || exit /b 1
".venv-win\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt || exit /b 1
".venv-win\Scripts\python.exe" -m app.train || exit /b 1
echo Setup complete. Run run-backend.cmd, then open http://127.0.0.1:8000
