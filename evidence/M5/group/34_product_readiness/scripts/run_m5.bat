@echo off
REM ============================================================================
REM M5 Integrated System: Windows Launcher
REM Starts FastAPI Backend, MJPEG Vision Stream, Motor Replay, and Live Dashboard
REM ============================================================================
setlocal enabledelayedexpansion
title M5 Integrated Vision & Motor Monitoring System

echo =====================================================================
echo   LAUNCHING M5 INTEGRATED SYSTEM (WINDOWS PC)
echo =====================================================================
echo [INFO] Host: 127.0.0.1
echo [INFO] Port: 8000
echo [INFO] Dashboard URL: http://127.0.0.1:8000
echo [INFO] API Documentation: http://127.0.0.1:8000/docs
echo =====================================================================
echo.

set PYTHONPATH=.

REM Open browser after brief delay
start "" http://127.0.0.1:8000

REM Launch FastAPI uvicorn server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --log-level info
pause

