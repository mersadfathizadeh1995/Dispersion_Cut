@echo off
REM ═══════════════════════════════════════════════════════════════════════
REM   DC_Cut / Dispersion Cut — Windows installer
REM   ---------------------------------------------------------------------
REM   1. Detects (or installs) Python 3.10+ from winget / python.org.
REM   2. Creates a virtual environment in the repo PARENT folder (.venv).
REM   3. Installs project dependencies from requirements.txt.
REM   4. Writes a Dispersion_Cut.bat launcher next to the venv.
REM   5. Runs an import smoke-test to prove the app can start.
REM
REM   Run by double-clicking this file, or from a shell:
REM     install.bat
REM ═══════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion

REM ── Resolve paths (robust against trailing backslash / spaces) ─────────
set "DCCUT_DIR=%~dp0"
if "%DCCUT_DIR:~-1%"=="\" set "DCCUT_DIR=%DCCUT_DIR:~0,-1%"

for %%I in ("%DCCUT_DIR%\..") do set "PARENT_DIR=%%~fI"

set "VENV_DIR=%PARENT_DIR%\.venv"
set "LAUNCHER=%PARENT_DIR%\Dispersion_Cut.bat"
set "TEMPLATE=%DCCUT_DIR%\scripts\Dispersion_Cut.bat"
set "REQS=%DCCUT_DIR%\requirements.txt"

echo.
echo =========================================================================
echo    DC_Cut / Dispersion Cut  --  Installer
echo =========================================================================
echo   dc_cut folder   : %DCCUT_DIR%
echo   parent folder   : %PARENT_DIR%
echo   venv location   : %VENV_DIR%
echo   launcher target : %LAUNCHER%
echo =========================================================================
echo.

if not exist "%REQS%" (
    echo   ERROR: requirements.txt not found at:
    echo     %REQS%
    pause
    exit /b 1
)
if not exist "%TEMPLATE%" (
    echo   ERROR: launcher template not found at:
    echo     %TEMPLATE%
    pause
    exit /b 1
)

REM ── 1. Find Python (prefer py launcher, fall back to 'python') ─────────
set "PY_CMD="
py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PY_CMD=py -3"
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "PY_CMD=python"
)

if "!PY_CMD!"=="" (
    echo   [1/5] No Python installation detected on PATH.
    echo         Attempting to install Python 3.11 ...
    call :install_python
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo   ERROR: Could not install Python automatically.
        echo   Please install Python 3.10+ from https://www.python.org/downloads/
        echo   and re-run this script.
        pause
        exit /b 1
    )
    REM Re-detect after install (PATH may have been refreshed for new shells
    REM but not this one, so probe both 'py' and likely install folders).
    py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
    if "!PY_CMD!"=="" (
        python --version >nul 2>&1 && set "PY_CMD=python"
    )
    if "!PY_CMD!"=="" (
        for %%P in (
            "%LocalAppData%\Programs\Python\Python312\python.exe"
            "%LocalAppData%\Programs\Python\Python311\python.exe"
            "%LocalAppData%\Programs\Python\Python310\python.exe"
            "%ProgramFiles%\Python312\python.exe"
            "%ProgramFiles%\Python311\python.exe"
            "%ProgramFiles%\Python310\python.exe"
        ) do (
            if exist "%%~P" (
                set "PY_CMD=%%~P"
                goto :py_found
            )
        )
    )
    :py_found
    if "!PY_CMD!"=="" (
        echo   ERROR: Python was installed but is not on PATH.
        echo   Please close and re-open this terminal, then run install.bat again.
        pause
        exit /b 1
    )
) else (
    echo   [1/5] Found Python on PATH.
)

for /f "delims=" %%V in ('!PY_CMD! --version 2^>^&1') do set "PY_VERSION=%%V"
echo         -^> !PY_CMD!  ^(!PY_VERSION!^)
echo.

REM ── 2. Create virtual environment in the parent folder ─────────────────
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo   [2/5] Reusing existing virtualenv at %VENV_DIR%.
) else (
    echo   [2/5] Creating virtualenv at %VENV_DIR% ...
    !PY_CMD! -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo   ERROR: 'python -m venv' failed.
        pause
        exit /b 1
    )
)
set "VPY=%VENV_DIR%\Scripts\python.exe"
echo.

REM ── 3. Install / update dependencies ───────────────────────────────────
echo   [3/5] Upgrading pip, setuptools, wheel ...
"%VPY%" -m pip install --upgrade pip setuptools wheel
if !ERRORLEVEL! NEQ 0 (
    echo   WARNING: pip upgrade failed ^(continuing with existing versions^).
)

echo.
echo   [3/5] Installing dependencies from requirements.txt ...
"%VPY%" -m pip install -r "%REQS%"
if !ERRORLEVEL! NEQ 0 (
    echo   ERROR: dependency install failed.
    pause
    exit /b 1
)
echo.

REM ── 4. Smoke test: make sure the app imports cleanly ───────────────────
echo   [4/5] Smoke test: importing the dc_cut package ...
"%VPY%" -c "import sys; sys.path.insert(0, r'%PARENT_DIR%'); import dc_cut; from dc_cut.gui.app import main; print('   -> dc_cut OK at', dc_cut.__file__)"
if !ERRORLEVEL! NEQ 0 (
    echo   ERROR: 'import dc_cut' failed -- the app will NOT launch yet.
    echo   See the traceback above, fix the environment, then re-run install.bat.
    pause
    exit /b 1
)
echo.

REM ── 5. Copy the launcher into the parent folder ────────────────────────
echo   [5/5] Installing launcher at %LAUNCHER% ...
copy /Y "%TEMPLATE%" "%LAUNCHER%" >nul
if !ERRORLEVEL! NEQ 0 (
    echo   ERROR: Could not write launcher to %LAUNCHER%.
    pause
    exit /b 1
)
echo.

echo =========================================================================
echo    Installation complete.
echo =========================================================================
echo   Launch Dispersion Cut by double-clicking:
echo     %LAUNCHER%
echo   or from a shell:
echo     "%LAUNCHER%"
echo =========================================================================
echo.

pause
endlocal
exit /b 0


REM ═══════════════════════════════════════════════════════════════════════
REM   Subroutine: install Python 3.11 automatically.
REM     - First tries winget (available on Win10 1709+ / Win11).
REM     - Falls back to downloading the official python.org installer
REM       via PowerShell and running it silently (user-scope, PATH added).
REM ═══════════════════════════════════════════════════════════════════════
:install_python
where winget >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo         Trying 'winget install Python.Python.3.11' ...
    winget install --id Python.Python.3.11 -e --source winget ^
        --accept-source-agreements --accept-package-agreements --silent
    if !ERRORLEVEL! EQU 0 exit /b 0
    echo         winget install returned an error, falling back to python.org ...
)

set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

echo         Downloading Python 3.11.9 installer ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -UseBasicParsing -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%'; exit 0 } catch { Write-Error $_; exit 1 }"
if not exist "%PY_INSTALLER%" exit /b 1

echo         Running silent install ^(user scope, PATH added^) ...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1
set "_rc=!ERRORLEVEL!"
del "%PY_INSTALLER%" >nul 2>&1
if !_rc! NEQ 0 exit /b 1
exit /b 0
