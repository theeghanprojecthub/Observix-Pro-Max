from __future__ import annotations

import json
from typing import Any, Dict

from .base import Profile


class JsonAuto(Profile):
    def normalize(self, raw: str) -> Dict[str, Any]:
        s = raw.strip()
        if not s.startswith("{"):
            return {"message": raw}

        try:
            obj = json.loads(s)
        except Exception:
            return {"message": raw}

        if isinstance(obj, dict):
            return obj
        return {"value": obj, "message": raw}
