@echo off
title SQL Assistant
echo ========================================
echo       STARTING SQL ASSISTANT
echo ========================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [X] Virtual environment not found!
    echo.
    echo Please run install.bat first
    echo.
    pause
    exit /b 1
)

REM Check if Ollama is running
echo Checking Ollama connection...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] WARNING: Cannot connect to Ollama
    echo     Make sure Ollama is running
    echo     You can start it from the system tray
    echo.
    timeout /t 3 >nul
)

echo Activating environment...
call venv\Scripts\activate.bat

echo Starting application...
echo.
echo ========================================
echo  The app will open in your browser
echo  Close this window to stop the app
echo ========================================
echo.

call venv\Scripts\activate.bat   ← Uses YOUR specific Python
python app.py                    ← With YOUR specific packages

REM If python crashes, keep window open
if errorlevel 1 (
    echo.
    echo [X] Application closed with errors
    echo.
    pause
)
```

---

