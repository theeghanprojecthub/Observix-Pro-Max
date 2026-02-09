from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, TextIO

from observix_agent.events import Event  # ✅ correct import (no circular import)


def _repair_escaped_windows_path(s: str) -> str:
    """
    Defensive repair for paths that accidentally contain control chars because
    something interpreted backslash escapes (e.g. "\\t" became a TAB).

    Example:
      "...\examples\temp\observix\demo.log" -> contains "\t" (TAB) -> invalid on Windows
      We convert TAB back into two chars: backslash + "t".
    """
    if not s:
        return s
    return s.replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


@dataclass
class FileTailSource:
    """
    Tails a text file and emits new lines as events.

    Supports:
      - from_start=True  -> start at beginning
      - from_start=False -> start at end (tail -f behaviour)

    Also supports legacy start_position ("begin"|"end") if provided.
    """

    path: str
    from_start: bool = False
    start_position: Optional[str] = None  # legacy compatibility

    _path: Path = field(init=False)
    _fh: Optional[TextIO] = field(default=None, init=False)

    def __post_init__(self) -> None:
        # ✅ Repair common escape issues (TAB/newline etc.)
        fixed = _repair_escaped_windows_path(self.path)

        # Normalize to OS path
        self._path = Path(fixed)

        # Normalize legacy parameter if used
        if self.start_position is not None:
            sp = str(self.start_position).lower().strip()
            if sp in ("begin", "start", "from_start"):
                self.from_start = True
            elif sp in ("end", "tail"):
                self.from_start = False

    def _open_if_needed(self) -> None:
        if self._fh is not None:
            return

        # If the file doesn't exist yet, fail clearly (better than cryptic OSError)
        if not self._path.exists():
            raise FileNotFoundError(f"file_tail source path not found: {self._path}")

        # open with newline="" so Windows newline handling is consistent
        self._fh = self._path.open("r", encoding="utf-8", errors="ignore", newline="")

        # Decide start position
        if self.from_start:
            self._fh.seek(0, io.SEEK_SET)
        else:
            self._fh.seek(0, io.SEEK_END)

    def poll(self, max_events: int) -> List[Event]:
        self._open_if_needed()
        assert self._fh is not None

        out: List[Event] = []
        while len(out) < max_events:
            line = self._fh.readline()
            if not line:
                break

            line = line.rstrip("\r\n")
            if line:
                out.append(Event(raw=line))
        return out

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None
