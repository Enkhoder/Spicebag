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

python src/utils/dependencyCheck.py

if "%~1"=="" (
    python src/app/cli.py
) else (
    python src/app/cli.py %*
)

if %ERRORLEVEL% neq 0 pause
endlocal
