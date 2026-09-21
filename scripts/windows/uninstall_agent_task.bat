@echo off
:: =============================================================================
:: InsiEDR Agent — Windows Task Scheduler Uninstaller
:: uninstall_agent_task.bat
::
:: PURPOSE
:: -------
:: Cleanly removes the InsiEDR_Agent Scheduled Task registered by
:: install_agent_task.bat.  Optionally clears the agent's local state and
:: queue directories.
::
:: USAGE
::   Double-click this file or run from any non-elevated shell.
::   A UAC prompt will appear (one time) if not already elevated.
::
:: =============================================================================

setlocal EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: CONFIGURATION — must match the values in install_agent_task.bat
:: ---------------------------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"

set "TASK_NAME=InsiEDR_Agent"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"

:: Set to 1 to also delete the local agent state and queue directories.
:: WARNING: This will erase any queued payloads that have not been sent yet.
set "CLEAN_STATE=0"

:: ---------------------------------------------------------------------------
:: STEP 1 — Privilege check
:: ---------------------------------------------------------------------------
echo.
echo [InsiEDR Uninstaller] Checking administrator privileges...
net session >nul 2>&1
if %errorlevel% == 0 goto :ADMIN_OK

echo [InsiEDR Uninstaller] Requesting administrator privileges (UAC prompt)...
powershell -NoProfile -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
exit /b 0

:ADMIN_OK
echo [InsiEDR Uninstaller] Running with administrator privileges.
echo.

:: ---------------------------------------------------------------------------
:: STEP 2 — Stop the running task (if active)
:: ---------------------------------------------------------------------------
echo [InsiEDR Uninstaller] Stopping task if currently running...
schtasks /End /TN "%TASK_NAME%" >nul 2>&1
echo [InsiEDR Uninstaller] Task stopped (or was not running).

:: ---------------------------------------------------------------------------
:: STEP 3 — Delete the scheduled task
:: ---------------------------------------------------------------------------
echo [InsiEDR Uninstaller] Removing scheduled task "%TASK_NAME%"...
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% neq 0 (
    echo [WARNING] Task "%TASK_NAME%" could not be deleted. It may not exist.
) else (
    echo [InsiEDR Uninstaller] Scheduled task removed successfully.
)

:: ---------------------------------------------------------------------------
:: STEP 4 — Optional: clean state and queue directories
:: ---------------------------------------------------------------------------
if "%CLEAN_STATE%"=="1" (
    echo.
    echo [InsiEDR Uninstaller] CLEAN_STATE=1 — removing agent state and queue...

    :: Default state dir: %PROGRAMDATA%\InsiEDR or %APPDATA%\InsiEDR
    set "STATE_DIR_PD=%PROGRAMDATA%\InsiEDR"
    set "STATE_DIR_AD=%APPDATA%\InsiEDR"

    if exist "!STATE_DIR_PD!" (
        echo [InsiEDR Uninstaller] Deleting: !STATE_DIR_PD!
        rmdir /s /q "!STATE_DIR_PD!"
    )
    if exist "!STATE_DIR_AD!" (
        echo [InsiEDR Uninstaller] Deleting: !STATE_DIR_AD!
        rmdir /s /q "!STATE_DIR_AD!"
    )

    echo [InsiEDR Uninstaller] State directories cleaned.
) else (
    echo.
    echo [InsiEDR Uninstaller] State and queue directories preserved.
    echo                       Set CLEAN_STATE=1 in this script to remove them.
)

:: ---------------------------------------------------------------------------
:: STEP 5 — Final report
:: ---------------------------------------------------------------------------
echo.
echo =========================================================================
echo   InsiEDR Agent Uninstallation Complete
echo =========================================================================
echo.
echo   Scheduled task "%TASK_NAME%" has been removed.
echo   The agent will no longer run in the background.
echo.
echo   To reinstall, run:  scripts\windows\install_agent_task.bat
echo.
echo =========================================================================
echo.
pause
endlocal
exit /b 0
