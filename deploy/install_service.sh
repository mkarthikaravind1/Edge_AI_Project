#!/usr/bin/env bash
# Install one of the systemd units for THIS Pi user and THIS repo folder (any username, any clone location).
#   bash deploy/install_service.sh compose      # Docker stack at boot (M3 cold boot, M5 power cycle)  <- normal choice
#   bash deploy/install_service.sh station      # venv instead of Docker (crash-restart test without Docker)
#   bash deploy/install_service.sh remove       # disable + remove both
# Only one of compose / station may be active: both would open the same webcam and GPIO pins.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
[ "$USER_NAME" = "root" ] && { echo "run as your normal user (the script calls sudo itself)"; exit 1; }

install_unit() {   # $1 = unit name (edge-compose / edge-station)
  sed -e "s#@USER@#${USER_NAME}#g" -e "s#@REPO@#${REPO}#g" "$REPO/deploy/$1.service" \
    | sudo tee "/etc/systemd/system/$1.service" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable "$1"
  echo "installed /etc/systemd/system/$1.service  (User=$USER_NAME, WorkingDirectory=$REPO)"
}

stop_unit() {      # $1 = unit name
  if systemctl list-unit-files "$1.service" >/dev/null 2>&1 && [ -f "/etc/systemd/system/$1.service" ]; then
    sudo systemctl disable --now "$1" >/dev/null 2>&1 || true
    sudo rm -f "/etc/systemd/system/$1.service"
    sudo systemctl daemon-reload
    echo "removed $1"
  fi
}

case "${1:-}" in
  compose)
    groups "$USER_NAME" | grep -qw docker || { echo "user $USER_NAME is not in the docker group yet: run deploy/pi_setup.sh and reboot"; exit 1; }
    stop_unit edge-station
    install_unit edge-compose
    echo "start now: sudo systemctl start edge-compose   (it also starts by itself at every boot)" ;;
  station)
    [ -x "$REPO/.venv/bin/python" ] || { echo "no .venv: run deploy/pi_setup.sh first"; exit 1; }
    stop_unit edge-compose
    (cd "$REPO" && docker compose -f docker/compose.yaml stop edge >/dev/null 2>&1) || true
    install_unit edge-station
    sudo systemctl start edge-station
    echo "status: systemctl status edge-station   logs: journalctl -u edge-station -f" ;;
  remove)
    stop_unit edge-compose
    stop_unit edge-station ;;
  *)
    echo "usage: bash deploy/install_service.sh compose|station|remove"; exit 2 ;;
esac
