@echo off
setlocal
cd /d %~dp0

if not exist .venv (
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

python scripts/dependencyCheck.py

python -m spicebag %*

if %ERRORLEVEL% neq 0 pause
endlocal