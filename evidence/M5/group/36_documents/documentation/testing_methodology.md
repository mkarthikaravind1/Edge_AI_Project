# M5 Testing & Verification Methodology

## 1. Test Architecture
The test suite is structured into 5 specialized layers under `testing/`:
- **Unit Tests (`testing/unit/`)**:
  - `test_m3_vision.py`: Model loading, class mapping, skin filter, 3-LED actuator truth table, decision policy.
  - `test_m4_motor.py`: 21-feature window extraction, normal operating baseline, overcurrent anomaly trigger.
- **Integration Tests (`testing/integration/`)**:
  - `test_integration.py`: Event bus routing, SQLite persistent writes, FastAPI REST and WebSocket endpoints, module decoupling resilience.
- **Inspection Station Tests (`testing/inspection/`)**:
  - `test_pass_fail_station.py`: Automated 20-sample pass/fail evaluation (Station 31) and 50-sample headline metric benchmark (Station 35).
- **Reliability Tests (`testing/reliability/`)**:
  - `test_reliability.py`: Missing webcam fallback, controlled fault injection and recovery, database lock resilience.

## 2. Execution
Run the full test suite with:
```cmd
pytest -v testing/
```
All 16 automated tests execute in under 35 seconds and report verified passes.

