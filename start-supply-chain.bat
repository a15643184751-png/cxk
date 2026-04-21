@echo off
chcp 65001 >nul
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\startup\start-supply-chain.ps1" %*

endlocal
