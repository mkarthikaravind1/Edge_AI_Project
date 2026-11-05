#!/usr/bin/env bash
# One-shot Raspberry Pi setup (fresh Raspberry Pi OS 64-bit Bookworm) = section 0 of docs/PI_CHECKLIST.md.
# Safe to run again: every step checks what is already done.
#   git clone https://github.com/mkarthikaravind1/Edge_AI_Project.git ~/Edge_AI_Project
#   bash ~/Edge_AI_Project/deploy/pi_setup.sh
# Log: ~/pi_setup.log.  Reboot when it says so (I2C / camera / docker group need it).
set -euo pipefail
exec > >(tee -a "$HOME/pi_setup.log") 2>&1
REPO="$(cd "$(dirname "$0")/.." && pwd)"
step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
need_reboot=0

step "0/7 OS check"
. /etc/os-release
echo "OS: $PRETTY_NAME  arch: $(uname -m)  python: $(python3 --version 2>&1)"
[ "$(uname -m)" = "aarch64" ] || { echo "!! needs the 64-bit Raspberry Pi OS (uname -m = aarch64)"; exit 1; }
if [ "${VERSION_CODENAME:-}" != "bookworm" ]; then
  printf '\033[1;33m!! This repo is pinned to Raspberry Pi OS Bookworm (Python 3.11, numpy 1.x).\n'
  printf '   This card has "%s". Re-flash with Raspberry Pi Imager -> Raspberry Pi OS (other) ->\n' "${VERSION_CODENAME:-unknown}"
  printf '   "Raspberry Pi OS (Legacy, 64-bit)" = Bookworm. Continue anyway with: FORCE_OS=1 bash %s\033[0m\n' "$0"
  [ "${FORCE_OS:-0}" = 1 ] || exit 1
fi

step "1/7 system packages"
sudo apt-get update
sudo apt-get install -y git python3-venv python3-picamera2 python3-gpiozero python3-lgpio python3-smbus2 \
    i2c-tools libgl1 libglib2.0-0 mosquitto-clients ufw v4l-utils curl

step "2/7 interfaces: I2C on, camera auto-detect"
if [ "$(sudo raspi-config nonint get_i2c)" != "0" ]; then sudo raspi-config nonint do_i2c 0; need_reboot=1; fi
CFG=/boot/firmware/config.txt; [ -f "$CFG" ] || CFG=/boot/config.txt
grep -q '^camera_auto_detect=1' "$CFG" || { echo 'camera_auto_detect=1' | sudo tee -a "$CFG"; need_reboot=1; }

step "3/7 docker"
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; need_reboot=1; fi
sudo systemctl enable --now docker
groups "$USER" | grep -q docker || { sudo usermod -aG docker "$USER"; need_reboot=1; }
groups "$USER" | grep -qw gpio || sudo usermod -aG gpio,video,i2c "$USER"
# board LEDs (green ACT, red PWR) are the station's visible outputs until an LED/relay is wired: let group gpio
# switch them without sudo (config/pi.yaml reject/run_permit: type onboard_led)
RULE=/etc/udev/rules.d/99-edge-board-leds.rules
if [ ! -f "$RULE" ]; then
  echo 'SUBSYSTEM=="leds", KERNEL=="ACT|PWR", ACTION=="add", RUN+="/bin/sh -c '"'"'chgrp gpio /sys%p/brightness /sys%p/trigger; chmod g+w /sys%p/brightness /sys%p/trigger'"'"'"' \
    | sudo tee "$RULE" >/dev/null
  sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=leds --action=add || true
fi
ls /sys/class/leds/ 2>/dev/null | tr '\n' ' '; echo "(board LEDs)"

step "4/7 python venv + requirements"
cd "$REPO"
[ -d .venv ] || python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --default-timeout=120 --retries 5 -r requirements-pi.txt
.venv/bin/pip install -e . --no-deps
grep -q 'EDGE_TARGET=pi' "$HOME/.bashrc" || echo 'export EDGE_TARGET=pi' >> "$HOME/.bashrc"

step "5/7 tests (must all pass on the Pi too)"
EDGE_TARGET=pi .venv/bin/python -m pytest -q || echo "!! some tests failed - send the output to Claude"

step "6/7 hardware check"
echo "USB webcam (config/pi.yaml camera: webcam, index: auto):"
v4l2-ctl --list-devices 2>/dev/null | head -12 || true
ls -l /dev/v4l/by-id/ 2>/dev/null || echo "  !! no USB webcam found: plug it into a USB port and run this script again"
EDGE_TARGET=pi .venv/bin/python - <<'PY' || true
from edgevision.hal import make_camera
from edgevision.config import load_config
try:
    cam = make_camera(load_config("pi")["camera"]); frames = [cam.read() for _ in range(10)]; cam.close()
    ok = [f for f in frames if f is not None]
    print(f"  webcam test: {len(ok)}/10 frames, size {ok[-1].image.shape[1]}x{ok[-1].image.shape[0]}" if ok else "  !! webcam opened but gave no frames")
except Exception as e:
    print("  !! webcam test failed:", e)
PY
echo "I2C bus 1 (MPU6050 shows 68):"; sudo i2cdetect -y 1 2>/dev/null || echo "  I2C not active yet (reboot)"
echo "temperature: $(vcgencmd measure_temp 2>/dev/null || echo n/a)"
echo "model: $(tr -d '\0' < /proc/device-tree/model)"

step "7/7 firewall (Modbus 502 and OpenPLC 8080 stay off the LAN; pi_evidence.sh m4 opens 8080 briefly)"
# 22 SSH, 5900 VNC (live view for capture_rig.py), 8000 dashboard, 8883 MQTT over TLS
for p in 22 5900 8000 8883; do sudo ufw allow "$p/tcp" >/dev/null; done
sudo ufw default deny incoming >/dev/null
echo "y" | sudo ufw enable >/dev/null && sudo ufw status | head -8

rm -f "$HOME/.edge_reboot_needed"
[ "$need_reboot" = 1 ] && touch "$HOME/.edge_reboot_needed"     # read by deploy/start_here.sh
if [ "$need_reboot" = 1 ]; then
  printf '\n\033[1;33mREBOOT NEEDED: sudo reboot   then run this script once more to confirm everything is green.\033[0m\n'
else
  printf '\n\033[1;32mPi ready. Next: bash scripts/pi_evidence.sh m1\033[0m\n'
  printf '  later (M3): bash deploy/install_service.sh compose   (station starts at every boot)\n'
  printf '  later (M5): bash deploy/kiosk.sh install             (monitor shows the dashboard after boot)\n'
fi
