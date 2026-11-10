# M3 Vision Source Audit Report & Integration Analysis

## 1. Executive Summary
- **Source Project**: Edge AI Milestone 3 (M3) — Decide and Act
- **Original Hardware Target**: Raspberry Pi 5 with Arducam / Raspberry Pi Camera V2
- **Model Framework**: Ultralytics YOLOv8 Nano (`best.pt`, 6.25 MB)
- **Trained Classes**: 
  - Class `0`: `gloves` (Safety gloves)
  - Class `1`: `head` (Bare head / unhelmeted worker violation)
  - Class `2`: `helmet` (Safety hardhat / compliant headwear)
- **Secondary Post-Processing**: Skin colorimetry (HSV + YCrCb + RGB) and Laplacian texture edge analysis distinguishes `bare_hand` violations from true `gloves`.
- **Target OS for M5**: Microsoft Windows 10/11 (x64) with native webcam, image upload, and recorded video input.

---

## 2. Preserved Authoritative LED Actuator Truth Table
Per the corrected M3 source specification, the LED logic is:

| Inspection Detection State | Green LED (GPIO 27) | Yellow LED (GPIO 17) | Red LED (GPIO 22) | Active Condition State | Industrial Meaning |
|:---|:---:|:---:|:---:|:---:|:---|
| **Helmet ONLY** | **ON** | OFF | OFF | `GREEN` | Helmet detected, gloves not yet detected |
| **Gloves ONLY** | OFF | **ON** | OFF | `YELLOW` | Gloves detected, helmet not yet detected |
| **Both Helmet AND Gloves** | OFF | OFF | **BLINKING (2 Hz)** | `RED_BLINKING` | Full PPE Compliance Achieved |
| **Neither Detected** | OFF | OFF | OFF | `OFF` | Idle / Clear Inspection Zone |

> [!IMPORTANT]
> - The Red LED is the **combined compliance indicator** and pulses/blinks when both helmet and gloves are detected.
> - Green and Yellow LEDs are strictly de-energized when Red is blinking.
> - The class `head` strictly indicates a **violation** (missing helmet) and is **never** conflated with `helmet`.

---

## 3. Inspection Decision Policy for M5
- **PASS**:
  - `helmet_detected == True` (Safety hardhat verified)
  - `gloves_detected == True` (Safety gloves verified)
  - `head_detected == False` (No bare head violations)
  - `bare_hand_detected == False` (No bare hand violations)
- **FAIL**:
  - Missing helmet (`helmet_detected == False` or `head_detected == True`)
  - Missing gloves (`gloves_detected == False` or `bare_hand_detected == True`)
  - Both PPE items missing

---

## 4. Windows Compatibility & Adapter Strategy
1. **Model Execution**: Runs natively on Windows using CPU/CUDA via PyTorch & Ultralytics.
2. **Video Capture**: Fallback-resilient pipeline supporting:
   - Index 0 / Default Windows DirectShow webcam.
   - User image upload (JPEG/PNG/WebP).
   - Video stream replay for repeatable automated benchmarking.
3. **Actuator Emulation**: Software GPIO state machine with non-blocking virtual timer threads matching the exact physical timing of the Raspberry Pi 5 RP1 chip.

