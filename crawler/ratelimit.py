"""Minimum pause between requests to the same host."""

import time
from collections.abc import Callable
from urllib.parse import urlsplit


class HostLimiter:
    def __init__(
        self,
        delay: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.delay = delay
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> float:
        """Block until the host may be hit again. Returns the time slept."""
        host = urlsplit(url).netloc
        slept = 0.0
        last = self._last.get(host)
        if last is not None:
            remaining = self.delay - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
                slept = remaining
        self._last[host] = self._clock()
        return slept
