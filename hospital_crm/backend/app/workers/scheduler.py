"""
Hospital CRM - Background Worker & Scheduler Engine
Manages scheduled jobs (reminders, follow-up notifications, SLA checks)
and asynchronous background task dispatching.
"""
import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from app.core.logging import logger


class TaskQueue:
    """Lightweight in-memory task queue with async execution support."""
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._completed_tasks = 0
        self._failed_tasks = 0

    async def enqueue(self, func: Callable, *args, **kwargs):
        """Enqueue a callable background task."""
        await self._queue.put((func, args, kwargs))

    async def _worker_loop(self):
        while self._running:
            try:
                func, args, kwargs = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                try:
                    if inspect.iscoroutinefunction(func):
                        await func(*args, **kwargs)
                    else:
                        func(*args, **kwargs)
                    self._completed_tasks += 1
                except Exception as e:
                    self._failed_tasks += 1
                    logger.error(f"Background task failed: {str(e)}", exc_info=True)
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def start(self):
        if not self._running:
            self._running = True
            try:
                loop = asyncio.get_running_loop()
                self._worker_task = loop.create_task(self._worker_loop())
            except RuntimeError:
                # In synchronous test or non-async context, task will run when loop starts
                self._worker_task = None
            logger.info("Background Task Worker started.")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Background Task Worker stopped.")

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "completed_tasks": self._completed_tasks,
            "failed_tasks": self._failed_tasks,
        }


class SchedulerEngine:
    """Scheduler Engine for periodic reminders and overdue checks."""
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
        self._running = False
        self._runner_task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None

    def register_job(self, name: str, interval_seconds: int, func: Callable):
        """Register a periodic job."""
        self._jobs[name] = {
            "interval": interval_seconds,
            "func": func,
            "last_executed": None,
            "run_count": 0,
        }
        logger.info(f"Registered periodic job: {name} (every {interval_seconds}s)")

    async def _scheduler_loop(self):
        while self._running:
            now = datetime.now(timezone.utc)
            self._last_run = now
            for name, job in self._jobs.items():
                last_exec = job["last_executed"]
                interval = job["interval"]
                if last_exec is None or (now - last_exec).total_seconds() >= interval:
                    try:
                        func = job["func"]
                        if inspect.iscoroutinefunction(func):
                            await func()
                        else:
                            func()
                        job["last_executed"] = now
                        job["run_count"] += 1
                    except Exception as e:
                        logger.error(f"Scheduler job '{name}' failed: {str(e)}", exc_info=True)
            await asyncio.sleep(1)

    def start(self):
        if not self._running:
            self._running = True
            try:
                loop = asyncio.get_running_loop()
                self._runner_task = loop.create_task(self._scheduler_loop())
            except RuntimeError:
                self._runner_task = None
            logger.info("Scheduler Engine started.")

    async def stop(self):
        self._running = False
        if self._runner_task:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
            logger.info("Scheduler Engine stopped.")

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "jobs_count": len(self._jobs),
            "jobs": {k: {"interval": v["interval"], "run_count": v["run_count"]} for k, v in self._jobs.items()},
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }


task_queue = TaskQueue()
scheduler_engine = SchedulerEngine()
