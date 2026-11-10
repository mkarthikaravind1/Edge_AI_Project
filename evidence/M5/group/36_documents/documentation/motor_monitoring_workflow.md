# M5 Motor Condition Monitoring & Anomaly Detection Workflow

## 1. Physical Signal Processing Pipeline
1. **Sensor Ingestion**:
   - Arduino Uno samples MPU6050 (vibration), ACS712-05B (current), voltage divider, and MAX9814 (audio) at 100 Hz.
   - For M5 on Windows, authentic readings are ingested via high-fidelity replay of 1,175 real sensor telemetry records from `telemetry_history.db` or CSV datasets.
2. **Windowed Feature Extraction**:
   - Telemetry is buffered in a 10-sample sliding FIFO window.
   - Computes 21 statistical, electrical, and vibration features (`current_mean`, `accel_mag_rms`, `sound_p2p_max`, etc.).
3. **Anomaly Inference Engine**:
   - Evaluates hard physical safety boundaries (Immediate alarm if `current > 0.200A` or `voltage < 3.8V`).
   - Evaluates multivariate statistical Z-scores across electrical, vibration, and acoustic domains.
   - Computes normalized anomaly score `[0.0, 1.0]`.
4. **Alert Dispatch**:
   - If anomaly score crosses threshold `0.65`, a critical motor alert event is dispatched, logged in SQLite, and highlighted on the dashboard strip charts.

