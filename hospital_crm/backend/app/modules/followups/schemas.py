"""
Hospital CRM - Follow-up Management Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.modules.followups.models import FollowUpTypeEnum, FollowUpStatusEnum
from app.modules.leads.schemas import LeadSummary


class FollowUpSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    executive_id: str
    scheduled_at: datetime
    type: str
    priority: str
    notes: Optional[str] = None
    status: str
    reminder_offset_minutes: int
    reminder_processed: bool
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    created_at: datetime


class ScheduleFollowUpRequest(BaseModel):
    lead_id: str
    scheduled_at: datetime
    type: FollowUpTypeEnum = FollowUpTypeEnum.CALL
    priority: str = "Medium"
    notes: Optional[str] = None
    reminder_offset_minutes: int = 15


class CompleteFollowUpRequest(BaseModel):
    completion_notes: str = Field(..., min_length=2)


class RescheduleFollowUpRequest(BaseModel):
    new_scheduled_at: datetime
    reason: str = Field(..., min_length=2)


class TodayWorkQueueResponse(BaseModel):
    summary: Dict[str, int]
    new_leads: List[LeadSummary]
    due_followups: List[FollowUpSummary]
    overdue_followups: List[FollowUpSummary]
    upcoming_followups: List[FollowUpSummary]
