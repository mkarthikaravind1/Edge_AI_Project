# M1 on the device — Raspberry Pi 5 (6 Nov 2026)

Device: **Raspberry Pi 5 Model B Rev 1.1**, 4 GB, Raspberry Pi OS (Legacy, 64-bit) Bookworm, Python 3.11.2,
USB webcam (SunplusIT ZQ-1080RL HD Camera) at 640×480 MJPG. Model: `models/best_int8.tflite` (YOLOv8n INT8, 320 px).
Run with `bash scripts/pi_evidence.sh m1` (menu 1 of `deploy/start_here.sh`). Every json records the host it ran on.

| Checklist item | Evidence | Measured on the Pi |
|---|---|---|
| Camera and repo | `first_frame_pi.png` / `.json`, `pi_setup_check_photo.jpg` (photo of the monitor: webcam test 10/10 frames, Pi 5 detected, setup done) | first frame 640×480 from the USB webcam |
| OpenCV pipeline (live overlay) | `live_overlay_pi.mp4` (30 s, boxes + counts on the Pi), `live_overlay_pi.png` (one frame), `pi_m1_results_photo.jpg` (monitor photo) | body 0.95 and lid 0.96 detected live; also 2 false `body` boxes on the hand / keyboard (a wrong-detection case for the write-up) |
| Baseline speed | `baseline_pi.json`, `baseline_pi_samples.csv` | **15.55 FPS** over 60 s (934 frames); frame latency **median 19.3 ms, p95 23.1 ms**; inference median 18.9 ms; **CPU 27.7 % mean / 38.1 % peak**; **temperature 60.7 °C mean / 63.7 °C peak**; no GPU used (CPU inference) |

Notes
- 15.5 FPS is set by the webcam's frame rate (the model alone runs at ~54 FPS, see M2), not by the detector.
- The model was trained on phone-video frames of a wooden desk; on the new webcam + background it still finds body
  and lid but adds false boxes. It is being retrained on clips recorded on the rig with this webcam.
