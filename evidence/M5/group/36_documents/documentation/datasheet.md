# Integrated System Technical Datasheet & Specification

## 1. System Identity
- **Product Name**: Integrated Vision Inspection and Motor Condition Monitoring System
- **Milestone Code**: Edge AI Milestone 5 (M5)
- **Host Target**: Windows 10 / 11 (x64) Workstation / Industrial PC
- **Development Team**: Jaishanth Lenin (jaishanthlenin-123)

---

## 2. Technical Specifications

### A. Vision Inspection Subsystem (M3 Integration)
- **Model Architecture**: Ultralytics YOLOv8 Nano (`best.pt`)
- **Trained Parameters**: ~3.0 Million Parameters
- **Inference Size**: 640 x 640 pixels
- **Classes**:
  - `0`: `gloves` (Safety gloves)
  - `1`: `head` (Bare head / unhelmeted worker violation)
  - `2`: `helmet` (Safety hardhat)
- **Inference Hardware**: Native Windows CPU (DirectShow / PyTorch)
- **Inference Latency**: 130 – 190 ms per frame on standard CPU
- **Throughput**: ~25 – 30 FPS acquisition; ~6 – 8 FPS continuous full inference
- **Secondary Filters**: Multi-spectrum skin colorimetry (HSV, YCrCb, RGB) + Laplacian edge texture analysis

### B. Motor Condition Monitoring Subsystem (M4 Integration)
- **Actuator Monitored**: SG90 Micro Servo Motor (5V DC)
- **Sensor Array**:
  - MPU6050 6-DOF IMU (Accelerometer & Gyroscope)
  - ACS712-05B Hall-Effect Current Sensor (185 mV/A sensitivity)
  - 0–25V Resistive Voltage Divider (5:1 ratio)
  - MAX9814 Electret Microphone with Auto-Gain Control (AGC)
- **Sampling Frequency**: 100 Hz (10 ms ADC interval on Arduino Uno)
- **Feature Pipeline**: 10-sample sliding window computing 21 statistical, electrical, and vibration features
- **ML Anomaly Engine**: Multivariate statistical regularized Z-score model (`anomaly_model_latest.pkl`)
- **Safety Limits**:
  - Normal Voltage Band: 4.50 V – 5.50 V
  - Overcurrent Alarm Threshold: > 0.200 A (200 mA)
  - Acoustic Shock Threshold: Sound P2P > 600

### C. Backend & Dashboard Layer
- **Backend Framework**: FastAPI (ASGI) + Uvicorn
- **Transport Protocols**: HTTP/1.1 REST, WebSockets, MJPEG Multipart
- **Database Engine**: Embedded SQLite 3 with WAL Journaling
- **UI Architecture**: Single Page Application (HTML5, CSS3, ES6 JavaScript, Chart.js)
- **Network Port**: Default `8000` (Localhost: `127.0.0.1:8000`)
- **Security**: No committed credentials, parameterized SQLite queries, input file type validation

