from __future__ import annotations

from typing import List

from observix_agent.events import Event


class RawProcessor:
    """Raw processor returns events unchanged."""

    def process(self, events: List[Event]) -> List[Event]:
        return events
