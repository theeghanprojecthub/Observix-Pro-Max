from __future__ import annotations

from typing import List

import httpx

from observix_agent.destinations.base import Destination
from observix_agent.events import Event


class HttpDestination(Destination):
    """Sends events to an HTTP endpoint as JSON array."""

    def __init__(self, url: str, timeout_seconds: float = 5.0) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._client = httpx.Client(timeout=self._timeout)

    def send(self, events: List[Event]) -> None:
        payload = [e.as_json_dict() for e in events]
        resp = self._client.post(self._url, json=payload)
        resp.raise_for_status()
