"""
Tests for Task Queue and Scheduler Engine.
"""
import asyncio
import pytest
from app.workers.scheduler import TaskQueue, SchedulerEngine


@pytest.mark.asyncio
async def test_task_queue_execution():
    """Verify background task queue processes enqueued async work."""
    queue = TaskQueue()
    queue.start()
    
    executed = []
    
    async def sample_task(val: int):
        executed.append(val)
        
    await queue.enqueue(sample_task, 42)
    
    # Wait briefly for queue worker to pick up and process task
    await asyncio.sleep(0.1)
    
    status = queue.status
    assert status["running"] is True
    assert 42 in executed
    assert status["completed_tasks"] >= 1
    
    await queue.stop()
    assert queue.status["running"] is False


@pytest.mark.asyncio
async def test_scheduler_engine_registration():
    """Verify scheduler registers periodic jobs and records execution counts."""
    scheduler = SchedulerEngine()
    
    runs = []
    
    def heartbeat():
        runs.append(True)
        
    scheduler.register_job("heartbeat", interval_seconds=1, func=heartbeat)
    assert scheduler.status["jobs_count"] == 1
    
    scheduler.start()
    await asyncio.sleep(1.2)
    await scheduler.stop()
    
    assert len(runs) >= 1
    assert scheduler.status["running"] is False
