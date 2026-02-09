from __future__ import annotations

from typing import Any, Dict

from .base import Profile


class KvPairs(Profile):
    """
    Parses: key=value key2=value2 ...
    """

    def normalize(self, raw: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for part in raw.split():
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        if not out:
            out["message"] = raw
        return out
