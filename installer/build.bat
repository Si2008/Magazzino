@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente di sviluppo non trovato. Leggere installer\README.md.
  exit /b 1
)
".venv\Scripts\python.exe" -B tools\crea_installer.py %*
if errorlevel 1 exit /b 1
echo Setup creato correttamente.
endlocal
