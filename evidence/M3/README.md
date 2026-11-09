# M3 — Decide and Act: evidence index

Every M3 checklist item, the number that proves it, and the exact files. Files stay flat in this folder because the
scripts write them here; this page is the map.

**Where it ran:** 💻 = measured on the laptop · ⏳ Pi = Pi run pending ([PI_CHECKLIST § M3](../../docs/PI_CHECKLIST.md#m3--decide-and-act-on-the-pi)).
Laptop numbers are never presented as Pi numbers.

| # | Criterion | Result | Evidence | Where |
|---|---|---|---|---|
| 3.1 | Decision rule sheet | `enclosure` ≥ 0.60 in **3 of the last 5 frames** → fire once per part; safe state after 1 s without frames | [DECISION_RULES](../../docs/DECISION_RULES.md) | — |
| 3.2 | Two streams | Both streams hold **30 FPS** (camera rate); flat out shared model 84 FPS each, separate models 107 FPS each | [two_stream_laptop.json](two_stream_laptop.json) | 💻, ⏳ Pi |
| 3.3 | Debounce | Single part frame does not fire; 3rd in a row fires; same part holds; new part fires again | [debounce_demo.json](debounce_demo.json), [debounce_demo.csv](debounce_demo.csv), tests [test_decide.py](../../tests/test_decide.py) | 💻, ⏳ Pi |
| 3.4 | Actuator + safe state | run_permit off **1.06 s** after the last frame (timeout 1.0 s), back on with the first good frame | [safe_state.json](safe_state.json), [safe_state_log.csv](safe_state_log.csv) | 💻 (simulated unplug), ⏳ Pi |
| 3.5 | Docker + auto-start | Bookworm image, `restart: unless-stopped`, systemd unit; healthy container on the laptop | [Dockerfile](../../docker/Dockerfile), [compose.yaml](../../docker/compose.yaml), [edge-compose.service](../../deploy/edge-compose.service), [docker_healthy_laptop.txt](../M5/docker_healthy_laptop.txt) | 💻, ⏳ Pi cold boot |
| 3.6 | End-to-end latency | Frame that fired → actuator p95 **8.8 ms** (median 6.6 ms); part's first frame → actuator ~75 ms (includes the deliberate 3-of-5 wait) | [e2e_latency_laptop.json](e2e_latency_laptop.json), [e2e_latency_laptop.csv](e2e_latency_laptop.csv) | 💻, ⏳ Pi |

## Code that produced it
| # | Script |
|---|---|
| 3.1 / 3.3 | [rules.py](../../src/edgevision/decide/rules.py), [parts.py](../../src/edgevision/decide/parts.py), [debounce_demo.py](../../scripts/debounce_demo.py) |
| 3.2 | [two_stream.py](../../scripts/two_stream.py) |
| 3.4 | [safe_state_demo.py](../../scripts/safe_state_demo.py), [actuator.py](../../src/edgevision/hal/actuator.py), watchdog in [runtime.py](../../src/edgevision/runtime.py) |
| 3.5 | [install_service.sh](../../deploy/install_service.sh) |
| 3.6 | [e2e_latency.py](../../scripts/e2e_latency.py) |

## Still to record on the Pi
`two_stream_pi.json`, `safe_state.json` with a real webcam unplug (film the relay), `e2e_latency_pi.json`,
`cold_boot_docker_ps.txt` + `cold_boot_edge.log` — commands in [PI_CHECKLIST § M3](../../docs/PI_CHECKLIST.md#m3--decide-and-act-on-the-pi).

More: [VIVA_NOTES § M3](../../docs/VIVA_NOTES.md#m3-decide-and-act) · all numbers: [RESULTS § M3](../../docs/RESULTS.md#m3)
