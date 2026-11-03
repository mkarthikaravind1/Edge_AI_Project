"""Anomaly model trained on NORMAL data only (pure numpy, runs anywhere).

Features are log-compressed (energies are heavy-tailed), standardised with the normal mean/std, and scored
by Mahalanobis distance to the normal cloud: "how many standard deviations away from normal, taking
correlated features into account". The alarm threshold is a percentile of the scores on normal windows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AnomalyModel:
    mean: np.ndarray
    std: np.ndarray
    inv_cov: np.ndarray
    threshold: float
    percentile: float

    @staticmethod
    def _prep(feats: np.ndarray) -> np.ndarray:
        return np.log1p(np.abs(np.atleast_2d(feats)))

    @classmethod
    def fit(cls, normal_feats: np.ndarray, calib_feats: np.ndarray | None = None,
            percentile: float = 99.5, shrink: float = 1.0) -> "AnomalyModel":
        """shrink=1 -> diagonal model (per-feature z-scores), the robust default with few windows;
        shrink<1 mixes in feature correlations, which overfits unless there are many more windows than features.
        calib_feats: windows from a HELD-OUT normal run; the threshold is set on them because
        training windows always look more 'normal' than new data."""
        x = cls._prep(normal_feats)
        mean, std = x.mean(0), x.std(0) + 1e-9
        z = (x - mean) / std
        cov = np.cov(z, rowvar=False)
        cov = (1 - shrink) * cov + shrink * np.eye(cov.shape[0])
        m = cls(mean, std, np.linalg.inv(cov), 0.0, percentile)
        ref = normal_feats if calib_feats is None else calib_feats
        m.threshold = float(np.percentile(m.score(ref), percentile))
        return m

    def score(self, feats: np.ndarray) -> np.ndarray:
        z = (self._prep(feats) - self.mean) / self.std
        return np.sqrt(np.einsum("ij,jk,ik->i", z, self.inv_cov, z))

    def is_anomaly(self, feats: np.ndarray) -> np.ndarray:
        return self.score(feats) > self.threshold

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"mean": self.mean.tolist(), "std": self.std.tolist(),
                                          "inv_cov": self.inv_cov.tolist(), "threshold": self.threshold,
                                          "percentile": self.percentile}))

    @staticmethod
    def load(path: str | Path) -> "AnomalyModel":
        d = json.loads(Path(path).read_text())
        return AnomalyModel(np.array(d["mean"]), np.array(d["std"]), np.array(d["inv_cov"]),
                            d["threshold"], d["percentile"])
