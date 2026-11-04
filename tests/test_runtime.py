import time

import numpy as np

from edgevision.config import load_config
from edgevision.detect.base import Detection, Detector
from edgevision.hal import ConsoleActuator, FakeCamera, FakePlc, FlakyCamera
from edgevision.runtime import StationRuntime


class StubDetector(Detector):
    """Sees an enclosure in every frame."""

    def __init__(self) -> None:
        super().__init__(["enclosure", "body", "lid"])

    def detect(self, image: np.ndarray) -> list[Detection]:
        return [Detection(0, "enclosure", 0.9, (10, 10, 100, 100))]


def make(camera, plc=None) -> StationRuntime:
    cfg = load_config("laptop")
    cfg["decide"]["camera_timeout_s"] = 0.3
    return StationRuntime(cfg, camera, StubDetector(), ConsoleActuator("reject", True),
                          ConsoleActuator("run_permit", True), plc=plc, keep_annotated=False)


def test_runtime_triggers_once_and_writes_plc() -> None:
    plc = FakePlc()
    rt = make(FakeCamera(64, 48), plc)
    events = []
    rt.bus.subscribe("decision", lambda t, p: events.append(p["event"]))
    rt.run_for(0.8)
    assert rt.frames > 10
    assert events.count("trigger") == 1           # part never leaves -> one trigger
    assert plc.read_register(0) == 1
    assert rt.latencies and rt.latencies[0]["frame_to_cmd_ms"] >= 0
    assert rt.run_permit.state is False           # stop() leaves the line in the safe state


def test_camera_loss_enters_safe_state_then_recovers() -> None:
    rt = make(FlakyCamera(FakeCamera(64, 48), drop_at_s=0.3, resume_at_s=1.2))
    events = []
    rt.bus.subscribe("decision", lambda t, p: events.append(p["event"]))
    rt.start()
    time.sleep(0.25)
    assert rt.run_permit.state is True            # healthy -> conveyor allowed
    time.sleep(0.7)                               # camera dead for > 0.3 s
    assert rt.state == "SAFE_STATE" and rt.run_permit.state is False
    time.sleep(0.6)                               # camera back
    rt.stop()
    assert "safe_state" in events and "recovered" in events
