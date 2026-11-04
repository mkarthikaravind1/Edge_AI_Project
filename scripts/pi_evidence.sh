#!/usr/bin/env bash
# Guided Pi evidence runner: every "on the device" measurement of docs/PI_CHECKLIST.md, milestone by milestone.
# It runs the commands, PAUSES for every hands-on step (wiring, unplugging, passing parts), and never commits:
# at the end it prints the git commands for you to run.
#   bash scripts/pi_evidence.sh m1        # or m2 / m3 / m4 / m5 / all
set -uo pipefail
cd "$(dirname "$0")/.."
export EDGE_TARGET=pi
PY=".venv/bin/python"
[ -x "$PY" ] || PY=python3
step()  { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ask()   { printf '\033[1;33m>> %s\033[0m\n   press ENTER when ready (or type s + ENTER to skip) ' "$*"; read -r a; [ "$a" != "s" ]; }
run()   { echo "\$ $*"; "$@" || echo "!! failed: $* - send the output above to Claude"; }
done_() { printf '\n\033[1;32mDone. Commit the evidence:\033[0m\n  git add %s && git commit -m "%s" && git push\n' "$1" "$2"; }

m1() {
  step "M1 Detect on the Pi"
  ask "Camera connected and the enclosure in view?" && run $PY scripts/capture_frame.py --name first_frame_pi
  ask "Live overlay 30 s (move the enclosure, body and lid in front of the camera)" && \
    run $PY scripts/run_live.py --headless --seconds 30 --save evidence/M1/live_overlay_pi.mp4
  run $PY -c "import cv2; c=cv2.VideoCapture('evidence/M1/live_overlay_pi.mp4'); c.set(1, 200); ok, f=c.read(); ok and cv2.imwrite('evidence/M1/live_overlay_pi.png', f)"
  ask "Baseline speed 60 s (keep a part in view)" && run $PY scripts/benchmark_pipeline.py --seconds 60
  done_ "evidence/M1" "M1: Pi first frame, live overlay, baseline"
  echo "  (the .mp4 is git-ignored; the .png screenshot is committed. Add the video with git add -f if < 50 MB)"
}

m2() {
  step "M2 Optimize on the Pi (let it idle 2 min first so it starts cool)"
  for b in tflite_int8 tflite_int8_full tflite_fp32 onnx_int8 onnx_fp32; do run $PY scripts/benchmark_model.py --backend "$b" --threads 4; done
  ask "INT8 live 30 s (parts in view)" && \
    run $PY scripts/run_live.py --backend tflite --model models/best_int8.tflite --headless --seconds 30 --save evidence/M2/live_int8_pi.mp4
  run $PY scripts/evaluate.py --backends tflite_int8 onnx_int8
  done_ "evidence/M2" "M2: Pi benchmarks + INT8 live"
  echo "  then on the LAPTOP: git pull && python scripts/compare_backends.py && python scripts/make_report.py"
}

m3() {
  step "M3 Decide and act on the Pi"
  ask "Relay IN1 on GPIO17 (pin 11), LED/relay IN2 on GPIO27 (pin 13) wired? (table in PI_CHECKLIST M3) - relay 1 should click on, LED blinks" && \
    run $PY -c "from gpiozero import LED; import time; r=LED(17); l=LED(27); r.on(); l.blink(0.2,0.2,5,False); r.off()"
  ask "Two streams 30 s (Pi camera + USB webcam both connected)" && run $PY scripts/two_stream.py --seconds 30
  run $PY scripts/debounce_demo.py
  ask "Safe state: at ~10 s UNPLUG the camera, at ~25 s plug it back (film relay 1)" && run $PY scripts/safe_state_demo.py --live --seconds 40
  ask "Latency: slide a closed enclosure under the camera and away, every ~3 s, until 25 events" && \
    run $PY scripts/e2e_latency.py --live --events 25
  step "Docker (first build ~10-15 min)"
  [ -f docker/.env ] || run $PY docker/mosquitto/make_passwd.py
  [ -f docker/mosquitto/certs/server.crt ] || run bash docker/mosquitto/make_certs.sh "$(hostname -I | awk '{print $1}')"
  chmod 600 docker/.env 2>/dev/null; chmod 640 docker/mosquitto/passwd 2>/dev/null
  run docker compose -f docker/compose.yaml up -d --build
  run sudo cp deploy/edge-compose.service /etc/systemd/system/
  run sudo systemctl daemon-reload
  run sudo systemctl enable edge-compose
  echo "Cold boot: sudo poweroff, pull power, plug in, wait 90 s, then: bash scripts/pi_evidence.sh coldboot"
  done_ "evidence/M3" "M3: Pi two-stream, debounce, safe state, e2e latency"
}

coldboot() {
  step "M3.5 cold boot proof"
  { date; uptime; docker ps; } | tee evidence/M3/cold_boot_docker_ps.txt
  docker logs edge --since 5m > evidence/M3/cold_boot_edge.log 2>&1
  ask "Put a part in view: the reject LED should pulse" && docker logs edge --since 1m 2>&1 | grep -iE "trigger|station starting" | tail -5 | tee -a evidence/M3/cold_boot_docker_ps.txt
  done_ "evidence/M3" "M3: cold boot (docker starts on power-up)"
}

m4() {
  step "M4 Monitor and connect on the Pi"
  ask "MPU6050 wired (VCC pin 1, GND 9, SDA 3, SCL 5) and taped to the motor?" && sudo i2cdetect -y 1
  if ask "Record 8 normal runs (30 s each, motor running, do not touch)"; then
    for i in 1 2 3 4 5 6 7 8; do run $PY scripts/record_imu.py --label normal --run "$i" --seconds 30; done
  fi
  ask "Fault 1: stick a coin / blu-tack on the rotor" && run $PY scripts/record_imu.py --label fault_unbalance --run 1 --seconds 30
  ask "Fault 2: bigger weight" && run $PY scripts/record_imu.py --label fault_unbalance --run 2 --seconds 30
  ask "Fault 3: remove the weight, TAP the mount about once a second" && run $PY scripts/record_imu.py --label fault_tap --run 1 --seconds 30
  run $PY scripts/train_anomaly.py --data data/imu/real
  ask "Live alert: motor normal; press ENTER in the monitor the moment you add the weight" && \
    run $PY scripts/motor_monitor.py --live --seconds 40
  run docker compose -f docker/compose.yaml up -d mosquitto
  run $PY scripts/mqtt_security_test.py
  docker logs mosquitto > evidence/M4/mosquitto_broker_pi.log 2>&1
  ask "Topics 60 s: station running (docker compose up -d), show parts and shake the motor" && \
    run $PY scripts/mqtt_subscribe.py --seconds 60 --save evidence/M4/mqtt_topics_sample_pi.json
  if ask "OpenPLC installed + edge_tags.st uploaded + PLC started? (PI_CHECKLIST 4.6; this opens port 8080 for the web UI)"; then
    sudo ufw allow 8080/tcp >/dev/null
    ask "Watch 60 s: pass parts under the camera" && run $PY scripts/plc_watch.py --seconds 60
    sudo ufw delete allow 8080/tcp >/dev/null
  fi
  ask "Drift 30 s from the station camera" && run $PY scripts/drift_report.py --live --seconds 30
  step "OTA v1 -> v2 -> broken v3 (rolled back), crash restart"
  for b in edge-v1 edge-v2 edge-v3-broken; do run docker exec edge python scripts/ota.py install "/app/deploy/ota/bundles/$b.tar.gz"; done
  run docker restart edge
  docker exec edge sh -c 'kill -USR1 1'; sleep 10
  { docker ps --filter name=edge; docker inspect -f 'restarts={{.RestartCount}}' edge; docker logs edge 2>&1 | grep -E "FORCED CRASH|station starting" | tail -3; } | tee evidence/M4/crash_restart_pi.log
  done_ "evidence/M4 data/imu/real models/anomaly.json" "M4: real IMU runs, anomaly model, MQTT TLS, topics, PLC, drift, OTA, restart"
}

m5() {
  step "M5 Complete system on the Pi"
  ask "Rig built (docs/RIG.md)? Photo saved as evidence/M5/rig_photo.jpg?" && run $PY scripts/capture_frame.py --name rig_view
  ask "Capture the rig set now (needs a screen/VNC): c x15, g x10, d x10" && run $PY scripts/capture_rig.py
  run $PY scripts/calibrate_inspection.py --dir data/rig/calib_good
  run $PY scripts/passfail_test.py --dir data/rig/test
  run docker compose -f docker/compose.yaml up -d --build
  if ask "10-minute full chain: pass parts every few seconds, mark each on the dashboard, shake the motor once"; then
    $PY scripts/mqtt_subscribe.py --seconds 600 --save evidence/M5/full_chain_mqtt_pi.json
    curl -s localhost:8000/api/stats > evidence/M5/full_chain_pi_stats.json
    curl -s localhost:8000/api/kpis > evidence/M5/full_chain_pi_kpis.json
    docker logs edge --since 11m > evidence/M5/full_chain_pi.log 2>&1
  fi
  ask "Power cycle: pull the plug, plug in, wait 90 s, then ENTER" && run $PY scripts/readiness_check.py --pi
  ask "Now switch Wi-Fi off / pull the cable (sudo nmcli radio wifi off), then ENTER" && run $PY scripts/readiness_check.py --pi
  echo "Wi-Fi back on: sudo nmcli radio wifi on"
  done_ "evidence/M5 data/rig models/inspection.json" "M5: rig pass/fail test, 10-min chain, readiness on the Pi"
}

case "${1:-}" in
  m1|m2|m3|m4|m5|coldboot) "$1" ;;
  all) m1; m2; m3; m4; m5 ;;
  *) echo "usage: bash scripts/pi_evidence.sh m1|m2|m3|coldboot|m4|m5|all" ;;
esac
