@echo off
setlocal
set "MT5_DIR=%~dp0runtime\beta_02"
if not exist "%MT5_DIR%\terminal64.exe" (
  echo ECHEC : terminal beta_02 introuvable.
  pause
  exit /b 1
)
start "MT5 BETA 02" /D "%MT5_DIR%" "%MT5_DIR%\terminal64.exe" /portable
