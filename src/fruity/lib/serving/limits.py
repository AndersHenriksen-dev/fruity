"""A limit on requests per minute, because the API is public and every request costs compute.

The limit is global, not per visitor: its job is to cap cost, and a client can fake the address a per-visitor limit
needs. Each replica counts on its own, so the service's limit is this one times the number of replicas.
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Callable, Mapping

from pydantic import BaseModel, ConfigDict

from fruity.lib.shared.settings import config_for

WINDOW_SECONDS = 60.0
REQUESTS_PER_MINUTE_VARIABLE = "FRUITY_REQUESTS_PER_MINUTE"


class LimitsConfig(BaseModel):
    """What one replica accepts."""

    model_config = ConfigDict(extra="forbid")

    requests_per_minute: int
    max_upload_bytes: int
    max_batch_files: int
    max_image_pixels: int


def with_environment(limits: LimitsConfig, environment: Mapping[str, str]) -> LimitsConfig:
    """Let a deployment raise the request limit, because a load test would otherwise measure only the limit."""
    override = environment.get(REQUESTS_PER_MINUTE_VARIABLE)
    return limits.model_copy(update={"requests_per_minute": int(override)}) if override else limits


LIMITS = with_environment(config_for(__name__, LimitsConfig), os.environ)


class RateLimiter:
    """Allow a number of requests in any 60 seconds."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        """Start with no requests counted.

        Args:
            per_minute: How many requests to allow in any 60 seconds.
            clock: Where the time comes from, in seconds.
        """
        self.per_minute = per_minute
        self.clock = clock
        self.recent: deque[float] = deque()

    def allow(self) -> bool:
        """Count a request if it is within the limit, and say whether it was."""
        now = self.clock()
        while self.recent and now - self.recent[0] >= WINDOW_SECONDS:
            self.recent.popleft()
        if len(self.recent) >= self.per_minute:
            return False
        self.recent.append(now)
        return True
