@echo off
cd /d "%~dp0frontend" || exit /b 1
where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js and npm were not found. Install Node.js LTS from https://nodejs.org/en/download/
  echo Then open a NEW CMD window and run run-frontend.cmd again.
  exit /b 1
)
if not exist "node_modules" (
  call npm install || exit /b 1
)
call npm run dev
