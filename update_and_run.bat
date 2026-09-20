@echo off
cd /d "%~dp0"
echo =======================================
echo Checking for updates from GitHub...
echo =======================================
git pull --ff-only
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Notice: Fast-forward update was skipped or no internet connection.
    echo Starting app anyway...
)
echo Launching The Archiver...
start pythonw yt_archive_app.py
