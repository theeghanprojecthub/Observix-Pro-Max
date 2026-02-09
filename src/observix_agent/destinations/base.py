from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from observix_agent.events import Event


class Destination(ABC):
    """A destination delivers events to an external target."""

    @abstractmethod
    def send(self, events: List[Event]) -> None:
        """Send a batch of events."""
        raise NotImplementedError
