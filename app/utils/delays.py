from __future__ import annotations

import asyncio
import random


async def sleep_fixed(seconds: float) -> None:
    await asyncio.sleep(max(0.0, seconds))


async def sleep_random(low: float, high: float) -> None:
    if low > high:
        low, high = high, low
    await asyncio.sleep(random.uniform(max(0.0, low), max(0.0, high)))


async def sleep_with_jitter(base_delay: float, random_range: tuple[float, float]) -> None:
    await sleep_fixed(base_delay)
    await sleep_random(*random_range)
