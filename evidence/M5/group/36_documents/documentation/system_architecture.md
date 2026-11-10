# M5 System Architecture: Integrated Vision Inspection & Motor Monitoring

## 1. High-Level Architectural Diagram

```mermaid
flowchart TD
    subgraph SENSORS_INPUTS ["Input Sources (Windows PC)"]
        CAM["Webcam (OpenCV / DirectShow)"]
        IMG["Image Upload / Static Test Rig"]
        VID["Recorded Video Test Stream"]
        REC_DB["Recorded Telemetry DB (1,175 Samples)"]
        REC_CSV["M4 Datasets / Raw CSVs"]
        MQTT_IN["Live MQTT Broker (Optional)"]
    end

    subgraph M3_VISION ["M3 Vision Inspection Subsystem"]
        YOLO["YOLOv8 Nano (best.pt)<br/>Classes: 0:gloves, 1:head, 2:helmet"]
        SKIN["Skin Colorimetry & Texture Analysis<br/>(Bare Hand vs Glove)"]
        LED_EMU["3-LED Logic Actuator Emulator<br/>(Green/Yellow/Red Blinking)"]
        INSP_DEC["Inspection Policy Engine<br/>(PASS / FAIL Evaluator)"]
    end

    subgraph M4_MOTOR ["M4 Motor Condition Monitoring Subsystem"]
        REPLAY_CTRL["Telemetry Replay Engine<br/>(Play/Pause/Rate Control)"]
        FEAT_ENG["Windowed Feature Extractor<br/>(21 Statistical Features)"]
        ANOM_MOD["Multivariate Anomaly Model<br/>(anomaly_model_latest.pkl)"]
        FAULT_INJ["Controlled Fault Injector<br/>(Current Surge / Grinding)"]
    end

    subgraph INTEGRATION_LAYER ["M5 Integration Layer"]
        VIS_ADAPT["Windows Vision Adapter"]
        MOT_ADAPT["Windows Motor Adapter"]
        EVT_BUS["Unified Event Manager & Normalizer"]
        SYS_MGR["System Health & Lifecycle Manager"]
    end

    subgraph BACKEND ["M5 FastAPI Backend"]
        REST_API["REST Endpoints<br/>(/api/status, /api/kpis, /api/export)"]
        WS_STREAM["WebSocket Telemetry Streamer<br/>(/ws/telemetry)"]
        MJPEG_FEED["MJPEG Video Server<br/>(/api/vision/stream)"]
        SQLITE_DB["M5 SQLite Unified Database<br/>(Inspections, Telemetry, Alerts)"]
    end

    subgraph DASHBOARD ["Unified Industrial Dashboard (Port 8000)"]
        OVERVIEW["1. System Overview & Headline KPIs"]
        LIVE_VISION["2. Vision Inspection & Actuator View"]
        LIVE_MOTOR["3. Motor Condition & Multi-Oscilloscope"]
        INSP_HIST["4. Inspection History & CSV Export"]
        MOT_HIST["5. Motor History & CSV Export"]
        ALERTS_CTR["6. Centralized Alerts Center"]
        SYS_HEALTH["7. System Health & Diagnostics"]
        BENCHMARK["8. Automated 20/50 Sample Test Runner"]
    end

    CAM --> VIS_ADAPT
    IMG --> VIS_ADAPT
    VID --> VIS_ADAPT
    VIS_ADAPT --> YOLO --> SKIN --> INSP_DEC
    INSP_DEC --> LED_EMU
    INSP_DEC --> EVT_BUS

    REC_DB --> REPLAY_CTRL
    REC_CSV --> REPLAY_CTRL
    MQTT_IN --> MOT_ADAPT
    REPLAY_CTRL --> MOT_ADAPT
    FAULT_INJ --> MOT_ADAPT
    MOT_ADAPT --> FEAT_ENG --> ANOM_MOD --> EVT_BUS

    EVT_BUS --> REST_API
    EVT_BUS --> WS_STREAM
    EVT_BUS --> SQLITE_DB
    VIS_ADAPT --> MJPEG_FEED

    REST_API --> DASHBOARD
    WS_STREAM --> DASHBOARD
    MJPEG_FEED --> LIVE_VISION
```

---

## 2. Decoupled Resilience Model
- **Independent Modules**: Vision and Motor monitoring execute in separate, isolated worker threads. A failure or disconnection in camera acquisition has zero impact on motor telemetry processing, and vice versa.
- **Fail-Safe Fallbacks**: If the webcam is disconnected, the vision pipeline safely degrades to static test image or recorded video mode without throwing unhandled exceptions.
- **Unified Event Pipeline**: All signals flow through `event_manager`, guaranteeing synchronized UTC ISO-8601 timestamps, explicit source labels, and persistent audit logging.

