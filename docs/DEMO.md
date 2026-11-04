# Final demonstration (M5.7 shot list + M5.8 live demo script)

The deadline demo must show: **auto-start after a power cycle, detection of my objects, the live dashboard, and my
headline metric**. Allow ~6 minutes. Rehearse once with a timer.

## Before the coach arrives (checklist)
- [ ] Rig set up and taped (RIG.md); 2 good parts + 1 of each defect + the motor with the MPU6050 on the table
- [ ] `git pull` done; `docker compose -f docker/compose.yaml ps` shows `edge` **healthy** and `mosquitto` Up
- [ ] Laptop/phone on the same network, dashboard open at `http://pi-karthik.local:8000`
- [ ] Terminal ready with `mosquitto_sub`-equivalent: `python scripts/mqtt_subscribe.py`
- [ ] OpenPLC Monitoring page open (`http://pi-karthik.local:8080`)

## Live demo script
| t | Do | Say | Visible proof |
|---|---|---|---|
| 0:00 | Pull the Pi's power plug, plug it back in, hands off | "Power cycle: nothing is started by hand." | Pi boots |
| ~1:00 | Refresh the dashboard | "systemd starts Docker, compose starts the broker and the station, restart=unless-stopped." | state RUNNING, FPS, line ● green |
| 1:30 | **Normal run:** put 3 good parts in the stop one after another | "Detect → inspect → decide, one result per part." | PASS each; parts feed; throughput/yield update; relay 1 stays on |
| 2:30 | Put the **marked** part, then the **lid-missing** part | "3 of 5 frames FAIL → reject output pulses, PLC coil pulses, MQTT detection message." | FAIL + reason; LED/relay 2 pulses; OpenPLC %QX0.0 blinks, %QW0 counts; subscriber prints `detection` |
| 3:30 | Mark each part good/defective on the dashboard | "Headline metric = correct results out of all parts I checked; false-pass rate beside it." | headline tile updates |
| 4:00 | **Injected fault:** stick the coin on the motor rotor (or tap the mount) | "Model trained on normal vibration only; 2 windows over the threshold = alert." | Motor card turns red "ANOMALY"; `motor/score` alert=true |
| 4:40 | **Pull the camera cable** | "Blind = stop: run_permit relay drops within ~1 s." | state SAFE STATE, relay 1 clicks off |
| 5:00 | Plug the camera back | "First good frame restores the line." | RUNNING again |
| 5:20 | Unplug the network cable / Wi-Fi off (dashboard via direct Ethernet or the Pi's screen) | "Broker, model and dashboard are all local: works offline." | still RUNNING |

## Demo video shot list (record on the phone, landscape, ≤ 3 min)
1. **Wide shot** of the whole station: Pi, camera arm, rig, relay/LED, motor + MPU6050 (5 s, slow pan).
2. **Power cycle**: hand pulls the plug, cut, plug in, dashboard coming up (show the clock in the frame).
3. **Normal run**: 3 good parts, split screen or cut between rig and dashboard (PASS, KPIs moving).
4. **Defects**: each defect type once; close-up of the LED/relay pulsing; dashboard FAIL + reason.
5. **PLC**: OpenPLC Monitoring tag changing at the same moment.
6. **Motor fault**: coin on rotor → dashboard motor card red.
7. **Camera unplug**: relay clicks off, SAFE STATE, plug back → RUNNING.
8. **Headline**: hold on the headline tile (e.g. "19/20 correct, false-pass 0 %") for 3 s.
9. Terminal: `python scripts/mqtt_security_test.py` → 6/6 PASS (2 s).
Save as `evidence/M5/demo.mp4`; videos are git-ignored, so add it with `git add -f evidence/M5/demo.mp4` if it is < 50 MB,
otherwise upload it (Drive / YouTube unlisted) and put the link in the README.
