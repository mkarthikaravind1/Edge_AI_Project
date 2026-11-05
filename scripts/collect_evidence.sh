#!/usr/bin/env bash
# Put everything this Pi produced for the assessment into ONE zip, to copy to the laptop and commit there.
#   bash scripts/collect_evidence.sh
# Only files that are NEW or CHANGED since the repo was cloned (git decides), in these folders:
#   evidence/  data/rig/  data/imu/real/  data/raw/videos/ (rig training clips)  models/inspection.json  models/anomaly.json
# No git login, no personal data: the Pi never commits or pushes.
set -euo pipefail
cd "$(dirname "$0")/.."
PATHS=(evidence data/rig data/imu/real data/raw/videos models/inspection.json models/anomaly.json)
LIST="$(mktemp)"
# -m modified tracked files, -o untracked files INCLUDING git-ignored ones (videos), so nothing is missed
git ls-files -m -o -- "${PATHS[@]}" 2>/dev/null | grep -v '/\.gitkeep$' | sort -u > "$LIST" || true
N=$(wc -l < "$LIST")
[ "$N" -gt 0 ] || { echo "nothing new yet: run a milestone first"; exit 0; }
OUT="$HOME/edge_evidence_$(hostname)_$(date +%Y%m%d_%H%M).zip"
python3 - "$OUT" "$LIST" <<'PY'
import sys, zipfile
out, lst = sys.argv[1], sys.argv[2]
files = [l.strip() for l in open(lst) if l.strip()]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, f)            # same paths as in the repo: unzip into the project folder on the laptop
print(f"{len(files)} files")
PY
echo "zip: $OUT ($(du -h "$OUT" | cut -f1))"
sed 's/^/  /' "$LIST" | head -60; [ "$N" -gt 60 ] && echo "  ... ($N files)"
rm -f "$LIST"
IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
cat <<EOF

Copy it to the LAPTOP (pick one):
  a) laptop PowerShell, same Wi-Fi:   scp $(id -un)@$(hostname).local:$OUT .
                                      (or  scp $(id -un)@$IP:$OUT .)
  b) USB stick: plug it into the Pi, open the file manager, copy $OUT onto it
Then on the laptop, in the project folder:  tar -xf $(basename "$OUT")   (puts every file in its place)
                                            git add -A evidence data/rig data/imu/real models
                                            git add -f evidence/*/*.mp4   (videos < 50 MB each)
                                            git commit -m "M1..: Pi evidence" && git push
Phone photos/videos: copy them from the phone to the laptop (USB cable / Google Photos download at full
quality), into evidence/M1..M5/, then commit. Avoid WhatsApp: it compresses photos and videos.
EOF
