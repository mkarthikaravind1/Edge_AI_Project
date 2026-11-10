# M5 Vision Inspection & Decision Workflow

## 1. Inspection Policy
- **PASS (Compliant)**:
  - `helmet_detected == True` (Safety Hardhat verified)
  - `gloves_detected == True` (Safety Gloves verified)
  - `head_detected == False` (No bare head violations)
  - `bare_hand_detected == False` (No bare hand violations)
- **FAIL (Non-Compliant)**:
  - Missing hardhat (bare head detected or helmet absent)
  - Missing safety gloves (bare hand detected or gloves absent)
  - Both PPE items missing

---

## 2. Detection Pipeline Execution
1. **Frame Ingestion**: Captured from DirectShow webcam, user image upload, or looping recorded video.
2. **YOLOv8 Nano Inference**: Processed at 640x640 resolution with confidence threshold `0.35` and IoU threshold `0.45`.
3. **Skin Colorimetry & Texture Post-Filter**: For every bounding box classified as `gloves`, an inner crop is extracted and evaluated in HSV, YCrCb, and RGB color spaces. If skin pixel density is high and Laplacian texture variance is low, the object is re-labeled as `bare_hand` (violation).
4. **Policy Evaluation**: Counts of compliant items vs violations are evaluated against the inspection policy.
5. **Actuator Update**: Virtual 3-LED state machine is updated according to the authoritative truth table.
6. **Persistence & Broadcast**: Normalized dictionary is published to `event_bus`, stored in SQLite, and pushed to WebSocket subscribers.

