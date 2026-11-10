@echo off
REM ============================================================================
REM M5 Integrated System: Graceful Process Shutdown
REM ============================================================================
echo [INFO] Stopping all running M5 Python uvicorn instances...
taskkill /F /IM uvicorn.exe /T 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [INFO] Terminating PID %%a on port 8000...
    taskkill /F /PID %%a 2>nul
)
echo [INFO] M5 system shutdown complete.
pause

