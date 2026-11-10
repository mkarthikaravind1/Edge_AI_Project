# M5 Unified Dashboard User Guide

## 1. Dashboard Navigation
The dashboard sidebar provides instant access to 8 operational views:
- **Overview**: Executive summary, 3 Headline KPIs, latest vision & motor cards, active alerts.
- **Vision Inspection**: Live MJPEG video player, mode selector (Webcam, Upload, Video), bounding boxes, 3-LED actuator stack emulator, single-shot test upload.
- **Motor Monitoring**: Live multi-channel oscilloscope strip charts (Current, Vibration, Audio, Anomaly Score), replay controls toolbar (Play, Pause, Reset, Speeds 0.5x to 5.0x), and fault injection selector.
- **Inspection History**: Paginated, searchable log of all quality decisions with ground-truth verification and CSV export.
- **Motor History**: Historical high-frequency telemetry records with CSV export.
- **Alerts Center**: Dedicated incident center with severity badges (INFO, WARNING, CRITICAL) and acknowledgment actions.
- **Assessment & Rig**: Automated runners for Station 31 (20-sample pass/fail), Station 35 (50-sample headline metric), and Station 32 (10-minute continuous full chain).
- **System Health**: Hardware connectivity status, backend uptime, and real-time scrolling console logs.

---

## 2. Interactive Features
### 3-LED Actuator Stack Visualizer
Located beneath the live vision stream:
- **Green LED**: Energizes when Helmet ONLY is detected.
- **Yellow LED**: Energizes when Gloves ONLY are detected.
- **Red LED (Blinking)**: Pulses at 2 Hz when BOTH Helmet AND Gloves are verified (compliant state).
- **All OFF**: De-energized when inspection zone is clear or unequipped.

### Motor Telemetry Replay & Fault Injection
Located on the Motor Monitoring tab:
- **Play / Pause / Reset**: Controls continuous replay of authentic recorded telemetry.
- **Speed Multiplier**: Adjusts replay pacing between half-speed (0.5x) and high-speed (5.0x).
- **Fault Injector**: Select `CURRENT_SURGE` to simulate stall overcurrent (>200mA) or `BEARING_GRIND` to simulate severe mechanical friction, immediately demonstrating how the ML anomaly model flags alarms.

