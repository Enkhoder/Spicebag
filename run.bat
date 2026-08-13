@echo off
setlocal
cd /d %~dp0
set PYTHONPATH=.

if not exist .venv (
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

python spicebag/utils/dependencyCheck.py

if "%~1"=="" (
    python spicebag/app/cli.py
) else (
    python spicebag/app/cli.py %*
)

if %ERRORLEVEL% neq 0 pause
endlocal