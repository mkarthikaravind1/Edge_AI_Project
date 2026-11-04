"""Tiny in-process publish/subscribe bus. The runtime publishes; MQTT, the dashboard and the logger subscribe.

Keeps the core loop decoupled: it never imports MQTT or FastAPI, it only calls bus.publish(topic, payload).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)
Handler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, topic: str, handler: Handler) -> None:
        """topic "*" receives everything."""
        with self._lock:
            self._subs[topic].append(handler)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        with self._lock:
            handlers = list(self._subs.get(topic, [])) + list(self._subs.get("*", []))
        for h in handlers:
            try:
                h(topic, payload)
            except Exception:          # one broken subscriber must never stop the inspection loop
                log.exception("bus subscriber failed on %s", topic)
