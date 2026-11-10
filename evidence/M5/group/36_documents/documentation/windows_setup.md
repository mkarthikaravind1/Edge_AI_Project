# Windows Installation & Execution Guide

## 1. Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Version 3.11.x (Installed and added to Windows PATH)
- **Git**: Installed for version control operations
- **Webcam**: Standard USB Webcam or integrated laptop camera (Index 0). *(Note: If no webcam is attached, the system automatically runs with sample images or recorded video).*

---

## 2. Automated Turn-Key Setup
From the repository root on Windows:
```cmd
setup_windows.bat
```
This batch script automatically:
1. Validates the Python installation.
2. Installs required packages from `requirements.txt`.
3. Creates `.env` configuration file from `.env.example`.
4. Compiles the standardized 20-sample inspection station dataset.

---

## 3. Launching the M5 Application
Double-click or run:
```cmd
run_m5.bat
```
This launches the FastAPI backend and automatically opens the user's default web browser to:
```
http://127.0.0.1:8000
```
API documentation (Swagger UI) is accessible at:
```
http://127.0.0.1:8000/docs
```

---

## 4. Shutting Down the Application
To stop all M5 services gracefully:
```cmd
stop_m5.bat
```
This terminates all background worker threads and frees port 8000.

