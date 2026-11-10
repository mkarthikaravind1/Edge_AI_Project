# M5 System Reliability, Fault Injection & Recovery Report

## 1. Resilience Architecture
The M5 system was engineered to guarantee that neither subsystem failure nor hardware disconnection compromises dashboard availability:
- **Decoupled Worker Threads**: Vision acquisition and motor replay operate in separate background threads with independent error handling.
- **Fail-Safe Sensor Fallback**: Disconnecting a live webcam automatically engages the standby image stream without crashing the Uvicorn server.
- **Zero Simulated Camouflage**: Replayed data, simulated data, and genuine live inputs are strictly labeled with their exact provenance (`source_mode`), preventing artificial claims.

## 2. Injected Fault Demonstrations (Assessment 37)
- **Fault 1: Current Stall Overload (`CURRENT_SURGE`)**:
  - Injected Value: Current jumps to 0.285 A (Limit: 0.200 A).
  - Observed Behavior: Multivariate anomaly score escalates from 0.05 to 0.95 within 100 ms. A CRITICAL motor alert is recorded in SQLite and broadcast to the dashboard.
  - Recovery: Returning to `NONE` restores score to <0.10 and de-energizes alarm state.
- **Fault 2: Severe Mechanical Friction (`BEARING_GRIND`)**:
  - Injected Value: Sound P2P exceeds 720 (Limit: 600) and vibration spikes to 620 ADC.
  - Observed Behavior: Cross-domain acoustic/vibration divergence triggers immediate anomaly warning.

