from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from observix_agent.events import Event


class Source(ABC):
    """A source produces events for a pipeline."""

    @abstractmethod
    def poll(self, max_events: int) -> List[Event]:
        """Return up to max_events newly available events."""
        raise NotImplementedError
