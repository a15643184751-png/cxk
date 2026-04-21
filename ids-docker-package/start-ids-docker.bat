@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0start-ids-docker.ps1" %*
endlocal
