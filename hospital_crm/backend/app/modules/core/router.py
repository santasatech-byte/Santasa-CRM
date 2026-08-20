"""
Hospital CRM - Core Health & System API Router
Provides system health monitoring, worker diagnostics, and environment status.
"""
from datetime import datetime, timezone
import os
import sys
from fastapi import APIRouter, Depends, status
from app.core.config import settings
from app.core.database import check_db_health
from app.workers.scheduler import task_queue, scheduler_engine

router = APIRouter(prefix="/core", tags=["Core System"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def get_system_health():
    """
    Comprehensive System Health Check.
    Verifies Database, Background Worker, and Scheduler status.
    """
    db_healthy = check_db_health()
    queue_status = task_queue.status
    scheduler_status = scheduler_engine.status
    
    is_healthy = db_healthy and queue_status["running"] and scheduler_status["running"]
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": {
            "name": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "version": "1.0.0",
            "python_version": sys.version.split()[0],
        },
        "services": {
            "database": {
                "status": "connected" if db_healthy else "disconnected",
                "healthy": db_healthy,
            },
            "task_queue": {
                "healthy": queue_status["running"],
                **queue_status
            },
            "scheduler": {
                "healthy": scheduler_status["running"],
                **scheduler_status
            },
            "telephony_adapter": {
                "active_provider": settings.TELEPHONY_PROVIDER,
                "status": "ready"
            },
            "whatsapp_adapter": {
                "active_provider": settings.WHATSAPP_PROVIDER,
                "status": "ready"
            }
        }
    }


@router.get("/info", status_code=status.HTTP_200_OK)
async def get_system_info():
    """Returns safe, non-sensitive system metadata."""
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
        "modules_active": [
            "Core", "Leads", "Calls", "FollowUps", "Appointments",
            "Integrations", "Reviews", "Notifications", "Reports",
            "Administration", "Audit"
        ]
    }
