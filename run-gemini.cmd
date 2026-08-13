@echo off
setlocal
cd /d "%~dp0"

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

".venv\Scripts\python.exe" -m hero_graph_lab --explore-provider gemini --explore-model gemini-2.5-flash %*
