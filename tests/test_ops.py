from pathlib import Path

from edgevision.monitor import AlertDebounce
from edgevision.ops import ota


def test_alert_debounce_needs_n_in_a_row() -> None:
    d = AlertDebounce(2)
    assert [d.update(x) for x in [True, False, True, True, True, False, False]] == \
        [None, None, None, "alert", None, None, "clear"]


def test_ota_install_upgrade_rollback_and_tamper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ota, "RELEASES", tmp_path / "releases")
    monkeypatch.setattr(ota, "ROOT", tmp_path)
    good = tmp_path / "good.bin"
    good.write_bytes(b"good model")
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"broken")
    bundles = tmp_path / "bundles"
    b1 = ota.build_bundle("v1", good, bundles)
    b2 = ota.build_bundle("v2", good, bundles, overlay={"detector": {"threads": 2}})
    b3 = ota.build_bundle("v3", bad, bundles)
    health = lambda cfg: {"ok": cfg["detector"]["model"].endswith("good.bin"), "reason": "test"}
    cfg = {"detector": {"model": "x", "threads": 4}}

    assert ota.install(b1, cfg, health)["result"] == "installed v1"
    assert ota.install(b2, cfg, health)["result"] == "installed v2"
    assert ota.apply_current_release(cfg)["detector"]["threads"] == 2          # overlay applied
    assert ota.install(b3, cfg, health)["result"].startswith("rolled back to v2")
    assert ota.current_version() == "v2"

    data = bytearray(b2.read_bytes())
    data[len(data) // 2] ^= 0xFF
    b2.write_bytes(bytes(data))                                               # tampered after publication
    rep = ota.install(b2, cfg, health)
    assert rep["result"].startswith("rejected") and ota.current_version() == "v2"
