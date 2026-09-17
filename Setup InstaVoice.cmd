@echo off
rem First-time setup: create .venv and install pinned requirements.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto :install
python -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" >nul 2>&1
if errorlevel 1 goto :launcher
python -m venv .venv || goto :error
goto :install
:launcher
py -3.11 -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" >nul 2>&1
if errorlevel 1 goto :missing_python
py -3.11 -m venv .venv || goto :error
:install
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" || goto :wrong_venv
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
".venv\Scripts\python.exe" -m unittest discover -v || goto :error
echo.
echo Setup complete. Run "Run InstaVoice.cmd" to start the studio.
pause
exit /b 0
:missing_python
echo Python 3.11 not found. Install Python 3.11 as python or via the Windows Python launcher.
goto :error
:wrong_venv
echo Existing .venv is not Python 3.11. Rename it and run setup again.
goto :error
:error
echo.
echo Setup failed. Check the messages above.
pause
exit /b 1
