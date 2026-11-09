# M5 — Complete System + Dashboard: evidence index

Every M5 checklist item, the number that proves it, and the exact files. Files stay flat in this folder because the
scripts write them here; this page is the map.

**Where it ran:** 💻 = measured on the laptop · ⏳ Pi = Pi run pending ([PI_CHECKLIST § M5](../../docs/PI_CHECKLIST.md#m5--complete-system-on-the-pi)).

| # | Criterion | Result | Evidence | Where |
|---|---|---|---|---|
| 5.1 | Inspection rig | Fixed camera at 30–45°, matte base, end stop, diffused lamp (design); stand-in images until the rig is built | [RIG](../../docs/RIG.md), stand-in set [data/rig_sim/contact_sheet.jpg](../../data/rig_sim/contact_sheet.jpg) | ⏳ rig photo |
| 5.2 | Pass/fail station | Stand-in test **16/20**, false-pass **0.30** (target ≤ 0.10 **not met yet**); marks and lid-missing caught, chips not | [passfail.json](passfail.json), [passfail_results.csv](passfail_results.csv), [passfail_confusion.png](passfail_confusion.png), [passfail_sheet.jpg](passfail_sheet.jpg), [inspection_calibration.json](inspection_calibration.json), first attempt [passfail_v1_before_fixes.json](passfail_v1_before_fixes.json) · [DEFECTS](../../docs/DEFECTS.md) | 💻 stand-in, ⏳ rig |
| 5.3 | Full chain | 10 min: **30.0 FPS**, 0 errors, 171/172 parts tracked, 1858 MQTT msgs (0 schema failures), part → reject p95 90 ms | [full_chain_laptop.json](full_chain_laptop.json), [full_chain_mqtt_laptop.json](full_chain_mqtt_laptop.json) | 💻 simulated conveyor, ⏳ Pi |
| 5.4 | Dashboard | Live camera + boxes, PASS/FAIL, headline, 3 KPIs, motor card, parts feed; works offline; desktop and phone | [dashboard_desktop_laptop.jpg](dashboard_desktop_laptop.jpg), [dashboard_phone_laptop.jpg](dashboard_phone_laptop.jpg), code [dashboard/](../../src/edgevision/dashboard/server.py) | 💻, ⏳ Pi |
| 5.5 | Product readiness | **7/7** static checks (offline UI, local broker, model on device, auto-start, log rotation, healthcheck) | [readiness_laptop.json](readiness_laptop.json), [docker_healthy_laptop.txt](docker_healthy_laptop.txt) | 💻, ⏳ Pi power-cycle + offline |
| 5.6 | Headline metric | Parts classified correctly / parts checked, with false-pass rate next to it: 16/20 on the stand-in set (target ≥ 18/20) | [passfail.json](passfail.json), `GET /api/kpis` in [kpis.py](../../src/edgevision/dashboard/kpis.py) | 💻 stand-in, ⏳ rig |
| — | Datasheet, demo script | One-page datasheet; timed live-demo script and video shot list | [DATASHEET](../../docs/DATASHEET.md), [DEMO](../../docs/DEMO.md) | ⏳ demo video |

## Code that produced it
| # | Script |
|---|---|
| 5.1 | [make_sim_rig.py](../../scripts/make_sim_rig.py), [capture_rig.py](../../scripts/capture_rig.py) |
| 5.2 | [inspect.py](../../src/edgevision/inspect.py), [calibrate_inspection.py](../../scripts/calibrate_inspection.py), [passfail_test.py](../../scripts/passfail_test.py) |
| 5.3 | [station_sim.py](../../scripts/station_sim.py) |
| 5.5 | [readiness_check.py](../../scripts/readiness_check.py) |

## Honest limits
- Pass/fail is measured on stand-in images with **simulated** marks/chips; the method was changed once after the first
  result, so 16/20 is optimistic. The rig test on the Pi is the honest number.

More: [VIVA_NOTES § M5](../../docs/VIVA_NOTES.md#m5-complete-system--dashboard) · all numbers: [RESULTS § M5](../../docs/RESULTS.md#m5)
