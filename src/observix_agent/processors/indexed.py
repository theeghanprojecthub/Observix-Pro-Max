from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Mapping, Optional, Set
from urllib.parse import urlparse, urlunparse

import httpx

from observix_agent.events import Event

_NORMALIZE_PATH = "/v1/normalize"


def _normalize_indexer_url(base_url: str) -> str:
    """
    Normalize the indexer base URL so it ends with exactly /v1/normalize.
    """
    if not base_url or not str(base_url).strip():
        raise ValueError("indexer_url is empty")

    u = str(base_url).strip()
    parsed = urlparse(u)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"indexer_url must include scheme and host, got: {base_url!r}")

    path = (parsed.path or "").rstrip("/")

    while path.endswith(_NORMALIZE_PATH):
        path = path[: -len(_NORMALIZE_PATH)].rstrip("/")

    final_path = (path + _NORMALIZE_PATH) if path else _NORMALIZE_PATH

    return urlunparse(
        (parsed.scheme, parsed.netloc, final_path, "", parsed.query, parsed.fragment)
    )


def _to_mapping(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Best-effort conversion of an object to a dict.
    """
    if isinstance(obj, Mapping):
        return dict(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return dict(obj.model_dump(mode="json"))
    if hasattr(obj, "dict"):
        return dict(obj.dict())
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return None


def _extract_raw_line(event_obj: Any) -> str:
    """
    Extract a raw log line from an Event-like object.
    """
    m = _to_mapping(event_obj)
    if not m:
        return str(event_obj)

    for k in ("raw", "text", "message", "body", "line"):
        v = m.get(k)
        if isinstance(v, str) and v.strip():
            return v

    payload = m.get("payload")
    if isinstance(payload, str) and payload.strip():
        return payload

    return str(event_obj)


def _event_fields() -> Set[str]:
    """
    Return the set of field names supported by the Event model/dataclass.
    """
    ann = getattr(Event, "__annotations__", None)
    if isinstance(ann, dict):
        return set(ann.keys())
    return set()


def _dict_to_event(d: Mapping[str, Any], *, fallback_raw: str = "") -> Event:
    """
    Convert an indexer-returned dict into an Event.
    Ensures required Event fields (e.g., raw) are always populated.
    """
    data = dict(d)

    msg = ""
    for k in ("raw", "message", "text", "line", "body"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            msg = v
            break

    if not msg and fallback_raw:
        msg = fallback_raw

    if (
        "raw" not in data
        or not isinstance(data.get("raw"), str)
        or not str(data.get("raw")).strip()
    ):
        data["raw"] = msg

    if (
        "text" not in data
        or not isinstance(data.get("text"), str)
        or not str(data.get("text")).strip()
    ):
        data["text"] = msg

    if "meta" not in data or not isinstance(data.get("meta"), dict):
        data["meta"] = {}

    allowed = _event_fields()
    if allowed:
        keep = {"raw", "text", "meta"}
        allowed = allowed.union(keep)
        data = {k: v for k, v in data.items() if k in allowed}

    return Event(**data)


def _extract_events_from_normalize_response(data: Any) -> List[Mapping[str, Any]]:
    """
    Extract normalized event dictionaries from the indexer response.
    Supported shapes:
      {"events": [...]}
      {"event": {...}}
      {"doc": {...}}
      {"docs": [...]}
      {"ok": true, "doc": {...}}
    """
    if isinstance(data, list):
        if all(isinstance(x, Mapping) for x in data):
            return list(data)
        raise RuntimeError("indexer_response_invalid_list_shape")

    if not isinstance(data, Mapping):
        raise RuntimeError("indexer_response_invalid_non_object")

    events = data.get("events")
    if isinstance(events, list) and all(isinstance(x, Mapping) for x in events):
        return list(events)

    event = data.get("event")
    if isinstance(event, Mapping):
        return [event]

    docs = data.get("docs")
    if isinstance(docs, list) and all(isinstance(x, Mapping) for x in docs):
        return list(docs)

    doc = data.get("doc")
    if isinstance(doc, Mapping):
        return [doc]

    raise RuntimeError("indexer_response_missing_events_key")


class IndexedProcessor:
    """
    Sends raw log lines to the indexer /v1/normalize endpoint and returns normalized Events.

    This indexer endpoint returns a single object (doc) per request in many deployments:
      {"ok": true, "doc": {...}}

    For correctness, this processor sends one raw line per request.
    """

    def __init__(self, options: Dict[str, Any]) -> None:
        self._timeout = float(options.get("timeout_seconds", 10.0))
        normalize_url = str(options.get("normalize_url") or "").strip()
        indexer_url = str(options.get("indexer_url") or "").strip()
        base = normalize_url or indexer_url
        self._normalize_url = _normalize_indexer_url(base)
        self._profile = str(options.get("profile", "passthrough"))
        self._include_meta = bool(options.get("include_meta", True))

    def process(self, batch: List[Any]) -> List[Event]:
        raw_lines = [_extract_raw_line(e) for e in batch]
        out: List[Event] = []

        with httpx.Client(timeout=self._timeout) as client:
            for raw in raw_lines:
                payload = {
                    "profile": self._profile,
                    "raw": raw,
                    "include_meta": self._include_meta,
                }
                resp = client.post(self._normalize_url, json=payload)
                if resp.status_code == 422:
                    raise RuntimeError(f"indexer_request_invalid_422: {resp.text}")
                resp.raise_for_status()
                data = resp.json()

                docs = _extract_events_from_normalize_response(data)
                if not docs:
                    raise RuntimeError(
                        f"indexer_response_empty: indexer_response={data!r}"
                    )

                out.extend(_dict_to_event(d, fallback_raw=raw) for d in docs)

        return out
