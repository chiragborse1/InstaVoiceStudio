@echo off
rem Import your own session via a hidden local prompt, using the project's .venv.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run "Setup InstaVoice.cmd" first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" ig_session_import.py
set "result=%ERRORLEVEL%"
pause
exit /b %result%
