"""Draw the software stack (camera -> ... -> hardware) for laptop and Pi side by side -> docs/stack.png.

    python scripts/draw_stack.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
LAYERS = [  # (layer, laptop, raspberry pi)
    ("Application", "edgevision: pipeline, decide, dashboard", "edgevision: pipeline, decide, dashboard"),
    ("Camera API", "OpenCV VideoCapture (webcam / video file)", "Picamera2 (libcamera) / OpenCV for USB cam"),
    ("Pre-\nprocessing", "OpenCV: letterbox 320x320, BGR->RGB, /255", "OpenCV: letterbox 320x320, BGR->RGB, /255"),
    ("Runtime", "PyTorch FP32 | ONNX Runtime FP32 | TFLite", "TFLite INT8 (LiteRT) | ONNX Runtime"),
    ("Delegate /\naccelerator", "CPU (MLAS / XNNPACK)", "CPU XNNPACK (Coral: libedgetpu / Hailo: HailoRT)"),
    ("OS", "Windows 11, Python 3.12", "Raspberry Pi OS 64-bit (Linux), Python 3.11, Docker"),
    ("Hardware", "Laptop x86-64 CPU", "Broadcom Arm Cortex-A CPU (+ optional NPU/TPU)"),
]
COLOURS = ["#4C78A8", "#72B7B2", "#54A24B", "#EECA3B", "#F58518", "#B279A2", "#9D755D"]


def main() -> None:
    fig, ax = plt.subplots(figsize=(13, 7.5))
    ax.set_xlim(0, 13.4)
    ax.set_ylim(0, len(LAYERS) + 1.2)
    ax.axis("off")
    ax.text(4.2, len(LAYERS) + 0.6, "Laptop (development)", ha="center", fontsize=13, weight="bold")
    ax.text(10.0, len(LAYERS) + 0.6, "Raspberry Pi (edge device)", ha="center", fontsize=13, weight="bold")
    for i, (layer, lap, pi) in enumerate(LAYERS):
        y = len(LAYERS) - 1 - i
        c = COLOURS[i]
        ax.text(0.1, y + 0.45, layer, va="center", fontsize=11, weight="bold")
        for x, txt in ((1.9, lap), (7.7, pi)):
            ax.add_patch(FancyBboxPatch((x, y + 0.1), 4.6, 0.7, boxstyle="round,pad=0.02", fc=c, ec="black", alpha=0.85))
            ax.text(x + 2.3, y + 0.45, txt, ha="center", va="center", fontsize=9.5, color="black")
        if i < len(LAYERS) - 1:
            for x in (4.2, 10.0):
                ax.annotate("", (x, y + 0.05), (x, y - 0.12), arrowprops=dict(arrowstyle="<-", lw=1.2))
    ax.set_title("Software stack: frame flows top -> bottom, detections flow back up", fontsize=12)
    out = ROOT / "docs/stack.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
