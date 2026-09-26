"""The controller and every motion source share one clock, so "Go" and sample times line up."""

import asyncio
import time


class Clock:
    def now(self):
        return time.monotonic()

    async def sleep(self, s):
        await asyncio.sleep(s)


class FakeClock:
    """Test clock: sleep() advances time instantly, so a 3-minute check-in runs in a second."""

    def __init__(self, t=1000.0):
        self.t = t

    def now(self):
        return self.t

    async def sleep(self, s):
        self.t += s
        await asyncio.sleep(0)
