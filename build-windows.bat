@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0build-windows.ps1"
exit /b %ERRORLEVEL%
