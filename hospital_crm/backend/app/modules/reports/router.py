"""
Hospital CRM - Analytics & Reports API Router
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions
from app.modules.administration.models import User
from app.modules.reports.service import ReportingService

router = APIRouter(prefix="/reports", tags=["Analytics & Reports"])


@router.get("/funnel", status_code=status.HTTP_200_OK)
async def get_conversion_funnel(
    branch_id: Optional[str] = None,
    current_user: User = Depends(require_permission(Permissions.VIEW_REPORTS)),
    db: Session = Depends(get_db)
):
    """Retrieves conversion funnel analytics."""
    return ReportingService.get_conversion_funnel(db=db, branch_id=branch_id)


@router.get("/executive-performance", status_code=status.HTTP_200_OK)
async def get_executive_performance(
    branch_id: Optional[str] = None,
    current_user: User = Depends(require_permission(Permissions.VIEW_EXECUTIVE_PERFORMANCE)),
    db: Session = Depends(get_db)
):
    """Retrieves executive scorecard (calls, talk time, adherence, revenue)."""
    return ReportingService.get_executive_performance(db=db, branch_id=branch_id)


@router.get("/source-attribution", status_code=status.HTTP_200_OK)
async def get_source_attribution(
    current_user: User = Depends(require_permission(Permissions.VIEW_REPORTS)),
    db: Session = Depends(get_db)
):
    """Retrieves conversion volume and conversion rates grouped by lead source."""
    return ReportingService.get_source_attribution(db=db)


@router.get("/revenue-summary", status_code=status.HTTP_200_OK)
async def get_revenue_summary(
    current_user: User = Depends(require_permission(Permissions.VIEW_REPORTS)),
    db: Session = Depends(get_db)
):
    """Retrieves total CRM converted revenue, volume, and average package ticket size."""
    return ReportingService.get_revenue_summary(db=db)
