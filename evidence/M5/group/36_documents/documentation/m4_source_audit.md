# M4 Motor Condition Monitoring Source Audit Report & Integration Analysis

## 1. Executive Summary
- **Source Project**: Edge AI Milestone 4 (M4) — SG90 Servo Motor Condition Monitoring and Anomaly Detection System
- **Original Hardware Architecture**:
  - Arduino Uno (10-bit ADC, 100 Hz high-speed sampling)
  - Raspberry Pi 5 (Edge Gateway & ML inference node)
  - SG90 Micro Servo (Actuator under test)
  - MPU6050 6-DOF IMU (Accelerometer & Gyroscope)
  - ACS712-05B Hall-effect Current Sensor
  - 0–25V Resistive Voltage Divider Sensor
  - MAX9814 Electret Microphone with AGC
  - *(Note: DHT11 temperature/humidity sensor is strictly NOT used in this architecture)*
- **Anomaly Detection Model**:
  - Serialized model: `saved_models/anomaly_model_latest.pkl` and `anomaly_model_latest.json`
  - Multivariate statistical Z-score engine with regularized noise floors across Electrical, Vibration, and Acoustic domains.
  - Normalized continuous anomaly score:
    - `0.00 – 0.40`: **NORMAL OPERATION** (Green)
    - `0.40 – 0.65`: **ELEVATED / TRANSIENT** (Amber)
    - `0.65 – 1.00`: **CRITICAL ANOMALY** (Red alert triggered)
- **Feature Extraction Pipeline**:
  - 10-sample sliding window computing 21 statistical, electrical, and vibration features:
    1. Electrical (Current): `current_mean`, `current_peak`, `current_std`, `current_rms`
    2. Electrical (Voltage): `voltage_mean`, `voltage_std`, `voltage_min`, `voltage_drop`
    3. Vibration (IMU): `accel_mag_mean`, `accel_mag_std`, `accel_mag_rms`, `accel_mag_p2p`, `accel_mag_crest_factor`, `accel_x_std`, `accel_y_std`, `accel_z_std`
    4. Acoustic: `sound_p2p_mean`, `sound_p2p_max`, `sound_rms_mean`, `sound_energy`
    5. Kinematic: `angle_motion_rate`
- **Telemetry History Database**:
  - SQLite database: `database/telemetry_history.db` containing **1,175 real sensor telemetry records** and **463 anomaly alert records**.

---

## 2. Windows Compatibility & Adapter Strategy
1. **Model Reuse**: `anomaly_model_latest.pkl` is loaded directly via Python `pickle` and `AnomalyDetectionModel` class.
2. **Data Ingestion Channels**:
   - `RECORDED_DATA` / `CSV_REPLAY`: High-fidelity replay of authentic physical telemetry from `telemetry_history.db` and raw M4 CSVs (`servo_normal_20261106_143433.csv`, `servo_telemetry_20261106_133524.csv`).
   - `LIVE_MQTT`: Direct client subscription to `motor/servo01/#` topics with TLS and authentication if an external broker is configured.
   - `SIMULATED`: Calibrated synthetic signal generator strictly reserved for testing fault injection when hardware feeds are detached.
3. **Replay Controller**:
   - Dedicated threaded replay engine supporting play, pause, resume, reset, variable playback speed (0.5x, 1x, 2x, 5x), and timestamp synchronization.
4. **Authenticity Guarantee**:
   - Each data point transmitted to the M5 backend explicitly carries its provenance (`source_mode`), preventing synthetic or replayed data from being misrepresented as live sensor readings.

