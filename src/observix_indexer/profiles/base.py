from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Profile(ABC):
    @abstractmethod
    def normalize(self, raw: str) -> Dict[str, Any]: ...
