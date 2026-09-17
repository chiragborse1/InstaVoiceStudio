@echo off
rem Launch InstaVoice Studio from the local .venv created by Setup InstaVoice.cmd.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run "Setup InstaVoice.cmd" first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" desktop.py %*
exit /b %ERRORLEVEL%
