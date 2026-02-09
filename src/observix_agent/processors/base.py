from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from observix_common.models import LogEvent, PipelineSpec


class Processor(ABC):
    def __init__(self, pipeline: PipelineSpec):
        self.pipeline = pipeline

    @abstractmethod
    def process_batch(self, events: Iterable[LogEvent]) -> List[LogEvent]: ...
