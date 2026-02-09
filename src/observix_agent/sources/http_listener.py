from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request, Response

from observix_agent.events import Event
from observix_agent.sources.base import Source


class HttpListenerSource(Source):
    """Receives events over HTTP and exposes them via poll()."""

    def __init__(
        self,
        host: str,
        port: int,
        path: str = "/ingest",
        max_queue_size: int = 50000,
    ) -> None:
        self._host = host
        self._port = port
        self._path = path if path.startswith("/") else f"/{path}"
        self._queue: Queue[Event] = Queue(maxsize=max_queue_size)
        self._app = FastAPI(title="Observix Agent HTTP Ingest", version="0.1.0")
        self._server: uvicorn.Server | None = None
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._register_routes()
        self._thread.start()

    def _register_routes(self) -> None:
        async def ingest(request: Request) -> Response:
            content_type = (request.headers.get("content-type") or "").lower()
            body = await request.body()
            if not body:
                return Response(status_code=400, content="empty body")

            events: List[Event] = []
            if "application/json" in content_type:
                try:
                    payload = json.loads(body.decode("utf-8", errors="ignore"))
                except Exception:
                    return Response(status_code=400, content="invalid json")

                if isinstance(payload, list):
                    for item in payload:
                        evt = self._event_from_item(item, request)
                        if evt is not None:
                            events.append(evt)
                else:
                    evt = self._event_from_item(payload, request)
                    if evt is not None:
                        events.append(evt)
            else:
                raw = body.decode("utf-8", errors="ignore").strip()
                if raw:
                    events.append(
                        Event(
                            ts=datetime.now(timezone.utc),
                            raw=raw,
                            meta=self._meta_from_request(request),
                        )
                    )

            accepted = 0
            for evt in events:
                try:
                    self._queue.put_nowait(evt)
                    accepted += 1
                except Exception:
                    break

            if accepted == 0:
                return Response(status_code=429, content="queue full")

            return Response(status_code=202, content=f"accepted={accepted}")

        self._app.add_api_route(self._path, ingest, methods=["POST"])
        self._app.add_api_route("/v1/health", lambda: {"ok": True}, methods=["GET"])

    def _meta_from_request(self, request: Request) -> Dict[str, Any]:
        return {
            "source": "http_listener",
            "path": self._path,
            "client": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

    def _event_from_item(self, item: Any, request: Request) -> Optional[Event]:
        meta = self._meta_from_request(request)
        if isinstance(item, str):
            raw = item.strip()
            if not raw:
                return None
            return Event(ts=datetime.now(timezone.utc), raw=raw, meta=meta)
        if isinstance(item, dict):
            raw = None
            structured: Dict[str, Any] = {}
            if "raw" in item and isinstance(item["raw"], str):
                raw = item["raw"].strip()
            else:
                try:
                    raw = json.dumps(item, separators=(",", ":"), ensure_ascii=False)
                except Exception:
                    raw = str(item)
            for k, v in item.items():
                if k == "raw":
                    continue
                structured[k] = v
            return Event(
                ts=datetime.now(timezone.utc),
                raw=raw,
                structured=structured,
                meta=meta,
            )
        raw = str(item).strip()
        if not raw:
            return None
        return Event(ts=datetime.now(timezone.utc), raw=raw, meta=meta)

    def _run_server(self) -> None:
        config = uvicorn.Config(
            self._app, host=self._host, port=self._port, log_level="info"
        )
        self._server = uvicorn.Server(config)
        self._server.run()

    def poll(self, max_events: int) -> List[Event]:
        out: List[Event] = []
        while len(out) < max_events:
            try:
                out.append(self._queue.get_nowait())
            except Empty:
                break
        return out
