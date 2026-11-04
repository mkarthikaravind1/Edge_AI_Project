import time

from fastapi.testclient import TestClient

from edgevision.dashboard.server import create_app
from edgevision.decide.parts import Part
from tests.test_runtime import StubDetector
from edgevision.config import load_config
from edgevision.hal import ConsoleActuator, FakeCamera
from edgevision.runtime import StationRuntime


def runtime_with_parts() -> StationRuntime:
    rt = StationRuntime(load_config("laptop"), FakeCamera(64, 48), StubDetector(), ConsoleActuator("r", True),
                        ConsoleActuator("p", True), keep_annotated=False)
    now = time.time()
    for i, (res, truth) in enumerate([("PASS", "good"), ("FAIL", "defective"), ("PASS", "defective")], 1):
        p = Part(i, now - 5)
        p.result, p.t_end, p.truth = res, now, truth
        rt.parts.append(p)
    rt.latencies.append({"frame_to_cmd_ms": 5.0, "first_hit_to_cmd_ms": 80.0})
    return rt


def test_kpis_headline_and_truth_endpoint() -> None:
    rt = runtime_with_parts()
    c = TestClient(create_app(rt))
    k = c.get("/api/kpis").json()
    assert k["headline"]["text"] == "2/3 correct"
    assert k["headline"]["false_pass_rate"] == 0.5           # 1 of 2 defective parts passed
    assert k["yield_pct"] == 66.7 and k["median_latency_ms"] == 80.0
    r = c.post("/api/parts/3/truth", json={"truth": "good"})
    assert r.status_code == 200 and r.json()["correct"] is True
    assert c.get("/api/kpis").json()["headline"]["text"] == "3/3 correct"
    assert c.post("/api/parts/3/truth", json={"truth": "maybe"}).status_code == 400


def test_health_and_websocket_snapshot() -> None:
    rt = runtime_with_parts()
    c = TestClient(create_app(rt))
    assert c.get("/api/health").status_code == 503             # not started -> unhealthy
    with c.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
    assert {"stats", "kpis", "parts", "live", "motor"} <= set(snap) and len(snap["parts"]) == 3
    assert c.get("/").status_code == 200 and "Edge Inspection" in c.get("/").text
