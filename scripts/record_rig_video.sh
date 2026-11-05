#!/usr/bin/env bash
# Record raw webcam clips on the rig for retraining the detector (M1 dataset v2 with the real camera + background).
#   bash scripts/record_rig_video.sh good_placements 60      # <name> <seconds>
#   bash scripts/record_rig_video.sh list                    # what is recorded so far
# Saves the webcam's own MJPG stream without re-encoding (no dropped frames on the Pi) to
#   data/raw/videos/rig_<name>_<time>.avi   (git-ignored: copy them to the laptop, see the end of this script)
# Suggested clips (60 s each, move the part between positions while recording, keep hands out as much as you can):
#   enclosure  - closed box, many placements and rotations      body - open body (Model 1) alone
#   lid        - loose lid alone                                 mixed - body + lid apart, lid half on, etc.
#   defects    - marked / chipped / lid missing / lid not seated parts
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=data/raw/videos; mkdir -p "$OUT"
if [ "${1:-}" = "list" ]; then ls -lh "$OUT"/rig_* 2>/dev/null || echo "no rig clips yet"; exit 0; fi
NAME="${1:?usage: bash scripts/record_rig_video.sh <name> [seconds]}"; SECS="${2:-60}"
command -v ffmpeg >/dev/null || sudo apt-get install -y ffmpeg

# only one program can hold the webcam: stop the station if it is running
docker ps --format '{{.Names}}' 2>/dev/null | grep -qx edge && { echo "(stopping the station to free the webcam)"; docker stop edge >/dev/null; }
systemctl is-active --quiet edge-station 2>/dev/null && sudo systemctl stop edge-station

DEV="$(ls /dev/v4l/by-id/*-video-index0 2>/dev/null | head -1)"; DEV="${DEV:-/dev/video0}"
FILE="$OUT/rig_${NAME}_$(date +%Y%m%d_%H%M%S).avi"
echo "camera $DEV -> $FILE  (${SECS}s). Starts in 3 s..."; sleep 3
ffmpeg -hide_banner -loglevel warning -stats -f v4l2 -input_format mjpeg -video_size 640x480 -framerate 30 \
       -i "$DEV" -t "$SECS" -c:v copy "$FILE"
echo "saved $FILE ($(du -h "$FILE" | cut -f1))"
cat <<EOF
Next (on the LAPTOP, same Wi-Fi):
  scp $(id -un)@$(hostname).local:$(pwd)/$OUT/rig_*.avi data/raw/videos/
  python scripts/extract_frames.py --video data/raw/videos/rig_*.avi --fps 3
then autolabel.py -> review_labels.py (review EVERY frame yourself) -> split.py -> train_colab.ipynb -> export.py
EOF
