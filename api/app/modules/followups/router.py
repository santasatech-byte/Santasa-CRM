"""
Hospital CRM - Follow-up Management & Today's Work Queue API Router
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions, check_resource_access
from app.core.errors import NotFoundError, ForbiddenError, ValidationError
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum
from app.modules.leads.schemas import LeadSummary
from app.modules.followups.models import FollowUp, FollowUpStatusEnum
from app.modules.followups.service import FollowUpService
from app.modules.followups.schemas import (
    FollowUpSummary,
    ScheduleFollowUpRequest,
    CompleteFollowUpRequest,
    RescheduleFollowUpRequest,
    TodayWorkQueueResponse
)

router = APIRouter(prefix="/followups", tags=["Follow-up Management & Work Queue"])


@router.post("", response_model=FollowUpSummary, status_code=status.HTTP_201_CREATED)
async def schedule_followup(
    request: ScheduleFollowUpRequest,
    current_user: User = Depends(require_permission(Permissions.SCHEDULE_FOLLOWUP)),
    db: Session = Depends(get_db)
):
    """Schedules a new follow-up action for a patient lead."""
    lead = db.get(Lead, request.lead_id)
    if not lead:
        raise NotFoundError("Lead", request.lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to schedule follow-ups for this lead.")

    followup = FollowUpService.schedule_followup(
        db=db,
        lead=lead,
        executive_id=lead.assigned_executive_id or current_user.id,
        scheduled_at=request.scheduled_at,
        followup_type=request.type,
        priority=request.priority,
        notes=request.notes,
        reminder_offset_minutes=request.reminder_offset_minutes,
        created_by_user_id=current_user.id
    )
    return FollowUpSummary.model_validate(followup)


@router.get("/work-queue", response_model=TodayWorkQueueResponse, status_code=status.HTTP_200_OK)
async def get_today_work_queue(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Primary workspace endpoint for call-center executives:
    Returns partitioned queues: New Leads, Due Today, Overdue (oldest first), Upcoming.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # 1. New Leads
    new_leads_stmt = select(Lead).where(
        Lead.lead_status == LeadStatusEnum.NEW.value,
        Lead.is_archived == False
    )
    if current_user.role == UserRole.CRM_EXECUTIVE.value:
        new_leads_stmt = new_leads_stmt.where(Lead.assigned_executive_id == current_user.id)
    elif current_user.role == UserRole.CRM_MANAGER.value and current_user.branch_id:
        new_leads_stmt = new_leads_stmt.where(Lead.branch_id == current_user.branch_id)
    new_leads = db.scalars(new_leads_stmt.limit(50)).all()

    # 2. Follow-ups Base Query
    f_stmt = select(FollowUp).where(
        FollowUp.status.in_([FollowUpStatusEnum.SCHEDULED.value, FollowUpStatusEnum.DUE.value])
    )
    if current_user.role == UserRole.CRM_EXECUTIVE.value:
        f_stmt = f_stmt.where(FollowUp.executive_id == current_user.id)

    all_followups = db.scalars(f_stmt).all()

    overdue = []
    due_today = []
    upcoming = []

    for f in all_followups:
        sched = f.scheduled_at
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)

        if sched < now:
            overdue.append(f)
        elif today_start <= sched <= today_end:
            due_today.append(f)
        else:
            upcoming.append(f)

    # Sort overdue oldest first
    overdue.sort(key=lambda x: x.scheduled_at)
    due_today.sort(key=lambda x: x.scheduled_at)

    return TodayWorkQueueResponse(
        summary={
            "new_leads_count": len(new_leads),
            "due_today_count": len(due_today),
            "overdue_count": len(overdue),
            "upcoming_count": len(upcoming)
        },
        new_leads=[LeadSummary.model_validate(l) for l in new_leads],
        due_followups=[FollowUpSummary.model_validate(f) for f in due_today],
        overdue_followups=[FollowUpSummary.model_validate(f) for f in overdue],
        upcoming_followups=[FollowUpSummary.model_validate(f) for f in upcoming]
    )


@router.post("/{followup_id}/complete", response_model=FollowUpSummary, status_code=status.HTTP_200_OK)
async def complete_followup(
    followup_id: str,
    request: CompleteFollowUpRequest,
    current_user: User = Depends(require_permission(Permissions.COMPLETE_FOLLOWUP)),
    db: Session = Depends(get_db)
):
    """Marks a follow-up complete with outcome notes."""
    stmt = select(FollowUp).where(FollowUp.id == followup_id)
    followup = db.scalars(stmt).first()
    if not followup:
        raise NotFoundError("FollowUp", followup_id)

    if not check_resource_access(current_user, owner_id=followup.executive_id):
        raise ForbiddenError("You are not authorized to complete this follow-up.")

    completed = FollowUpService.complete_followup(
        db=db,
        followup_id=followup_id,
        user_id=current_user.id,
        completion_notes=request.completion_notes
    )
    return FollowUpSummary.model_validate(completed)


@router.post("/{followup_id}/reschedule", response_model=FollowUpSummary, status_code=status.HTTP_200_OK)
async def reschedule_followup(
    followup_id: str,
    request: RescheduleFollowUpRequest,
    current_user: User = Depends(require_permission(Permissions.SCHEDULE_FOLLOWUP)),
    db: Session = Depends(get_db)
):
    """Reschedules follow-up to a new date and time with reason."""
    stmt = select(FollowUp).where(FollowUp.id == followup_id)
    followup = db.scalars(stmt).first()
    if not followup:
        raise NotFoundError("FollowUp", followup_id)

    if not check_resource_access(current_user, owner_id=followup.executive_id):
        raise ForbiddenError("You are not authorized to reschedule this follow-up.")

    new_f = FollowUpService.reschedule_followup(
        db=db,
        followup_id=followup_id,
        user_id=current_user.id,
        new_scheduled_at=request.new_scheduled_at,
        reason=request.reason
    )
    return FollowUpSummary.model_validate(new_f)
