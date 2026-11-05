import time

from edgevision.config import load_config
from edgevision.hal import ConsoleActuator, CsvReplayImu, FakeCamera, FakePlc, make_actuator, make_camera, make_plc


def test_configs_load() -> None:
    for target in ("laptop", "pi"):
        cfg = load_config(target)
        assert cfg["classes"] == ["enclosure", "body", "lid"]
        assert cfg["decide"]["n"] <= cfg["decide"]["m"]


def test_fake_camera_frames_and_failure() -> None:
    cam = FakeCamera(320, 240, fail_after=3)
    frames = [cam.read() for _ in range(5)]
    assert [f is not None for f in frames] == [True, True, True, False, False]
    assert frames[0].image.shape == (240, 320, 3)
    assert frames[1].t_capture >= frames[0].t_capture


def test_make_camera_fake() -> None:
    assert make_camera({"type": "fake", "width": 64, "height": 48}).read().image.shape == (48, 64, 3)


def test_pi_config_uses_usb_webcam_and_a_second_stream_that_exists_in_git() -> None:
    cfg = load_config("pi")
    assert cfg["camera"]["type"] == "webcam"
    assert cfg["camera2"]["type"] == "images"
    from edgevision.config import resolve
    assert any(resolve(cfg["camera2"]["path"]).glob("*.jpg"))       # committed test frames, present on the Pi


def test_image_folder_camera_loops(tmp_path) -> None:
    import cv2
    import numpy as np
    for i in range(3):
        cv2.imwrite(str(tmp_path / f"f{i}.jpg"), np.full((40, 60, 3), 50 * i, np.uint8))
    cam = make_camera({"type": "images", "path": str(tmp_path), "fps": 30}, realtime=False)
    frames = [cam.read() for _ in range(7)]
    assert all(f is not None and f.image.shape == (40, 60, 3) for f in frames)
    assert frames[3].image.mean() == frames[0].image.mean()            # wrapped around after 3 images


def test_resolve_webcam() -> None:
    from edgevision.hal import resolve_webcam
    assert resolve_webcam(1) == 1 and resolve_webcam("2") == 2 and resolve_webcam("/dev/video4") == "/dev/video4"
    assert resolve_webcam("auto") in (0,) or str(resolve_webcam("auto")).startswith("/dev/v4l/by-id/")


def test_console_actuator_pulse(capsys) -> None:
    a = make_actuator({"type": "console"})
    assert isinstance(a, ConsoleActuator)
    a.pulse(0.05, "test")
    assert a.state
    time.sleep(0.15)
    assert not a.state
    assert [h[1].split()[0] for h in a.history] == ["ON", "OFF"]
    assert "ON  (energised)" in capsys.readouterr().out


def test_fake_plc_roundtrip() -> None:
    p = make_plc({"type": "fake"})
    assert isinstance(p, FakePlc)
    p.write_coil(0, True)
    p.write_register(0, 70000)
    assert p.read_coil(0) is True
    assert p.read_register(0) == 70000 & 0xFFFF


def test_csv_replay_imu(tmp_path) -> None:
    f = tmp_path / "run.csv"
    f.write_text("t,ax,ay,az,gx,gy,gz\n0,0,0,1,0,0,0\n0.005,0.1,0,1,0,0,0\n")
    imu = CsvReplayImu(str(f))
    assert imu.read().az == 1.0
    assert imu.read().ax == 0.1
    assert imu.read() is None
