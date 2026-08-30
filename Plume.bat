@echo off
REM ---------------------------------------------------------------------------
REM  Plume - French <-> English conversation helper
REM  Convenient source launcher. Double-click, or run from a terminal.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

REM Prefer the Windows py launcher; fall back to python on PATH.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 plume.py
) else (
    python plume.py
)

if %errorlevel% neq 0 (
    echo.
    echo Plume exited with an error. If you have not installed the requirement yet, run:
    echo     pip install -r requirements.txt
    echo.
    pause
)
endlocal
