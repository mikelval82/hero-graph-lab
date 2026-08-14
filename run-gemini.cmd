@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "APP_PORT=8765"
set "PREVIOUS_ARGUMENT="
for %%A in (%*) do (
    if /I "!PREVIOUS_ARGUMENT!"=="--port" set "APP_PORT=%%~A"
    set "PREVIOUS_ARGUMENT=%%~A"
)

if not exist ".venv\Scripts\python.exe" (
    echo Graph Lab virtual environment not found.
    echo Create it with: py -3.12 -m venv .venv
    exit /b 1
)

".venv\Scripts\python.exe" -c "import google.genai" >nul 2>&1
if errorlevel 1 (
    echo Gemini support is not installed in the Graph Lab environment.
    echo Install it with: .venv\Scripts\python.exe -m pip install -e ".[gemini]"
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$connection = Get-NetTCPConnection -State Listen -LocalPort %APP_PORT% -ErrorAction SilentlyContinue | Select-Object -First 1;" ^
    "if (-not $connection) { exit 0 };" ^
    "$process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $connection.OwningProcess);" ^
    "if ($process.CommandLine -notmatch '(?i)(-m\s+hero_graph_lab|hero-graph-lab)') { Write-Error ('Port %APP_PORT% is already used by ' + $process.Name); exit 1 };" ^
    "Write-Host ('Restarting Graph Lab process ' + $connection.OwningProcess + ' on port %APP_PORT%...');" ^
    "Stop-Process -Id $connection.OwningProcess -Force; Wait-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue"
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m hero_graph_lab --explore-provider gemini --explore-model gemini-2.5-flash %*
