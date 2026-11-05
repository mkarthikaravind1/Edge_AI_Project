#!/usr/bin/env bash
# ONE command for the Raspberry Pi. First time (fresh SD card, logged in to the desktop, Terminal open):
#   bash /boot/firmware/start_here.sh         # if you copied this file onto the SD card from the laptop
#   or: git clone https://github.com/mkarthikaravind1/Edge_AI_Project.git ~/Edge_AI_Project && bash ~/Edge_AI_Project/deploy/start_here.sh
# It installs everything (deploy/pi_setup.sh), reboots by itself when needed and CONTINUES after the reboot
# (a Terminal window opens again), then shows a menu that runs every milestone (scripts/pi_evidence.sh) and
# reminds you which photo / video to take at each step. Run it again any time: it remembers what is done.
set -uo pipefail
REPO_URL="https://github.com/mkarthikaravind1/Edge_AI_Project.git"
REPO="$HOME/Edge_AI_Project"
STATE="$HOME/.edge_progress"
RESUME="$HOME/.config/autostart/edge-start-here.desktop"
LABWC="$HOME/.config/labwc/autostart"
c()    { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
title(){ printf '\n'; c "1;36" "==== $* ===="; }
pause(){ printf '\033[1;33m>> %s\033[0m  [ENTER] ' "$*"; read -r _; }
done_mark() { grep -qx "$1" "$STATE" 2>/dev/null || echo "$1" >> "$STATE"; }
is_done()   { grep -qx "$1" "$STATE" 2>/dev/null; }
tick()      { is_done "$1" && printf '\033[1;32m[done]\033[0m' || printf '      '; }

# ---------------------------------------------------------------- 0. get the code (and run the copy inside it)
if [ "$(cd "$(dirname "$0")" 2>/dev/null && pwd)" != "$REPO/deploy" ]; then
  if [ ! -d "$REPO/.git" ]; then
    title "Getting the code"
    command -v git >/dev/null || { sudo apt-get update && sudo apt-get install -y git; }
    git clone "$REPO_URL" "$REPO" || { c "1;31" "clone failed: is Wi-Fi connected? (top-right network icon)"; exit 1; }
  else
    git -C "$REPO" pull --ff-only || true
  fi
  exec bash "$REPO/deploy/start_here.sh" "$@"
fi
cd "$REPO"
touch "$STATE"

stop_resume() { rm -f "$RESUME"; [ -f "$LABWC" ] && sed -i '\#deploy/start_here.sh#d' "$LABWC"; return 0; }
arm_resume() {   # open a Terminal with this script again after the reboot
  mkdir -p "$(dirname "$RESUME")" "$(dirname "$LABWC")"
  local cmd="lxterminal --geometry=110x34 -e bash -lc 'flock -n /tmp/edge-start.lock bash $REPO/deploy/start_here.sh; exec bash'"
  printf '[Desktop Entry]\nType=Application\nName=Edge project setup (continue)\nExec=%s\n' "$cmd" > "$RESUME"
  touch "$LABWC"; grep -q "deploy/start_here.sh" "$LABWC" || echo "$cmd &" >> "$LABWC"
}

# ---------------------------------------------------------------- 1. setup (until no reboot is needed)
if ! is_done setup; then
  title "Step 1/2: installing everything (10-25 min, the Pi needs internet). Enter your Pi password when asked."
  stop_resume
  rm -f "$HOME/.edge_reboot_needed"
  bash deploy/pi_setup.sh
  rc=$?
  if [ $rc -eq 0 ] && [ -f "$HOME/.edge_reboot_needed" ]; then
    arm_resume
    c "1;33" "The Pi must restart once (I2C / docker group). This window opens again by itself after the restart."
    c "1;33" "(If it does not: open Terminal and type   bash ~/Edge_AI_Project/deploy/start_here.sh )"
    for s in 10 9 8 7 6 5 4 3 2 1; do printf '\rrestarting in %2d s (Ctrl+C to cancel) ' "$s"; sleep 1; done
    sudo reboot; exit 0
  fi
  [ $rc -eq 0 ] || { c "1;31" "Setup stopped with an error (see above / ~/pi_setup.log). Take a photo of the screen and send it to Claude."; exit 1; }
  done_mark setup
fi
stop_resume

# No personal data on this Pi: no git name/email, no GitHub login, nothing is committed or pushed from here.
# The Pi only COLLECTS evidence (menu 9 -> one zip); copy it to the laptop and commit there from your own account.

if ! is_done photo_setup; then
  title "Step 2/2: first photo"
  pause "PHOTO: the whole setup (Pi + webcam + monitor + your part) -> save as evidence/M1/setup_photo.jpg later"
  done_mark photo_setup
fi

# ---------------------------------------------------------------- menu
shots() {   # photo / video reminders per step
  case "$1" in
    m1) echo "  PHOTO screen after the first frame | VIDEO 30 s live overlay on the monitor (boxes + counts) | PHOTO speed result";;
    rig) echo "  PHOTO the rig (camera mount, dark card, stop, lamp) + write the camera height in docs/RIG.md";;
    m2) echo "  VIDEO INT8 running live | PHOTO the benchmark table (median / p95 / FPS / size)";;
    m3) echo "  VIDEO board LEDs test | VIDEO unplug the webcam: red PWR LED goes OFF, dashboard SAFE STATE, plug back -> ON"
        echo "  VIDEO 25 parts passing -> green ACT LED pulses each time | then the COLD BOOT video (pull the plug)";;
    coldboot) echo "  VIDEO pull the plug -> plug in -> dashboard comes back -> place a part -> green LED pulses";;
    m4) echo "  PHOTO MQTT 6/6 result | VIDEO OpenPLC tag changing when a part is seen | PHOTO OTA rollback + crash restart"
        echo "  (no MPU6050 on this rig: the sensor steps can be skipped with s + ENTER)";;
    m5) echo "  PHOTO 10 good + 10 defective parts laid out | PHOTO confusion matrix | VIDEO 10-min run (a short clip)"
        echo "  VIDEO power cycle with Wi-Fi off -> dashboard back by itself | PHOTO dashboard on your phone";;
  esac
}
run_step() { title "$2"; shots "$1"; pause "Ready?"; shift 2; "$@" && done_mark "$STEP"; }

while true; do
  title "Edge project on $(hostname) - what next?  (photos/videos: phone, of the monitor + the Pi)"
  echo "  1) $(tick m1)       M1  first frame, live overlay, baseline speed"
  echo "  2) $(tick rig)       Rig photo + record webcam clips for retraining"
  echo "  3) $(tick m2)       M2  benchmarks (TFLite/ONNX, FP32/INT8) + INT8 live"
  echo "  4) $(tick m3)       M3  board LEDs, two streams, debounce, camera unplug, latency, Docker + auto-start"
  echo "  5) $(tick coldboot)       M3  cold-boot proof (after pulling the plug)"
  echo "  6) $(tick m4)       M4  MQTT TLS, topics, OpenPLC, drift, OTA rollback, crash restart"
  echo "  7) $(tick kiosk)       M5  dashboard full-screen on the monitor at every boot"
  echo "  8) $(tick m5)       M5  rig pass/fail (10+10 parts), 10-min full chain, power cycle offline"
  echo "  9)              Collect ALL evidence into one zip (+ how to copy it to the laptop)"
  echo " 10)              Leave the Pi clean (delete my files + Wi-Fi from this Pi, at the very end)"
  echo "  0)              Quit (run  bash ~/Edge_AI_Project/deploy/start_here.sh  to come back)"
  read -rp "choose: " ch
  case "$ch" in
    1) STEP=m1; run_step m1 "M1 Detect" bash scripts/pi_evidence.sh m1 ;;
    2) STEP=rig; title "Rig + training clips"; shots rig
       pause "Rig built (docs/RIG.md)?"
       for clip in enclosure body lid mixed defects; do
         read -rp "record clip '$clip' now (60 s)? [Y/n/q] " a
         [ "$a" = q ] && break; [ "$a" = n ] && continue
         bash scripts/record_rig_video.sh "$clip" 60
       done
       bash scripts/record_rig_video.sh list; done_mark rig ;;
    3) STEP=m2; run_step m2 "M2 Optimize" bash scripts/pi_evidence.sh m2 ;;
    4) STEP=m3; run_step m3 "M3 Decide and act" bash scripts/pi_evidence.sh m3 ;;
    5) STEP=coldboot; run_step coldboot "M3 cold boot" bash scripts/pi_evidence.sh coldboot ;;
    6) STEP=m4; run_step m4 "M4 Monitor and connect" bash scripts/pi_evidence.sh m4 ;;
    7) STEP=kiosk; title "Kiosk"; bash deploy/kiosk.sh install && done_mark kiosk ;;
    8) STEP=m5; run_step m5 "M5 Complete system" bash scripts/pi_evidence.sh m5 ;;
    9) title "Collect evidence"
       bash scripts/collect_evidence.sh ;;
    10) title "Leave the Pi clean"
       c "1;33" "Do this ONLY after the evidence zip is safely on your laptop."
       read -rp "type DELETE to remove ~/Edge_AI_Project, the evidence zips, the services/kiosk and saved Wi-Fi: " a
       if [ "$a" = DELETE ]; then
         bash deploy/kiosk.sh remove || true; bash deploy/install_service.sh remove || true
         (docker compose -f docker/compose.yaml down -v 2>/dev/null; docker image rm edge-inspection:latest 2>/dev/null) || true
         rm -f "$HOME"/edge_evidence_*.zip "$STATE" "$HOME/pi_setup.log"
         cd "$HOME" && rm -rf "$REPO"
         for w in $(nmcli -t -f NAME,TYPE connection show 2>/dev/null | awk -F: '$2=="802-11-wireless"{print $1}'); do
           sudo nmcli connection delete "$w" >/dev/null && echo "forgot Wi-Fi: $w"
         done
         c "1;32" "Done. Last step: sudo deluser --remove-home <your user> from another account, or re-flash the card."
         exit 0
       fi ;;
    0) exit 0 ;;
    *) ;;
  esac
done
