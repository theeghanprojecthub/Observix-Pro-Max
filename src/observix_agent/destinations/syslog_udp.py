from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import List, Optional

from observix_agent.destinations.base import Destination
from observix_agent.events import Event


class SyslogUdpDestination(Destination):
    """Sends events to a remote syslog server over UDP."""

    def __init__(
        self,
        host: str,
        port: int,
        pri: int = 13,
        hostname: Optional[str] = None,
        appname: str = "observix",
    ) -> None:
        self._host = host
        self._port = port
        self._pri = pri
        self._hostname = hostname
        self._appname = appname
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _format_line(self, e: Event) -> str:
        ts = e.ts.astimezone(timezone.utc).strftime("%b %d %H:%M:%S")
        host = self._hostname or e.meta.get("agent_id") or "observix"
        msg = e.raw.replace("\n", " ").strip()
        return f"<{self._pri}>{ts} {host} {self._appname}: {msg}"

    def send(self, events: List[Event]) -> None:
        for e in events:
            line = self._format_line(e).encode("utf-8", errors="ignore")
            self._sock.sendto(line, (self._host, self._port))
