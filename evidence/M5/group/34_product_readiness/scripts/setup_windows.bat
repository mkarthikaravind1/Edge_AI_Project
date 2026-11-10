@echo off
REM ============================================================================
REM M5 Integrated System: Windows Environment Setup
REM ============================================================================
echo =====================================================================
echo   SETTING UP M5 INTEGRATED SYSTEM (WINDOWS PC)
echo =====================================================================

python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.11+.
    pause
    exit /b 1
)

echo.
echo [1/3] Installing / Verifying Python dependencies from requirements.txt...
pip install -r requirements.txt

echo.
echo [2/3] Initializing environment configuration...
if not exist .env (
    copy .env.example .env
    echo [INFO] Created .env from .env.example.
)

echo.
echo [3/3] Preparing inspection station datasets...
python inspection_station\inspection_engine\prepare_datasets.py

echo.
echo =====================================================================
echo   M5 SETUP COMPLETE!
echo   To launch the complete application, execute: run_m5.bat
echo =====================================================================
pause

