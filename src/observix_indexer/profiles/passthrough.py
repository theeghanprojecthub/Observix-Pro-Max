from __future__ import annotations

from typing import Any, Dict

from .base import Profile


class Passthrough(Profile):
    def normalize(self, raw: str) -> Dict[str, Any]:
        return {"message": raw}
