# Threat model (M4.7)

System: Raspberry Pi station on the shop-floor LAN → camera + model + relay/LED + MPU6050, Mosquitto broker (TLS),
OpenPLC over Modbus TCP, web dashboard on :8000, OTA model updates.

## One threat per level

| Level | Threat | What could happen | Mitigation | Applied? | Evidence |
|---|---|---|---|---|---|
| **Device** | Someone with shell access (or a stolen SD card) reads the broker password / keys | impersonate the station on MQTT, publish fake PASS results | secrets only in git-ignored `docker/.env`; private keys never committed (`.gitignore`: `*.key`, `certs/`, `passwd`, `.env`); broker stores only salted hashes; read-only `config/` and `models/` mounts in the container | ✅ | `git check-ignore -v docker/.env docker/mosquitto/passwd docker/mosquitto/certs/server.key` → all ignored |
| **Network** | Sniffing or spoofing MQTT on the LAN | read results, inject fake detections, impersonate the broker | **TLS-only listener (no port 1883 at all), no anonymous users, password file, per-user ACL** (`edge` may write only `edge/#`, `monitor` is read-only); client verifies the broker certificate against my own CA | ✅ | `evidence/M4/mqtt_security.json` — 6/6: anonymous refused, wrong password refused, plain TCP refused, impostor CA refused, password+TLS accepted, read-only publish dropped |
| **Application / cloud** | A malicious or corrupted model update (OTA) | the station runs a model that passes defective parts, or crashes | bundle SHA-256 must match the published hash; every file must match the manifest; only listed files are unpacked; health check (recall ≥ 0.9 on reference images, latency budget) before it counts; automatic rollback | ✅ | `evidence/M4/ota.json` — tampered bundle rejected, broken v3 rolled back to v2; `tests/test_ops.py` |
| **Physical / data** | Camera covered, unplugged or blinded; lighting changes the input (deliberately or by a failing lamp) | defective parts pass uninspected; silent accuracy loss | camera watchdog → **safe state: run_permit relay off = conveyor stop** (fail-safe wiring: crash or power cut also stops); drift report on brightness/contrast/sharpness/confidence | ✅ | `evidence/M3/safe_state.json` (stop 1.06 s after camera loss); `evidence/M4/drift_report.json` (failing lamp → DRIFT) |

## Mitigations applied (≥ 2 required): 5
1. MQTT: TLS only + passwords + ACL + broker certificate verification (measured, 6/6).
2. Fail-safe safe state on camera loss (measured, 1.06 s).
3. OTA integrity check + health check + automatic rollback (measured).
4. Secrets kept out of git; only hashes on the broker.
5. Drift monitoring of the camera input.

## Known gaps (accepted for this prototype)
- **Modbus TCP has no authentication.** OpenPLC runs on the same Pi and the station talks to it on `127.0.0.1`;
  on the Pi, block port 502 from the LAN: `sudo ufw default deny incoming && sudo ufw allow 22,8000,8883/tcp && sudo ufw enable`
  (also keeps the OpenPLC web UI on 8080 off the LAN).
- **Dashboard has no login.** It is read-only (no endpoint changes outputs or settings); exposed only on the LAN.
- **Container is privileged** (simplest access to camera/GPIO/I²C). Next step: replace with explicit `devices:` and
  `group_add` for `video`, `gpio`, `i2c`.
- OTA bundles are hashed, not signed: an attacker who can change both the bundle and its `.sha256` is not stopped.
  Next step: sign bundles (e.g. minisign / Ed25519) and keep only the public key on the device.
