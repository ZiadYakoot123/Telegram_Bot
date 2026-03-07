from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(slots=True)
class BatchConfig:
    enabled: bool = True
    batch_size: int = 25
    delay_between_batches: float = 20.0


class BatchController:
    def __init__(self, config: BatchConfig) -> None:
        self.config = config
        self._stop_event = asyncio.Event()

    def enable(self, enabled: bool) -> None:
        self.config.enabled = enabled

    def set_batch_size(self, batch_size: int) -> None:
        self.config.batch_size = max(1, batch_size)

    def set_delay_between_batches(self, seconds: float) -> None:
        self.config.delay_between_batches = max(0.0, seconds)

    def emergency_stop(self) -> None:
        self._stop_event.set()

    def reset_stop(self) -> None:
        self._stop_event.clear()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    async def wait_between_batches(self) -> None:
        if self.config.delay_between_batches > 0:
            await asyncio.sleep(self.config.delay_between_batches)
