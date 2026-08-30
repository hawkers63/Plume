@echo off
rem Plume - GitHub repository update script

cd /d "C:\Plume"

set "COMMIT_MSG=%~1"

rem If no commit message was passed as a parameter, prompt for one
if "%COMMIT_MSG%"=="" (
    set /p "COMMIT_MSG=Enter commit message: "
)

rem Abort if no commit message was entered
if "%COMMIT_MSG%"=="" (
    echo No commit message provided. Aborting update.
    pause
    exit /b 1
)

echo Staging files...
git add Plume.py README.md scriptorium_config.example.json

echo Committing changes...
git commit -m "%COMMIT_MSG%"

echo Pushing to GitHub...
git push

echo.
echo Repository update complete.
pause
