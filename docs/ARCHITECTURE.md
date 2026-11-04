# Architecture

## Software stack (M2.5)

![software stack](stack.png)

(`docs/stack.png` is drawn by `scripts/draw_stack.py`; the same stack as Mermaid below renders on GitHub.)

```mermaid
flowchart TB
    subgraph PI["Raspberry Pi (edge device)"]
        direction TB
        A2["Application: edgevision pipeline / decide / dashboard"]
        B2["Camera API: Picamera2 (libcamera) or OpenCV for USB"]
        C2["Pre-processing: OpenCV letterbox 320x320, BGR->RGB, /255"]
        D2["Runtime: TFLite INT8 (LiteRT) or ONNX Runtime"]
        E2["Delegate: XNNPACK on CPU (Coral libedgetpu / HailoRT if fitted)"]
        F2["OS: Raspberry Pi OS 64-bit + Docker"]
        G2["Hardware: Arm Cortex-A CPU (+ optional NPU/TPU)"]
        A2 --> B2 --> C2 --> D2 --> E2 --> F2 --> G2
    end
    subgraph LAP["Laptop (development)"]
        direction TB
        A1["Application: edgevision"]
        B1["Camera API: OpenCV VideoCapture (webcam / video)"]
        C1["Pre-processing: OpenCV letterbox 320x320"]
        D1["Runtime: PyTorch FP32 / ONNX Runtime / TFLite"]
        E1["Delegate: CPU (MLAS / XNNPACK)"]
        F1["OS: Windows 11"]
        G1["Hardware: x86-64 CPU"]
        A1 --> B1 --> C1 --> D1 --> E1 --> F1 --> G1
    end
```

## Code structure

```mermaid
flowchart LR
    CAM["hal.Camera<br/>webcam / video / Picamera2"] --> DET["detect.Detector<br/>ultralytics / onnx / tflite"]
    DET --> OVL["pipeline.overlay<br/>boxes, counts, FPS"]
    DET --> DEC["decide.DecisionEngine<br/>N-of-M, cooldown, safe state"]
    DEC --> ACT["hal.Actuator<br/>console / GPIO relay"]
    DEC --> PLC["hal.Plc<br/>fake / Modbus TCP"]
    IMU["hal.Imu<br/>CSV / MPU6050"] --> MON["monitor<br/>features + anomaly"]
```

Only `hal/*` and the runtime backends import hardware/runtime libraries. Switching laptop -> Pi is `EDGE_TARGET=pi`
(`config/pi.yaml`), not a code change.

## Why the runtime is pluggable
`make_detector()` builds the backend named in the config. The same `detect(image) -> [Detection]` contract is used by
the live pipeline, the evaluator and the benchmark, so accuracy and speed are compared on identical pre/post-processing.
An accelerator is added by passing a delegate (e.g. `delegate: libedgetpu.so.1` for Coral) or a new backend class.
