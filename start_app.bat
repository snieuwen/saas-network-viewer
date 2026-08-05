@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "CODEX_RUNTIME=C:\Users\Sandor Nieuwenhuijs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python"
set "CODEX_PYTHON=%CODEX_RUNTIME%\python.exe"
if exist "%CODEX_PYTHON%" (
  set "TCL_LIBRARY=%CODEX_RUNTIME%\tcl\tcl8.6"
  set "TK_LIBRARY=%CODEX_RUNTIME%\tcl\tk8.6"
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
      goto :exe_fallback
    )
  )
)

".venv\Scripts\python.exe" -c "import pandas, openpyxl, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing the required components. This is only needed once...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :exe_fallback
)

".venv\Scripts\python.exe" desktop_app.py
exit /b %errorlevel%

:exe_fallback
if exist "saas-network-viewer.exe" (
  echo Python is unavailable. Starting the packaged fallback, which may not include the latest source changes.
  start "" "saas-network-viewer.exe"
  exit /b 0
)

echo.
echo Python 3.11 or newer and the required components were not found.
echo Install Python from https://www.python.org/downloads/ and try again.
pause
exit /b 1
