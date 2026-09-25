@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo ========================================================
echo        The Archiver - Publish New Build
echo ========================================================
echo.

set HAS_CHANGES=
for /f "tokens=*" %%a in ('git status --porcelain') do set HAS_CHANGES=1

if not defined HAS_CHANGES (
    echo [Info] No changes detected. There is nothing to publish!
    pause
    exit /b
)

set /p msg="Enter a brief description for this update: "
if "%msg%"=="" set msg="Update build"

echo.
python auto_changelog.py --prompt "%msg%"
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Changelog / Version update failed or cancelled.
    pause
    exit /b
)

echo.
for /f "tokens=3 delims= " %%a in ('findstr /C:"APP_VERSION =" yt_archive_app.py') do set VER=%%~a

echo [Info] Staging changes for Git...
git add .
git commit -m "%msg% (v%VER%)"
git push origin main

echo.
echo [Info] Creating Git release tag v%VER%...
git tag v%VER% 2>nul
git push origin --tags

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   SUCCESS! v%VER% published to GitHub.
    echo ========================================================
) else (
    echo [Error] Failed to publish the build.
)
pause
