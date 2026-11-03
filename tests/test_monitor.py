import numpy as np

from edgevision.monitor import AnomalyModel, feature_names, sliding_windows, window_features

RATE = 200


def signal(rng: np.random.Generator, fault: bool, seconds: float = 20) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    x = np.column_stack([0.02 * np.sin(2 * np.pi * 25 * t + i) + rng.normal(0, 0.008, len(t)) for i in range(6)])
    if fault:
        x += 0.1 * np.sin(2 * np.pi * 25 * t)[:, None]
    return x


def feats(x: np.ndarray) -> np.ndarray:
    return np.array([window_features(w, RATE) for w in sliding_windows(x, RATE, RATE // 2)])


def test_feature_vector_shape() -> None:
    f = window_features(np.zeros((RATE, 6)), RATE)
    assert f.shape == (len(feature_names()),)


def test_threshold_is_percentile_of_normal_scores() -> None:
    rng = np.random.default_rng(0)
    normal = feats(signal(rng, False, 60))
    m = AnomalyModel.fit(normal, percentile=99.0)
    rate = m.is_anomaly(normal).mean()
    assert rate <= 0.02                      # ~1 % of training windows above a 99th-percentile threshold


def test_fault_scores_above_threshold_and_normal_mostly_below(tmp_path) -> None:
    rng = np.random.default_rng(1)
    m = AnomalyModel.fit(feats(signal(rng, False, 60)), calib_feats=feats(signal(rng, False, 30)), percentile=99.5)
    assert m.is_anomaly(feats(signal(rng, True))).mean() > 0.9
    assert m.is_anomaly(feats(signal(rng, False))).mean() < 0.05
    m.save(tmp_path / "m.pkl")
    assert AnomalyModel.load(tmp_path / "m.pkl").threshold == m.threshold
