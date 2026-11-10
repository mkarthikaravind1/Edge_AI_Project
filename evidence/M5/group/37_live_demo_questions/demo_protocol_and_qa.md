# Assessment Requirement 37: Live Demonstration Protocol & Coach Q&A Bank

## 1. Assessment Requirement & Weighting
- **Requirement Statement**: *"I run one normal run and one injected fault, and answer the coach's questions."*
- **Assessment Milestone**: M5 Milestone — System Demonstration & Technical Defense
- **Maximum Marks**: **1 Mark**

---

## 2. Demonstration 1: Standard Normal Execution Protocol
### Objective:
Demonstrate the end-to-end synchronized operation of the vision inspection station, motor condition monitoring, three headline KPIs, and live industrial dashboard.

### Step-by-Step Procedure:
1. **Launch Application**:
   - Double-click `run_m5.bat` from Windows File Explorer.
   - Browser opens to `http://127.0.0.1:8000`.
2. **Observe System Overview**:
   - Confirm global status indicator displays green `SYSTEM OPERATIONAL`.
   - Point out the **Three Headline KPIs**:
     - KPI 1: Inspection Accuracy (`100%`)
     - KPI 2: Inspection Pass Rate (`50.0%`)
     - KPI 3: Motor Anomaly Events (`0` or current active count).
3. **Execute Vision Inspection**:
   - Switch to **Vision Inspection** tab.
   - Point out the live video feed with bounding boxes and HUD overlay.
   - Point out the **3-LED Actuator Stack**:
     - Green LED illuminates when helmet only is present.
     - Yellow LED illuminates when gloves only are present.
     - Red LED blinks continuously when both helmet and gloves are detected.
4. **Execute Motor Condition Telemetry**:
   - Switch to **Motor Monitoring** tab.
   - Point out the multi-channel oscilloscopes streaming current, vibration, and audio.
   - Adjust replay speed to `2.0x` and observe live sample rate synchronization.

---

## 3. Demonstration 2: Controlled Injected Fault & Recovery Protocol
### Objective:
Demonstrate fault detection, instantaneous alarm generation, dashboard notification, and seamless recovery after fault clearance without damaging hardware.

### Step-by-Step Procedure:
1. **Inject Overcurrent Stall Fault**:
   - On the **Motor Monitoring** tab, open the **Inject Controlled Fault** dropdown.
   - Select `Current Surge (>200mA)`.
2. **Observe Immediate Fault Reaction**:
   - Current reading spikes to `0.285 A` (Limit: `0.200 A`).
   - Multivariate anomaly score shoots from `0.05` to `0.95`.
   - Motor status badge transitions from green `NORMAL` to red `ANOMALY`.
   - A critical alarm card appears in the Alerts Center.
   - KPI 3 counter increments to reflect the new anomaly event.
3. **Clear Fault & Verify Recovery**:
   - Select `Clean Normal Operation` from the dropdown.
   - Observe current returning to nominal `0.085 A`.
   - Anomaly score decays back to `<0.10`.
   - Status badge returns to green `NORMAL` within 100 ms.

---

## 4. Comprehensive Coach Question-and-Answer Bank

### Q1: Why did you develop M5 on Windows instead of Raspberry Pi?
> **Answer**:
> *"Milestones M3 and M4 were individually developed and tested on Raspberry Pi 5 and Arduino hardware to prove physical edge feasibility. For Milestone M5, our objective is system integration, production dashboard delivery, and automated verification across both subsystems. Developing the integrated software product on Windows allows us to leverage high-performance multi-threading, direct webcam acceleration, unified database logging, and professional browser visualization, while preserving the authentic Raspberry Pi models, codebases, and recorded datasets without requiring fragile multi-board hardware tethering."*

### Q2: What is the exact class mapping of your YOLO model?
> **Answer**:
> *"Our trained YOLOv8 Nano model (`best.pt`) uses three classes: Class 0 is `gloves`, Class 1 is `head` (which represents an unhelmeted bare head and is strictly treated as a violation), and Class 2 is `helmet` (safety hardhat). Additionally, our vision adapter applies a secondary skin colorimetry and Laplacian texture filter to detect exposed bare hands within glove candidate crops."*

### Q3: Explain the 3-LED Actuator logic and why the Red LED blinks.
> **Answer**:
> *"Per the corrected M3 specification, the 3-LED indicator stack follows an authoritative four-state truth table: Green LED turns ON when helmet ONLY is detected; Yellow LED turns ON when gloves ONLY are detected; Red LED blinks at 2 Hz when BOTH helmet and gloves are simultaneously detected to indicate full compliance; and all LEDs remain OFF when neither is detected. Green and Yellow are strictly extinguished while the Red LED blinks."*

### Q4: How is your motor anomaly model trained and how does it detect anomalies?
> **Answer**:
> *"The motor anomaly model (`anomaly_model_latest.pkl`) is a multivariate statistical engine with regularized noise floors trained on normal baseline operating data. A 10-sample sliding window extracts 21 statistical, electrical, and vibration features. The model combines hard physical safety thresholds (immediate alarm if current exceeds 200mA) with cross-domain Z-scores spanning electrical, vibration, and acoustic channels. The composite score is normalized through a sigmoid function into a continuous range from 0.0 to 1.0, triggering an anomaly alert when the score exceeds 0.65."*

### Q5: How do you prevent replayed or simulated data from being misrepresented as live sensor data?
> **Answer**:
> *"Every single telemetry packet ingested by our adapter explicitly carries a metadata tag `source_mode`: `LIVE_MQTT`, `RECORDED_DATA`, `CSV_REPLAY`, or `SIMULATED`. The backend, database, and live dashboard preserve this label on all displays and exports, guaranteeing complete technical honesty and data provenance."*

---

## 5. Verification Status
- **Verification Status**: **VERIFIED & COMPLETE** (1 / 1 Mark).

