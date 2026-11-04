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

step "1/7 system packages"
sudo apt-get update
sudo apt-get install -y git python3-venv python3-picamera2 python3-gpiozero python3-lgpio python3-smbus2 \
    i2c-tools libgl1 libglib2.0-0 mosquitto-clients ufw

step "2/7 interfaces: I2C on, camera auto-detect"
if [ "$(sudo raspi-config nonint get_i2c)" != "0" ]; then sudo raspi-config nonint do_i2c 0; need_reboot=1; fi
CFG=/boot/firmware/config.txt; [ -f "$CFG" ] || CFG=/boot/config.txt
grep -q '^camera_auto_detect=1' "$CFG" || { echo 'camera_auto_detect=1' | sudo tee -a "$CFG"; need_reboot=1; }

step "3/7 docker"
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; need_reboot=1; fi
sudo systemctl enable --now docker
groups "$USER" | grep -q docker || { sudo usermod -aG docker "$USER"; need_reboot=1; }
groups "$USER" | grep -qw gpio || sudo usermod -aG gpio,video,i2c "$USER"

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
echo "cameras:";  (rpicam-hello --list-cameras 2>/dev/null || libcamera-hello --list-cameras 2>/dev/null || echo "  (rpicam tools missing)") | head -8
echo "USB video:"; ls /dev/video* 2>/dev/null | head -4 || true
echo "I2C bus 1 (MPU6050 shows 68):"; sudo i2cdetect -y 1 2>/dev/null || echo "  I2C not active yet (reboot)"
echo "temperature: $(vcgencmd measure_temp 2>/dev/null || echo n/a)"
echo "model: $(tr -d '\0' < /proc/device-tree/model)"

step "7/7 firewall (Modbus 502 and OpenPLC 8080 stay off the LAN; pi_evidence.sh m4 opens 8080 briefly)"
# 22 SSH, 5900 VNC (live view for capture_rig.py), 8000 dashboard, 8883 MQTT over TLS
for p in 22 5900 8000 8883; do sudo ufw allow "$p/tcp" >/dev/null; done
sudo ufw default deny incoming >/dev/null
echo "y" | sudo ufw enable >/dev/null && sudo ufw status | head -8

if [ "$need_reboot" = 1 ]; then
  printf '\n\033[1;33mREBOOT NEEDED: sudo reboot   then run this script once more to confirm everything is green.\033[0m\n'
else
  printf '\n\033[1;32mPi ready. Next: bash scripts/pi_evidence.sh m1\033[0m\n'
fi
