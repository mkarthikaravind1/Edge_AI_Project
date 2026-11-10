# M5 Known Limitations & Technical Scope

## 1. Physical vs Replayed Data Stream Boundary
- **Vision Subsystem**: Can operate using live Windows DirectShow webcams or uploaded images. In environments without an attached webcam, it defaults to calibrated inspection test frames.
- **Motor Subsystem**: Physical servo motor telemetry acquisition was conducted on Arduino Uno and Raspberry Pi 5 during the M4 milestone. For M5 on Windows, sensor telemetry is replayed from the authentic M4 SQLite database (1,175 real sensor telemetry records) and CSV files. Disconnected physical sensors are never misrepresented as providing live readings.

## 2. Hardware Actuation
- Physical 3-LED stack actuation requires Raspberry Pi 5 RP1 GPIO pins. On Windows, the system executes an identical virtual actuator state machine with non-blocking timer threads and displays the state via the live HUD overlay and dashboard visual indicators.

## 3. Lighting Sensitivity
- Extreme low-light conditions (<50 Lux) can reduce glove detection confidence. The recommended inspection zone illumination is 350 – 500 Lux diffuse overhead lighting.

