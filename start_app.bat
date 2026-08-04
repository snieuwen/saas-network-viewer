@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if exist "saas-network-viewer.exe" (
  start "" "saas-network-viewer.exe"
  exit /b 0
)

set "CODEX_PYTHON=C:\Users\Sandor Nieuwenhuijs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" desktop_app.py
  exit /b %errorlevel%
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the local Python environment...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>nul
    if not errorlevel 1 (
      python -m venv .venv
    ) else (
      echo Python was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
      pause
      exit /b 1
    )
  )
)

".venv\Scripts\python.exe" -c "import pandas, openpyxl, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing the required components. This is only needed once...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :install_error
)

".venv\Scripts\python.exe" desktop_app.py
exit /b %errorlevel%

:install_error
echo.
echo Installation failed. Check your internet connection or contact your IT administrator.
pause
exit /b 1
