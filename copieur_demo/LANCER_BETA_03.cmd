@echo off
setlocal
set "MT5_DIR=%~dp0runtime\beta_03"
if not exist "%MT5_DIR%\terminal64.exe" (
  echo ECHEC : terminal beta_03 introuvable.
  pause
  exit /b 1
)
start "MT5 BETA 03" /D "%MT5_DIR%" "%MT5_DIR%\terminal64.exe" /portable
