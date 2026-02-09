from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Event is the internal representation transported through a pipeline."""

    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: str
    structured: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    def as_json_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return self.model_dump(mode="json")
