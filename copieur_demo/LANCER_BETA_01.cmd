@echo off
setlocal
set "MT5_DIR=%~dp0runtime\beta_01"
if not exist "%MT5_DIR%\terminal64.exe" (
  echo ECHEC : terminal beta_01 introuvable.
  pause
  exit /b 1
)
start "MT5 BETA 01" /D "%MT5_DIR%" "%MT5_DIR%\terminal64.exe" /portable
