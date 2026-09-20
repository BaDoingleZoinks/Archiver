@echo off
cd /d "%~dp0"
echo ========================================================
echo        The Archiver - First-Time Push to GitHub
echo ========================================================
echo.
set /p GHUSER="Enter your GitHub username: "
if "%GHUSER%"=="" (
    echo [Error] Username cannot be empty.
    pause
    exit /b
)
echo.
echo Configuring remote origin for: %GHUSER%/Archiver...
git remote remove origin 2>nul
git remote add origin https://github.com/%GHUSER%/Archiver.git
echo.
echo Pushing code and tags to GitHub...
echo (A GitHub login window may appear to sign you in)
echo.
git push -u origin main --tags
echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   SUCCESS! Your project is now published on GitHub.
    echo ========================================================
) else (
    echo ========================================================
    echo   Push failed. Make sure you created the 'Archiver'
    echo   repository on GitHub first at https://github.com/new
    echo ========================================================
)
echo.
pause
