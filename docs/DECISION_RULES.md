# Decision rule sheet (M3.1)

Implemented in `src/edgevision/decide/rules.py` (`DecisionEngine`), wired in `src/edgevision/runtime.py`,
configured in the `decide:` block of `config/laptop.yaml` / `config/pi.yaml`. Unit tests: `tests/test_decide.py`,
`tests/test_runtime.py`.

| Item | Value | Config key | Why |
|---|---|---|---|
| **Input** | detections from the INT8 YOLOv8n (320 px) every frame; M3: class `enclosure` (a closed part in view). M5: the inspection verdict `FAIL` | `trigger_classes`, `inspection.enabled` | The closed box is the finished product the station checks. |
| **Confidence threshold** | 0.60 | `conf_threshold` | Measured with the shipped INT8 model on the 54 real test+val frames: all **77 correct** detections score ≥ 0.61 (median 0.96), while **7 of 11 false** detections score < 0.60. So 0.60 removes most false hits and no real one. The margin is thin (min 0.61), and debounce covers the rest: one weak frame cannot fire alone. |
| **Debounce** | fire when ≥ **3 of the last 5** frames are hits | `n`, `m` | One bad frame can never fire (needs 3); a real part (in view ≥ 0.5 s) always does. At 30 FPS the wait is 2 frames ≈ 67 ms; at 6 FPS (Pi 4 target) ≈ 0.33 s. |
| **One trigger per part** | after firing, re-arm only after 5 frames in a row with no hit (part has left) | `rearm_on_clear` | Without it a part that stays in view fires again every cooldown (measured: 8 triggers in 15 s for one part). |
| **Cooldown** | 2.0 s minimum between triggers | `cooldown_s` | Second guard against double-counting if the part briefly vanishes (occlusion by a hand). |
| **Action** | `reject` output (GPIO27, LED / relay 2) pulses 0.5 s; PLC coil %QX0.0 pulses; holding register %QW0 = trigger count; MQTT `edge/<id>/detection` event | `pulse_s`, `reject`, `plc` | |
| **Safe state when the camera fails** | no frame for **1.0 s** → `run_permit` (GPIO17, relay 1) **de-energised = conveyor STOP**; restored with the first good frame | `camera_timeout_s`, `run_permit` | See reasoning below. |

## Safe state — reasoning
- **Blind = stop.** If the camera fails, defective parts would pass uninspected. Stopping the line is the only state
  where no bad part can leave.
- **Fail-safe wiring, not fail-safe software.** The conveyor may run *only while* relay 1 is energised. Every failure
  mode removes the energy: camera lost (watchdog turns it off), program crash or hang (the Python process dies, the
  GPIO line falls to 0 V), power loss (the coil drops out). No failure leaves the line running.
- **1.0 s timeout.** Normal frame gap is 33 ms (30 FPS) to 170 ms (6 FPS); 1 s is > 5× the slowest normal gap, so
  a single slow frame never stops the line, while a dead camera is caught within about 1.05 s
  (watchdog ticks every 50 ms). Measured on the laptop: **1.06 s** (`evidence/M3/safe_state.json`).
- **Auto-recovery.** The first good frame re-energises `run_permit`; the debounce window is cleared, so no stale hits
  can fire straight after recovery.

## Evidence
| Claim | File | Laptop result |
|---|---|---|
| One bad frame does not trigger, N in a row do | `evidence/M3/debounce_demo.json` / `.csv` | glitch frame 6: no trigger; triggers at frames 15 and 59 as expected |
| Camera loss → safe state, then recovery | `evidence/M3/safe_state.json` / `safe_state_log.csv` | off 1.06 s after last frame; back on at first frame |
| Frame → actuator latency (≥ 20 events) | `evidence/M3/e2e_latency_laptop.json` | 25 events: median 6.6 ms, p95 8.8 ms (first hit → cmd 73 / 75 ms) |
| Pi results | `*_pi.json` | after the Pi run (`docs/PI_CHECKLIST.md`, M3) |
