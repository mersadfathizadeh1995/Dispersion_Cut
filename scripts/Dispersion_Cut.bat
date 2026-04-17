@echo off
REM ═══════════════════════════════════════════════════════════════════════
REM   Dispersion Cut — launcher
REM   (auto-installed next to the venv by dc_cut\install.bat; do not edit
REM    this copy by hand — re-run install.bat to refresh it.)
REM ═══════════════════════════════════════════════════════════════════════

setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

set "VENV=%HERE%\.venv"
set "PYEXE=%VENV%\Scripts\python.exe"
set "PKG_ROOT=%HERE%"

if not exist "%PYEXE%" (
    echo.
    echo   [Dispersion Cut] Virtual environment not found at:
    echo     %VENV%
    echo.
    echo   Please run the installer first:
    echo     %HERE%\dc_cut\install.bat
    echo.
    pause
    exit /b 1
)

if not exist "%PKG_ROOT%\dc_cut\__init__.py" (
    echo.
    echo   [Dispersion Cut] Cannot locate the dc_cut package next to this
    echo   launcher.  Expected:
    echo     %PKG_ROOT%\dc_cut\__init__.py
    echo.
    pause
    exit /b 1
)

set "PYTHONPATH=%PKG_ROOT%;%PYTHONPATH%"

"%PYEXE%" -m dc_cut %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   [Dispersion Cut] Exited with code %RC%.
    pause
)

endlocal & exit /b %RC%
