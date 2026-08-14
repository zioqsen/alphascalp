@echo off
setlocal
set "MT5_DIR=%~dp0runtime\beta_04"
if not exist "%MT5_DIR%\terminal64.exe" (
  echo ECHEC : terminal beta_04 introuvable.
  pause
  exit /b 1
)
start "MT5 BETA 04" /D "%MT5_DIR%" "%MT5_DIR%\terminal64.exe" /portable
