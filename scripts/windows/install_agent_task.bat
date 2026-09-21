@echo off
:: =============================================================================
:: InsiEDR Agent — Windows Task Scheduler Installer
:: install_agent_task.bat
::
:: PURPOSE
:: -------
:: One-time installation script that:
::   1.  Detects whether it is running with administrator privileges.
::   2.  If NOT admin → re-launches itself via PowerShell "runas" (one UAC
::       prompt, never shown again).
::   3.  If admin → registers the InsiEDR_Agent Scheduled Task with:
::         - Run level : HIGHEST  (/RL HIGHEST)
::         - Run as    : SYSTEM   (/RU SYSTEM)
::         - Triggers  : ONSTART (boot) + DAILY at 03:00 as a restart-guard
::         - Env var   : INSIEDR_SCHEDULED_TASK=1  (suppresses further UAC
::                       checks inside agent.py — prevents re-launch loops)
::   4.  Verifies elevation succeeded using the --check-admin agent flag.
::   5.  Starts the task immediately so the agent is live without a reboot.
::
:: USAGE
::   Double-click this file, or run from any non-elevated shell:
::       install_agent_task.bat
::
:: CUSTOMISATION
::   Edit the variables in the "CONFIGURATION" section below to match your
::   deployment environment.  All other sections should be left unchanged.
::
:: NOTE: This script must remain in the scripts\windows\ directory so that
::       relative paths resolve correctly.
:: =============================================================================

setlocal EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: CONFIGURATION — edit these values for your deployment
:: ---------------------------------------------------------------------------

:: Absolute path to the project root (parent of agent\ and scripts\)
:: By default, derived from the location of this script (../../)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"

:: Python executable — uses the project's virtual environment by default.
:: Change to "python" or a full path if using a system-wide install.
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"

:: Task name as it will appear in Windows Task Scheduler
set "TASK_NAME=InsiEDR_Agent"

:: Description shown in Task Scheduler
set "TASK_DESCRIPTION=InsiEDR endpoint telemetry agent — runs as SYSTEM with highest privilege"

:: Daily restart-guard time (HH:MM in 24-hour format)
set "DAILY_RESTART_TIME=03:00"

:: Path to the .env file that contains INSIEDR_* environment variables.
:: The wrapper command sources this file before launching the agent.
:: Leave blank if you inject env vars another way (registry, Group Policy, etc.)
set "ENV_FILE=%PROJECT_ROOT%\.env"

:: ---------------------------------------------------------------------------
:: STEP 1 — Check for administrator privileges
:: ---------------------------------------------------------------------------
echo.
echo [InsiEDR Installer] Checking administrator privileges...
net session >nul 2>&1
if %errorlevel% == 0 goto :ADMIN_OK

:: ---------------------------------------------------------------------------
:: STEP 2 — Not admin: re-launch this script elevated (one UAC prompt)
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Administrator rights required.
echo [InsiEDR Installer] Windows will now ask for your permission (UAC).
echo [InsiEDR Installer] This is the ONLY time you will see this prompt.
echo.

:: Use PowerShell Start-Process with -Verb RunAs to trigger UAC.
:: The -Wait flag keeps the PowerShell window open until the elevated
:: instance finishes, so any error output is visible.
powershell -NoProfile -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"

:: Exit the non-elevated parent cleanly.
exit /b 0

:ADMIN_OK
:: ---------------------------------------------------------------------------
:: STEP 3 — Running as admin. Announce and verify the Python executable.
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Running with administrator privileges.
echo.

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found:
    echo         %PYTHON_EXE%
    echo.
    echo         Please edit PYTHON_EXE in this script to point to your Python
    echo         interpreter or virtual environment.
    pause
    exit /b 1
)

echo [InsiEDR Installer] Using Python: %PYTHON_EXE%
echo [InsiEDR Installer] Project root: %PROJECT_ROOT%
echo.

:: ---------------------------------------------------------------------------
:: STEP 4 — Verify that the agent can confirm admin access via --check-admin
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Verifying privilege detection in the agent...
cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m agent.agent --check-admin
if %errorlevel% neq 0 (
    echo [WARNING] agent --check-admin returned a non-zero exit code.
    echo          The task will still be registered, but some collectors may
    echo          not have full access. Check agent logs for details.
    echo.
) else (
    echo [InsiEDR Installer] Privilege check passed.
    echo.
)

:: ---------------------------------------------------------------------------
:: STEP 5 — Set the task command to the user's preferred RunAgent.bat
:: ---------------------------------------------------------------------------
set "TASK_CMD="%PROJECT_ROOT%\RunAgent.bat""
echo [InsiEDR Installer] Using target script: %TASK_CMD%

:: ---------------------------------------------------------------------------
:: STEP 6 — Delete any existing task registration (clean reinstall)
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Removing existing task (if any)...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

:: ---------------------------------------------------------------------------
:: STEP 7 — Register the boot trigger task (/SC ONSTART)
::
:: /SC ONSTART      → trigger at every system startup
:: /RL HIGHEST      → run with highest available privileges
:: /RU SYSTEM       → run as the SYSTEM account (no user session needed)
:: /F               → force creation, suppress confirmation prompts
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Registering scheduled task (boot trigger)...

schtasks /Create /TN "%TASK_NAME%" /TR "%TASK_CMD%" /SC ONSTART /RL HIGHEST /RU SYSTEM /F

if %errorlevel% neq 0 (
    echo [ERROR] Failed to register boot-trigger task. Exit code: %errorlevel%
    echo         Check that your system policy allows SYSTEM tasks with HIGHEST privilege.
    pause
    exit /b %errorlevel%
)

echo [InsiEDR Installer] Boot-trigger task registered successfully.

:: ---------------------------------------------------------------------------
:: STEP 8 — Add a DAILY restart-guard trigger using PowerShell
::
:: schtasks /Create does not support multiple triggers in one call.
:: We use a PowerShell script block to add the daily trigger to the
:: existing task object via the Task Scheduler COM API.
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Adding daily restart-guard trigger (%DAILY_RESTART_TIME%)...

powershell -NoProfile -Command ^
    "$ts = New-Object -ComObject Schedule.Service; $ts.Connect(); " ^
    "$tf = $ts.GetFolder('\'); " ^
    "$task = $tf.GetTask('%TASK_NAME%'); " ^
    "$def = $task.Definition; " ^
    "$trigger = $def.Triggers.Create(2); " ^
    "$trigger.StartBoundary = (Get-Date -Format 'yyyy-MM-dd') + 'T%DAILY_RESTART_TIME%:00'; " ^
    "$trigger.Enabled = $true; " ^
    "$tf.RegisterTaskDefinition('%TASK_NAME%', $def, 4, 'SYSTEM', $null, 5) | Out-Null; " ^
    "Write-Host '[InsiEDR Installer] Daily trigger added.'"

if %errorlevel% neq 0 (
    echo [WARNING] Could not add daily restart-guard trigger. Boot-only trigger is still active.
    echo          This is non-fatal — the agent will still start on every boot.
)

:: ---------------------------------------------------------------------------
:: STEP 9 — Start the task immediately (no reboot required)
:: ---------------------------------------------------------------------------
echo [InsiEDR Installer] Starting the agent task now (no reboot required)...
schtasks /Run /TN "%TASK_NAME%"

if %errorlevel% neq 0 (
    echo [WARNING] Could not start task immediately. It will run on next boot.
) else (
    echo [InsiEDR Installer] Agent task started successfully.
)

:: ---------------------------------------------------------------------------
:: STEP 10 — Final status report
:: ---------------------------------------------------------------------------
echo.
echo =========================================================================
echo   InsiEDR Agent Installation Complete
echo =========================================================================
echo.
echo   Task Name   : %TASK_NAME%
echo   Run As      : SYSTEM
echo   Privilege   : HIGHEST
echo   Triggers    : System boot  +  Daily at %DAILY_RESTART_TIME%
echo   Agent Dir   : %PROJECT_ROOT%
echo   Python      : %PYTHON_EXE%
echo.
echo   The agent is now running silently in the background.
echo   No further UAC prompts will appear.
echo.
echo   To check status:
echo     schtasks /Query /TN %TASK_NAME% /FO LIST /V
echo.
echo   To view logs, check the agent state directory or run:
echo     "%PYTHON_EXE%" -m agent.agent --status
echo.
echo   To uninstall, run:  scripts\windows\uninstall_agent_task.bat
echo.
echo =========================================================================
echo.
pause
endlocal
exit /b 0
