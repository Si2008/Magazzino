@echo off
setlocal
set "MAGAZZINO_CONFIG=%~dp0config.toml"
if not exist "%MAGAZZINO_CONFIG%" (
    echo Configurazione del Magazzino non trovata: %MAGAZZINO_CONFIG%
    pause
    exit /b 1
)
start "" /D "%~dp0" "%~dp0dist\UI-2.4.3-20261106-finale\MagazzinoProfili-2.4.3\MagazzinoProfili.exe" %*
endlocal
