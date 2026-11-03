"""IMU window -> feature vector: RMS, peak and FFT band energies per axis."""

from __future__ import annotations

import numpy as np

AXES = ["ax", "ay", "az", "gx", "gy", "gz"]
BANDS_HZ = [(0, 5), (5, 20), (20, 50), (50, 100)]


def feature_names() -> list[str]:
    names = []
    for a in AXES:
        names += [f"{a}_rms", f"{a}_peak"] + [f"{a}_band_{lo}_{hi}" for lo, hi in BANDS_HZ]
    return names


def window_features(win: np.ndarray, rate_hz: float) -> np.ndarray:
    """win: (samples, 6) in AXES order. Mean is removed per axis so gravity does not dominate."""
    x = win - win.mean(axis=0, keepdims=True)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / rate_hz)
    spec = np.abs(np.fft.rfft(x, axis=0)) ** 2 / len(x)
    feats = []
    for i in range(x.shape[1]):
        col = x[:, i]
        feats += [float(np.sqrt(np.mean(col ** 2))), float(np.max(np.abs(col)))]
        for lo, hi in BANDS_HZ:
            m = (freqs >= lo) & (freqs < hi)
            feats.append(float(spec[m, i].sum()))
    return np.array(feats)


def sliding_windows(data: np.ndarray, size: int, step: int) -> list[np.ndarray]:
    return [data[i:i + size] for i in range(0, len(data) - size + 1, step)]
