from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from observix_agent.destinations.base import Destination
from observix_agent.destinations.file import FileDestination
from observix_agent.destinations.http import HttpDestination
from observix_agent.destinations.syslog_udp import SyslogUdpDestination
from observix_agent.events import Event
from observix_agent.processors.indexed import IndexedProcessor
from observix_agent.processors.raw import RawProcessor
from observix_agent.sources.base import Source
from observix_agent.sources.file_tail import FileTailSource
from observix_agent.sources.http_listener import HttpListenerSource
from observix_agent.sources.syslog_udp import SyslogUdpSource
from observix_agent.state import AgentState


@dataclass(frozen=True)
class Runtime:
    """Runtime metadata and shared state available to pipeline executions."""

    agent_id: str
    region: str
    tenant_id: Optional[str]
    state: AgentState


class PipelineRunner:
    """
    Runs one pipeline assignment using a non-blocking tick loop.
    """

    def __init__(self, runtime: Runtime, spec: Any, retry: Any) -> None:
        self._rt = runtime
        self._retry = retry
        self._spec = self._normalize_spec(spec)

        self.pipeline_id = str(
            self._spec.get("pipeline_id")
            or self._spec.get("id")
            or self._spec.get("name")
            or ""
        )
        self.name = str(self._spec.get("name") or self.pipeline_id or "pipeline")
        self.enabled = bool(self._spec.get("enabled", True))

        self._batch_max_events = int(self._spec.get("batch_max_events", 50))
        self._batch_max_seconds = float(self._spec.get("batch_max_seconds", 1.0))

        self._agent_meta: Dict[str, Any] = {
            "agent_id": self._rt.agent_id,
            "region": self._rt.region,
        }
        if self._rt.tenant_id is not None:
            self._agent_meta["tenant_id"] = self._rt.tenant_id

        self._source = self._build_source(self._spec["source"])
        self._destination = self._build_destination(self._spec["destination"])
        self._processor = self._build_processor(
            self._spec.get("processor") or {"mode": "raw", "options": {}}
        )

        self._buffer: List[Event] = []
        self._last_flush = time.monotonic()

        self._send_attempt = 0
        self._next_send_at = 0.0
        self._inflight: List[Event] = []

        self._metrics: Dict[str, int] = {
            "received": 0,
            "buffered": 0,
            "sent_batches": 0,
            "sent_events": 0,
            "send_failures": 0,
        }
        self._last_ok_at: Optional[float] = None
        self._last_err: Optional[str] = None
        self._last_metrics_log = time.monotonic()
        self._metrics_interval_seconds = 5.0

    def tick(self) -> None:
        """Advance pipeline execution by one scheduling slice."""
        if not self.enabled:
            return

        now = time.monotonic()

        if self._inflight and now < self._next_send_at:
            self._maybe_log_metrics(now)
            return

        if self._inflight:
            self._try_send_inflight()
            self._maybe_log_metrics(now)
            return

        pulled = self._source.poll(self._batch_max_events)
        if pulled:
            self._buffer.extend(pulled)
            self._metrics["received"] += len(pulled)
            self._metrics["buffered"] += len(pulled)

        self._flush_if_needed()
        self._maybe_log_metrics(now)

    def _flush_if_needed(self) -> None:
        if not self._buffer:
            return

        age = time.monotonic() - self._last_flush
        if len(self._buffer) < self._batch_max_events and age < self._batch_max_seconds:
            return

        batch = self._buffer
        self._buffer = []
        self._last_flush = time.monotonic()

        processed = self._processor.process(batch)
        for e in processed:
            e.meta.update(self._agent_meta)
            e.meta["pipeline"] = self.name
            if self.pipeline_id:
                e.meta["pipeline_id"] = self.pipeline_id

        self._inflight = processed
        self._send_attempt = 0
        self._next_send_at = time.monotonic()
        self._try_send_inflight()

    def _try_send_inflight(self) -> None:
        if not self._inflight:
            return

        try:
            self._destination.send(self._inflight)
            self._metrics["sent_batches"] += 1
            self._metrics["sent_events"] += len(self._inflight)
            self._last_ok_at = time.time()
            self._last_err = None

            self._inflight = []
            self._send_attempt = 0
            self._next_send_at = 0.0
        except Exception as e:
            self._metrics["send_failures"] += 1
            self._last_err = f"{type(e).__name__}: {e}"

            self._send_attempt += 1
            delay = self._compute_backoff_seconds(self._send_attempt)
            self._next_send_at = time.monotonic() + delay

    def _compute_backoff_seconds(self, attempt: int) -> float:
        """Compute exponential backoff with bounded jitter."""
        base = 0.5
        cap = 10.0
        exp = min(cap, base * (2 ** max(0, attempt - 1)))
        jitter = (time.monotonic() % 1.0) * 0.25
        return min(cap, exp + jitter)

    def _maybe_log_metrics(self, now_monotonic: float) -> None:
        """Print pipeline runtime stats periodically."""
        if (now_monotonic - self._last_metrics_log) < self._metrics_interval_seconds:
            return

        next_in = 0.0
        if self._inflight:
            next_in = max(0.0, self._next_send_at - now_monotonic)

        last_ok = "None"
        if self._last_ok_at is not None:
            age_s = max(0.0, time.time() - self._last_ok_at)
            last_ok = f"{age_s:.1f}s_ago"

        print(
            "pipeline_stats "
            f"pipeline_id={self.pipeline_id or 'n/a'} "
            f"name={self.name} "
            f"recv={self._metrics['received']} "
            f"sent_events={self._metrics['sent_events']} "
            f"sent_batches={self._metrics['sent_batches']} "
            f"failures={self._metrics['send_failures']} "
            f"buffer={len(self._buffer)} "
            f"inflight={len(self._inflight)} "
            f"retry_attempt={self._send_attempt} "
            f"next_send_in={next_in:.2f}s "
            f"last_ok={last_ok} "
            f"last_err={(self._last_err or 'None')}"
        )

        self._last_metrics_log = now_monotonic

    def _normalize_spec(self, spec: Any) -> Dict[str, Any]:
        """Convert a dict or pydantic model into a plain dict."""
        if isinstance(spec, dict):
            return spec
        if hasattr(spec, "model_dump"):
            return spec.model_dump(mode="json")
        if hasattr(spec, "dict"):
            return spec.dict()
        raise TypeError("pipeline spec must be dict or pydantic model")

    def _build_source(self, cfg: Dict[str, Any]) -> Source:
        """Create a source implementation from config."""
        t = str(cfg.get("type"))
        opts = cfg.get("options") or {}

        if t == "file_tail":
            path = str(opts["path"])
            from_start = bool(opts.get("from_start", False))
            start_position = opts.get("start_position")
            return FileTailSource(
                path=path, from_start=from_start, start_position=start_position
            )

        if t == "syslog_udp":
            host = str(opts.get("host", "0.0.0.0"))
            port = int(opts["port"])
            max_queue_size = int(opts.get("max_queue_size", 50000))
            return SyslogUdpSource(host=host, port=port, max_queue_size=max_queue_size)

        if t == "http_listener":
            host = str(opts.get("host", "0.0.0.0"))
            port = int(opts["port"])
            path = str(opts.get("path", "/ingest"))
            max_queue_size = int(opts.get("max_queue_size", 50000))
            return HttpListenerSource(
                host=host, port=port, path=path, max_queue_size=max_queue_size
            )

        raise ValueError(f"unknown source type: {t}")

    def _build_destination(self, cfg: Dict[str, Any]) -> Destination:
        """Create a destination implementation from config."""
        t = str(cfg.get("type"))
        opts = cfg.get("options") or {}

        if t == "file":
            path = str(opts["path"])
            fmt = str(opts.get("format", "raw"))
            return FileDestination(path=path, format=fmt)

        if t == "http":
            url = str(opts["url"])
            timeout = float(opts.get("timeout_seconds", 5.0))
            return HttpDestination(url=url, timeout_seconds=timeout)

        if t == "syslog_udp":
            host = str(opts["host"])
            port = int(opts.get("port", 514))
            pri = int(opts.get("pri", 13))
            hostname = opts.get("hostname")
            appname = str(opts.get("appname", "observix"))
            return SyslogUdpDestination(
                host=host, port=port, pri=pri, hostname=hostname, appname=appname
            )

        raise ValueError(f"unknown destination type: {t}")

    def _build_processor(self, cfg: Dict[str, Any]) -> Any:
        mode = str(cfg.get("mode", "raw"))
        opts = cfg.get("options") or {}

        if mode == "raw":
            return RawProcessor()

        if mode == "indexed":
            return IndexedProcessor(opts)

        raise ValueError(f"unknown processor mode: {mode}")
