@echo off
setlocal

cd /d "%~dp0.."

where py >nul 2>nul
if %errorlevel%==0 (
  py -3.11 --version >nul 2>nul
  if %errorlevel%==0 (
    set PYTHON_CMD=py -3.11
    goto setup
  )
  py -3.12 --version >nul 2>nul
  if %errorlevel%==0 (
    set PYTHON_CMD=py -3.12
    goto setup
  )
)

where python >nul 2>nul
if %errorlevel%==0 (
  set PYTHON_CMD=python
  goto setup
)

echo Python 3.11 or 3.12 is required. Install one, then rerun this script.
exit /b 1

:setup
%PYTHON_CMD% -m venv .venv-windows
".venv-windows\Scripts\python.exe" -m pip install --upgrade pip
".venv-windows\Scripts\python.exe" -m pip install -r backend\requirements.txt
".venv-windows\Scripts\python.exe" -m pip install -r backend\requirements-dev.txt

echo Windows environment ready: .venv-windows
echo Activate with: .venv-windows\Scripts\activate.bat
