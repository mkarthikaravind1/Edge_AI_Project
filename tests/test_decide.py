import pytest

from edgevision.decide import Debounce, DecisionEngine, Event
from edgevision.detect import Detection


def det(name: str = "body", conf: float = 0.9) -> Detection:
    return Detection(0, name, conf, (0, 0, 10, 10))


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def engine(clock: Clock, n: int = 3, m: int = 5, cooldown: float = 2.0) -> DecisionEngine:
    return DecisionEngine(["body"], 0.6, n, m, cooldown, camera_timeout_s=1.0, clock=clock)


def test_debounce_single_bad_frame_does_not_fire() -> None:
    d = Debounce(3, 5)
    assert [d.update(h) for h in [False, True, False, False, False]] == [False] * 5


def test_debounce_n_of_m_fires() -> None:
    d = Debounce(3, 5)
    assert [d.update(h) for h in [True, False, True, True]] == [False, False, False, True]


def test_debounce_window_forgets_old_hits() -> None:
    d = Debounce(3, 5)
    for h in [True, True, False, False, False, False, False]:
        d.update(h)
    assert d.hits == 0


def test_debounce_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        Debounce(6, 5)


def test_engine_one_frame_no_trigger_then_n_frames_trigger() -> None:
    c = Clock()
    e = engine(c)
    events = []
    for dets in [[det()], [], [], [], []]:
        c.t += 0.1
        events.append(e.on_frame(dets).event)
    assert Event.TRIGGER not in events
    for _ in range(3):
        c.t += 0.1
        ev = e.on_frame([det()]).event
    assert ev == Event.TRIGGER


def test_engine_low_confidence_and_wrong_class_ignored() -> None:
    c = Clock()
    e = engine(c, n=1, m=1)
    assert e.on_frame([det(conf=0.5)]).event == Event.NONE
    assert e.on_frame([det(name="lid")]).event == Event.NONE
    assert e.on_frame([det(conf=0.6)]).event == Event.TRIGGER


def test_engine_cooldown_blocks_retrigger() -> None:
    c = Clock()
    e = engine(c, n=1, m=1, cooldown=2.0)
    assert e.on_frame([det()]).event == Event.TRIGGER
    c.t += 1.0
    assert e.on_frame([det()]).event == Event.COOLDOWN
    c.t += 1.5
    assert e.on_frame([det()]).event == Event.TRIGGER


def test_camera_loss_enters_safe_state_once_and_recovers() -> None:
    c = Clock()
    e = engine(c)
    e.on_frame([])
    c.t += 0.5
    assert e.check_camera() is None
    c.t += 0.6
    assert e.check_camera().event == Event.SAFE_STATE
    assert e.check_camera() is None          # reported once only
    assert e.on_frame([det()]).event == Event.RECOVERED
    assert not e.safe
