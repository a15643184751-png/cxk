@echo off
chcp 65001 >nul
setlocal

if exist "D:\ids\runtime\venvs\ids-backend\Scripts\python.exe" (
  "D:\ids\runtime\venvs\ids-backend\Scripts\python.exe" "D:\ids\runtime\startup\configure_ids_multisite.py"
) else (
  python "D:\ids\runtime\startup\configure_ids_multisite.py"
)

endlocal
