"""Create random passwords for the MQTT users and the hashed Mosquitto password file.

    python docker/mosquitto/make_passwd.py
-> docker/.env              MQTT_PASSWORD=... (edge), MQTT_MONITOR_PASSWORD=... (monitor)   [git-ignored]
-> docker/mosquitto/passwd  hashed with mosquitto_passwd (run inside the official image)     [git-ignored]

Plain-text passwords exist only in docker/.env on this machine; the broker only stores salted hashes.
"""

from __future__ import annotations

import secrets
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "eclipse-mosquitto:2.0.20"


def main() -> None:
    env_path = HERE.parent / ".env"
    env = {}
    if env_path.exists():
        env = dict(l.split("=", 1) for l in env_path.read_text().splitlines() if "=" in l)
    env.setdefault("MQTT_PASSWORD", secrets.token_urlsafe(18))
    env.setdefault("MQTT_MONITOR_PASSWORD", secrets.token_urlsafe(18))
    env_path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))

    passwd = HERE / "passwd"
    passwd.write_text("")
    for user, key in (("edge", "MQTT_PASSWORD"), ("monitor", "MQTT_MONITOR_PASSWORD")):
        subprocess.run(["docker", "run", "--rm", "-v", f"{HERE}:/work", IMAGE,
                        "mosquitto_passwd", "-b", "/work/passwd", user, env[key]], check=True)
    users = [l.split(":")[0] for l in passwd.read_text().splitlines() if l]
    print(f"passwd written for {users}; passwords in {env_path} (git-ignored)")


if __name__ == "__main__":
    main()
