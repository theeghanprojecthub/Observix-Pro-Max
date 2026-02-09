from __future__ import annotations

import json
from pathlib import Path
from typing import List

from observix_agent.destinations.base import Destination
from observix_agent.events import Event


class FileDestination(Destination):
    """Writes events to a file as newline-delimited raw or JSONL."""

    def __init__(self, path: str, format: str = "raw") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._format = format

    def send(self, events: List[Event]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            if self._format == "jsonl":
                for e in events:
                    f.write(json.dumps(e.as_json_dict(), ensure_ascii=False) + "\n")
            else:
                for e in events:
                    f.write(e.raw + "\n")
