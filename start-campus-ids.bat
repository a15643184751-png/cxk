@echo off
chcp 65001 >nul
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\startup\start-campus-ids.ps1" %*

endlocal
