from __future__ import annotations

from typing import Any, Dict

from observix_indexer.profiles.passthrough import Passthrough
from observix_indexer.profiles.json_auto import JsonAuto
from observix_indexer.profiles.kv_pairs import KvPairs

_REGISTRY = {
    "passthrough": Passthrough(),
    "json_auto": JsonAuto(),
    "kv_pairs": KvPairs(),
}


def normalize(profile: str, raw: str) -> Dict[str, Any]:
    p = _REGISTRY.get(profile)
    if not p:
        raise ValueError(f"Unknown profile: {profile}")
    return p.normalize(raw)
