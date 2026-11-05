#!/usr/bin/env bash
# Show the dashboard full-screen on the Pi's monitor every time the desktop starts (M5 demo, power-cycle test).
#   bash deploy/kiosk.sh install     # desktop auto-login + Chromium kiosk at http://localhost:8000
#   bash deploy/kiosk.sh run         # open it now (what the autostart entry calls)
#   bash deploy/kiosk.sh remove      # back to a normal desktop (auto-login is left as it is)
# Leave kiosk: Alt+F4 (or Ctrl+W). The station itself runs as a service, not in the browser: closing Chromium
# never stops the station, and the dashboard stays reachable at http://<hostname>.local:8000 from a phone.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
URL="${KIOSK_URL:-http://localhost:8000}"
ENTRY="$HOME/.config/autostart/edge-kiosk.desktop"
LABWC="$HOME/.config/labwc/autostart"
LINE="bash $REPO/deploy/kiosk.sh run &"

browser() { command -v chromium-browser || command -v chromium || true; }

case "${1:-}" in
  run)
    exec 9>"/tmp/edge-kiosk.lock"; flock -n 9 || exit 0          # started by two autostart mechanisms: run once
    for _ in $(seq 1 150); do                                     # wait up to 5 min for the station (cold boot)
      curl -fs -o /dev/null "$URL/" && break; sleep 2
    done
    B="$(browser)"; [ -n "$B" ] || { echo "Chromium not found: sudo apt install -y chromium-browser"; exit 1; }
    exec "$B" --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble \
         --check-for-update-interval=31536000 --password-store=basic "$URL" ;;
  install)
    [ -n "$(browser)" ] || sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium
    mkdir -p "$(dirname "$ENTRY")" "$(dirname "$LABWC")"
    # XDG autostart (Wayfire / X11 desktops)
    cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Edge inspection dashboard (kiosk)
Exec=bash $REPO/deploy/kiosk.sh run
X-GNOME-Autostart-enabled=true
EOF
    # labwc (current Raspberry Pi OS desktop) reads its own autostart file
    touch "$LABWC"; grep -qF "$LINE" "$LABWC" || echo "$LINE" >> "$LABWC"
    # boot straight into the desktop, logged in, so the monitor shows the dashboard after a power cycle
    if command -v raspi-config >/dev/null; then sudo raspi-config nonint do_boot_behaviour B4 || true; fi
    echo "kiosk installed: reboot to test (sudo reboot). Leave it with Alt+F4." ;;
  remove)
    rm -f "$ENTRY"
    [ -f "$LABWC" ] && sed -i "\#$REPO/deploy/kiosk.sh run#d" "$LABWC"
    echo "kiosk removed (desktop auto-login unchanged: sudo raspi-config -> System -> Boot / Auto Login)" ;;
  *)
    echo "usage: bash deploy/kiosk.sh install|run|remove"; exit 2 ;;
esac
