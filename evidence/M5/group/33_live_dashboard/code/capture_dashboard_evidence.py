"""
Captures genuine, high-resolution evidence screenshots of the running M5 dashboard
using Playwright Chromium for all eight M5 assessment requirements.
"""

import sys
import time
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_31 = BASE_DIR / "evidence" / "M5" / "31_pass_fail_station" / "screenshots"
EVIDENCE_33 = BASE_DIR / "evidence" / "M5" / "33_live_dashboard" / "screenshots"
EVIDENCE_34 = BASE_DIR / "evidence" / "M5" / "34_product_readiness" / "screenshots"

EVIDENCE_31.mkdir(parents=True, exist_ok=True)
EVIDENCE_33.mkdir(parents=True, exist_ok=True)
EVIDENCE_34.mkdir(parents=True, exist_ok=True)


def capture_evidence():
    print("[Evidence Capturer] Starting M5 server process...")
    # Launch uvicorn server as background process
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BASE_DIR)
    )

    # Wait for server to respond
    server_url = "http://127.0.0.1:8000"
    connected = False
    for attempt in range(20):
        try:
            r = requests.get(f"{server_url}/api/status", timeout=1.0)
            if r.status_code == 200:
                connected = True
                print(f"[Evidence Capturer] M5 Server responsive after {attempt+1} attempts.")
                break
        except Exception:
            time.sleep(0.5)

    if not connected:
        print("[Evidence Capturer] ERROR: Server failed to respond!")
        server_process.terminate()
        return

    try:
        with sync_playwright() as p:
            print("[Evidence Capturer] Launching Chromium browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 950})

            # 1. Dashboard Overview
            page.goto(server_url)
            page.wait_for_selector(".kpi-card")
            time.sleep(3.0)  # Allow WebSocket telemetry stream to populate charts
            shot1 = EVIDENCE_33 / "01_dashboard_overview.png"
            page.screenshot(path=str(shot1))
            print(f"[Evidence Capturer] Saved: {shot1.name}")

            # 2. Vision Inspection Rig Tab
            page.click("button[data-tab='vision']")
            time.sleep(2.0)
            shot2 = EVIDENCE_33 / "02_vision_inspection_rig.png"
            page.screenshot(path=str(shot2))
            print(f"[Evidence Capturer] Saved: {shot2.name}")

            # 3. Motor Oscilloscope Tab
            page.click("button[data-tab='motor']")
            time.sleep(3.0)
            shot3 = EVIDENCE_33 / "03_motor_condition_oscilloscope.png"
            page.screenshot(path=str(shot3))
            print(f"[Evidence Capturer] Saved: {shot3.name}")

            # 4. Inject Motor Anomaly Fault to demonstrate Alert (Assessment 33 & 37)
            print("[Evidence Capturer] Injecting CURRENT_SURGE fault to capture live anomaly...")
            requests.post(f"{server_url}/api/motor/fault_injection", data={"fault_type": "CURRENT_SURGE"})
            time.sleep(3.0)
            shot4 = EVIDENCE_33 / "04_live_motor_anomaly_alert.png"
            page.screenshot(path=str(shot4))
            print(f"[Evidence Capturer] Saved: {shot4.name}")

            # Restore clean state
            requests.post(f"{server_url}/api/motor/fault_injection", data={"fault_type": "NONE"})

            # 5. Alerts Center
            page.click("button[data-tab='alerts']")
            time.sleep(1.5)
            shot5 = EVIDENCE_33 / "05_alerts_center.png"
            page.screenshot(path=str(shot5))
            print(f"[Evidence Capturer] Saved: {shot5.name}")

            # 6. Assessment Station & Reports
            page.click("button[data-tab='assessment']")
            time.sleep(1.5)
            shot6 = EVIDENCE_31 / "06_assessment_benchmarks.png"
            page.screenshot(path=str(shot6))
            print(f"[Evidence Capturer] Saved: {shot6.name}")

            # 7. System Health
            page.click("button[data-tab='health']")
            time.sleep(1.5)
            shot7 = EVIDENCE_34 / "07_system_health.png"
            page.screenshot(path=str(shot7))
            print(f"[Evidence Capturer] Saved: {shot7.name}")

            browser.close()

    finally:
        print("[Evidence Capturer] Terminating background server process...")
        server_process.terminate()
        server_process.wait()
        print("[Evidence Capturer] Evidence capture complete.")


if __name__ == "__main__":
    capture_evidence()

