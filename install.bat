@echo off
echo ========================================
echo    SQL ASSISTANT - ONE-TIME SETUP
echo ========================================
echo.

REM Check for Python 3.11 specifically
echo Checking for Python 3.11...
echo.

REM Try to find Python 3.11 using py launcher (Windows-specific)
py --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%V in ('py --version 2^>nul') do set "PY_VERSION=%%V"
    echo Found Python version: %PY_VERSION%
    
    REM Check if it's 3.11.x
    echo %PY_VERSION% | findstr /r "^3\.11\." >nul
    if not errorlevel 1 (
        set PYTHON_CMD=py
        goto :python_found
    )
    
    REM If not 3.11, check if we can specify version
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=py -3.11
        goto :python_found
    )
)

REM Try python 3.11 directly
python3.11 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python3.11
    goto :python_found
)

REM Try python command with version check
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%V in ('python --version 2^>nul') do set "PY_VERSION=%%V"
    echo %PY_VERSION% | findstr /r "^3\.11\." >nul
    if not errorlevel 1 (
        set PYTHON_CMD=python
        goto :python_found
    )
)

REM If we get here, Python 3.11 not found
echo [X] ERROR: Python 3.11 not found!
echo.
echo Python 3.11 is required for this application.
echo.
echo ========================================
echo    INSTALLING PYTHON 3.11
echo ========================================
echo.
echo Step 1: Downloading Python 3.11...
echo.
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python-3.11-installer.exe'"

if not exist "python-3.11-installer.exe" (
    echo [X] Failed to download Python installer
    echo.
    echo Please manually download from: https://www.python.org/downloads/release/python-3119/
    echo Look for "Windows installer (64-bit)"
    echo.
    echo IMPORTANT: During installation, CHECK "Add Python to PATH"
    pause
    exit /b 1
)

echo Step 2: Installing Python 3.11...
echo.
echo IMPORTANT: In the installer window:
echo 1. CHECK "Add Python 3.11 to PATH"
echo 2. Click "Install Now"
echo 3. Wait for installation to complete
echo 4. Close the installer when done
echo.
echo Starting installer...
start /wait python-3.11-installer.exe

REM Clean up installer
del python-3.11-installer.exe 2>nul

echo.
echo Step 3: Verifying installation...
echo.

REM Wait a moment for environment to update
timeout /t 5 /nobreak >nul

REM Check for Python 3.11
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.11
    goto :python_found
)

python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%V in ('python --version 2^>nul') do set "PY_VERSION=%%V"
    echo %PY_VERSION% | findstr /r "^3\.11\." >nul
    if not errorlevel 1 (
        set PYTHON_CMD=python
        goto :python_found
    )
)

echo [X] Python 3.11 installation may not be complete
echo.
echo Please try:
echo 1. Restart your computer
echo 2. Run this installer again
echo.
echo OR install Python 3.11 manually from:
echo https://www.python.org/downloads/release/python-3119/
echo.
pause
exit /b 1

:python_found
echo [OK] Python found: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo [1/5] Creating virtual environment...
%PYTHON_CMD% -m venv venv
if errorlevel 1 (
    echo [X] Failed to create virtual environment
    echo.
    echo Try running as Administrator
    echo Or check if Python installation is complete
    pause
    exit /b 1
)

echo [2/5] Activating environment...
call venv\Scripts\activate.bat

echo [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [4/5] Installing dependencies (this may take 2-3 minutes)...
echo     Please wait...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [X] Failed to install dependencies
    echo.
    echo This might be a network issue. Trying again with timeout...
    pip install --default-timeout=100 -r requirements.txt --quiet
    if errorlevel 1 (
        echo [X] Still failed. Check your internet connection.
        echo.
        echo You can try manually: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo [5/5] Creating folders...

if not exist "config" mkdir config
if not exist "schemas" mkdir schemas

echo.
echo ========================================
echo    INSTALLATION COMPLETE!
echo ========================================
echo.
echo ✅ Python environment ready
echo ✅ Dependencies installed
echo ✅ Folders created
echo.
echo ========================================
echo    REQUIRED BEFORE FIRST USE:
echo ========================================
echo.
echo 1. ⚠️ MUST UPLOAD FEW-SHOT EXAMPLES ⚠️
echo    - Create a JSON file with your database examples
echo    - Upload it through the app interface
echo.
echo 2. Install SQL Server ODBC Driver 17
echo    https://go.microsoft.com/fwlink/?linkid=2249006
echo.
echo 3. Install Ollama
echo    https://ollama.ai/download
echo    Command: ollama pull deepseek-coder:6.7b
echo.
echo ========================================
echo    EXAMPLE FEW-SHOT FILE FORMAT:
echo ========================================
echo Create examples\your_few_shot.json with:
echo {
echo   "few_shot_examples": [
echo     {
echo       "question": "Your question about YOUR database",
echo       "sql": "SELECT columns FROM your_tables;"
echo     }
echo   ]
echo }
echo.
echo ========================================
echo.
echo To start the application: Double-click start.bat
echo.
echo ⚠️ IMPORTANT: You MUST upload your own few-shot examples
echo    before using the application!
echo.
pause