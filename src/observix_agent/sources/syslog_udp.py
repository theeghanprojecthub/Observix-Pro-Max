from __future__ import annotations

import socket
import threading
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import List

from observix_agent.events import Event
from observix_agent.sources.base import Source


class SyslogUdpSource(Source):
    """Receives syslog messages over UDP and exposes them via poll()."""

    def __init__(self, host: str, port: int, max_queue_size: int = 50000) -> None:
        self._host = host
        self._port = port
        self._queue: Queue[Event] = Queue(maxsize=max_queue_size)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self._host, self._port))
        self._sock.settimeout(1.0)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError:
                break
            raw = data.decode("utf-8", errors="ignore").strip()
            if not raw:
                continue
            evt = Event(
                ts=datetime.now(timezone.utc),
                raw=raw,
                meta={"source": "syslog_udp", "remote_addr": f"{addr[0]}:{addr[1]}"},
            )
            try:
                self._queue.put_nowait(evt)
            except Exception:
                continue

    def poll(self, max_events: int) -> List[Event]:
        out: List[Event] = []
        while len(out) < max_events:
            try:
                out.append(self._queue.get_nowait())
            except Empty:
                break
        return out

    def close(self) -> None:
        """Stop the receiver."""
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass
