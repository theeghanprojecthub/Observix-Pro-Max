from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    jitter: float = 0.1

    def sleep(self, attempt: int) -> None:
        # attempt is 1-based
        delay = min(
            self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1))
        )
        delay = delay * (1 + random.uniform(-self.jitter, self.jitter))
        time.sleep(max(0.0, delay))
