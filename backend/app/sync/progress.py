"""Thread → asyncio progress fan-out for Server-Sent Events.

The sync engine runs in a worker thread (garminconnect is blocking). Each SSE
client owns an `asyncio.Queue`; `publish()` schedules `put_nowait` on the
client's event loop via `call_soon_threadsafe`, so the worker never touches
asyncio objects directly.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SyncState:
    run_id: int | None = None
    mode: str | None = None          # initial | delta | manual
    status: str = "idle"             # idle | running | ok | error | cancelled
    phase: str | None = None         # range | daily | activities | finalize
    message: str = ""
    current_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    days_total: int = 0
    days_done: int = 0
    activities_total: int = 0
    activities_new: int = 0
    activities_done: int = 0
    errors: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    recent_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # camelCase for the frontend
        return {
            "runId": d["run_id"], "mode": d["mode"], "status": d["status"], "phase": d["phase"],
            "message": d["message"], "currentDate": d["current_date"], "startDate": d["start_date"],
            "endDate": d["end_date"], "daysTotal": d["days_total"], "daysDone": d["days_done"],
            "activitiesTotal": d["activities_total"], "activitiesNew": d["activities_new"],
            "activitiesDone": d["activities_done"], "errors": d["errors"], "startedAt": d["started_at"],
            "finishedAt": d["finished_at"], "error": d["error"], "recentLog": d["recent_log"],
        }


class SyncBroker:
    def __init__(self, log_size: int = 50):
        self._lock = threading.Lock()
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = {}
        self._next_id = 1
        self.state = SyncState()
        self._log: deque[str] = deque(maxlen=log_size)

    # ---------------------------------------------------------- subscribers
    def subscribe(self) -> tuple[int, asyncio.Queue]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            self._subscribers[sid] = (loop, queue)
        return sid, queue

    def unsubscribe(self, sid: int) -> None:
        with self._lock:
            self._subscribers.pop(sid, None)

    # -------------------------------------------------------------- publish
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            d = self.state.to_dict()
            d["recentLog"] = list(self._log)
            return d

    def update(self, event_type: str = "progress", log_line: str | None = None, **changes: Any) -> None:
        with self._lock:
            for k, v in changes.items():
                setattr(self.state, k, v)
            if log_line:
                self._log.append(log_line)
            payload = self.state.to_dict()
            payload["recentLog"] = list(self._log)[-10:]
            payload["type"] = event_type
            subscribers = list(self._subscribers.values())
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(self._safe_put, queue, payload)
            except RuntimeError:
                pass  # loop closed

    @staticmethod
    def _safe_put(queue: asyncio.Queue, payload: dict[str, Any]) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(payload)

    def log(self, line: str) -> None:
        self.update("log", log_line=line, message=line)
