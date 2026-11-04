"""Dashboard backend: REST + WebSocket + MJPEG camera stream. The web page in static/ is just one client of this API.

  GET  /                     web UI (static/index.html)
  GET  /video.mjpg           live annotated camera view (MJPEG, ~10 FPS)
  GET  /api/health           200 while the station runs, 503 otherwise (container healthcheck)
  GET  /api/stats            runtime status
  GET  /api/kpis             throughput, yield, median latency, headline metric
  GET  /api/parts?n=20       latest parts (verdict, reasons, operator truth)
  POST /api/parts/{id}/truth {"truth": "good"|"defective"}  operator ground truth -> headline metric
  WS   /ws                   pushes a full snapshot every 0.5 s
No endpoint can switch an output or change a setting: the dashboard only observes (+ records operator truth).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .kpis import kpis

STATIC = Path(__file__).parent / "static"


class Truth(BaseModel):
    truth: str


def create_app(rt: Any) -> FastAPI:
    app = FastAPI(title="Edge inspection station", version="1.0")
    motor_hist: deque[dict[str, Any]] = deque(maxlen=240)
    rt.bus.subscribe("motor", lambda t, p: motor_hist.append({"t": p.get("t"), "score": p["score"],
                                                              "alert": p["alert"]}))

    def motor() -> dict[str, Any] | None:
        if rt.motor is None:
            return None
        return {**rt.motor.last, "history": list(motor_hist)[-120:]}

    def parts(n: int) -> list[dict[str, Any]]:
        return [p.to_dict() for p in list(rt.parts)[-n:]][::-1]

    def snapshot() -> dict[str, Any]:
        cur = rt.tracker.current
        return {"ts": time.time(), "stats": rt.stats(), "kpis": kpis(rt), "motor": motor(), "parts": parts(15),
                "live": {"verdict": (rt.last_verdict or {}).get("verdict"), "reasons": (rt.last_verdict or {}).get("reasons", []),
                         "detections": [d.to_dict() for d in rt.last_dets],
                         "part_in_view": cur is not None, "frame_age_s": round(time.perf_counter() - rt.last_frame_t, 2)
                         if rt.last_frame_t else None}}

    @app.get("/api/health")
    def health() -> JSONResponse:
        age = time.perf_counter() - rt.last_frame_t if rt.last_frame_t else None
        ok = rt.state == "running" and age is not None and age < 5
        return JSONResponse({"ok": ok, "state": rt.state, "fps": round(rt.fps.fps, 2),
                             "last_frame_age_s": None if age is None else round(age, 2)}, status_code=200 if ok else 503)

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        return rt.stats()

    @app.get("/api/kpis")
    def get_kpis() -> dict[str, Any]:
        return kpis(rt)

    @app.get("/api/parts")
    def get_parts(n: int = 20) -> list[dict[str, Any]]:
        return parts(min(max(n, 1), 500))

    @app.post("/api/parts/{pid}/truth")
    def set_truth(pid: int, body: Truth) -> dict[str, Any]:
        if body.truth not in ("good", "defective"):
            raise HTTPException(400, "truth must be 'good' or 'defective'")
        for p in rt.parts:
            if p.id == pid:
                p.truth = body.truth
                return p.to_dict()
        raise HTTPException(404, "no such part")

    @app.get("/video.mjpg")
    async def video() -> StreamingResponse:
        async def gen():
            while True:
                img = rt.last_annotated
                if img is not None:
                    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
                await asyncio.sleep(0.1)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        try:
            while True:
                await sock.send_json(snapshot())
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app


def serve_in_thread(rt: Any, cfg: dict[str, Any]):
    import uvicorn

    d = cfg.get("dashboard", {})
    server = uvicorn.Server(uvicorn.Config(create_app(rt), host=d.get("host", "0.0.0.0"), port=d.get("port", 8000),
                                           log_level="warning", access_log=False))
    threading.Thread(target=server.run, name="dashboard", daemon=True).start()
    return server
