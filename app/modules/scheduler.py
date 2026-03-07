from __future__ import annotations

import logging
from datetime import datetime
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import Database


logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def schedule_once(
        self,
        name: str,
        run_at: datetime,
        func: Callable[[], Awaitable[None]],
    ) -> str:
        job = self.scheduler.add_job(func, DateTrigger(run_date=run_at), id=name, replace_existing=True)
        await self.database.log_operation("schedule", "success", f"One-time job '{name}' at {run_at.isoformat()}")
        return str(job.id)

    async def schedule_interval(
        self,
        name: str,
        seconds: int,
        func: Callable[[], Awaitable[None]],
    ) -> str:
        job = self.scheduler.add_job(func, IntervalTrigger(seconds=seconds), id=name, replace_existing=True)
        await self.database.log_operation("schedule", "success", f"Interval job '{name}' every {seconds}s")
        return str(job.id)

    async def schedule_cron(
        self,
        name: str,
        cron: str,
        func: Callable[[], Awaitable[None]],
    ) -> str:
        # Cron format: "minute hour day month day_of_week"
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression. Expected 5 fields")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        job = self.scheduler.add_job(func, trigger, id=name, replace_existing=True)
        await self.database.log_operation("schedule", "success", f"Cron job '{name}' with '{cron}'")
        return str(job.id)

    def remove_job(self, name: str) -> None:
        self.scheduler.remove_job(job_id=name)

    def list_jobs(self) -> list[dict[str, str]]:
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": str(job.id),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else "none",
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]
