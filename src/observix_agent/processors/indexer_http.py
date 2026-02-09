from __future__ import annotations

from typing import Iterable, List

import httpx

from observix_common.models import LogEvent, PipelineSpec
from observix_agent.processors.base import Processor


class IndexerHttpProcessor(Processor):
    """
    Options:
      - indexer_url: str (default http://127.0.0.1:7100)
      - profile: str (default passthrough)
      - timeout_seconds: float (default 3)
    """

    def __init__(self, pipeline: PipelineSpec):
        super().__init__(pipeline)
        opts = pipeline.processor.options
        self.indexer_url = str(opts.get("indexer_url", "http://127.0.0.1:7100")).rstrip(
            "/"
        )
        self.profile = str(opts.get("profile", "passthrough"))
        self.timeout = float(opts.get("timeout_seconds", 3))

    def process_batch(self, events: Iterable[LogEvent]) -> List[LogEvent]:
        out: List[LogEvent] = []
        with httpx.Client(timeout=self.timeout) as client:
            for e in events:
                r = client.post(
                    f"{self.indexer_url}/v1/normalize",
                    json={"profile": self.profile, "raw": e.raw},
                )
                r.raise_for_status()
                doc = r.json().get("doc", {})
                e.structured.update(doc)
                out.append(e)
        return out
