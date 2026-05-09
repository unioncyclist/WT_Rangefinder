@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "%~dp0shape_distance.py"
) else (
  py "%~dp0shape_distance.py"
)

if errorlevel 1 (
  echo.
  echo 程序异常退出，按任意键关闭...
  pause >nul
)

endlocal
