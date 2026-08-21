"""
Hospital CRM - Lead Management Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.modules.leads.models import LeadSourceEnum, LeadPriorityEnum, LeadStatusEnum


class LeadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_name: str
    primary_phone: str
    normalized_phone: str
    secondary_phone: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    city: str
    lead_source: str
    campaign: Optional[str] = None
    department: str
    service_interested: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_executive_id: Optional[str] = None
    lead_status: str
    priority: str
    next_followup_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class CreateLeadRequest(BaseModel):
    patient_name: str = Field(..., min_length=2, max_length=255)
    primary_phone: str = Field(..., min_length=7, max_length=50)
    secondary_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    city: str = "Hassan"
    lead_source: LeadSourceEnum = LeadSourceEnum.MANUAL
    campaign: Optional[str] = None
    department: str = "Fertility & IVF"
    service_interested: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_executive_id: Optional[str] = None
    priority: LeadPriorityEnum = LeadPriorityEnum.MEDIUM
    next_followup_at: Optional[datetime] = None
    notes: Optional[str] = None


class UpdateLeadRequest(BaseModel):
    patient_name: Optional[str] = None
    secondary_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    city: Optional[str] = None
    lead_source: Optional[LeadSourceEnum] = None
    department: Optional[str] = None
    service_interested: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_executive_id: Optional[str] = None
    lead_status: Optional[LeadStatusEnum] = None
    priority: Optional[LeadPriorityEnum] = None
    next_followup_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_archived: Optional[bool] = None


class LeadSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    branch_id: Optional[str] = None
    limit: int = 20


class ManualAssignRequest(BaseModel):
    new_executive_id: str
    reason: Optional[str] = "Manual Manager Assignment"


class AutoAssignRequest(BaseModel):
    reason: Optional[str] = "Automatic Round-Robin Assignment"


class LeadAssignmentHistorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    previous_executive_id: Optional[str] = None
    new_executive_id: str
    assigned_by: str
    assigned_at: datetime
    strategy: str
    reason: Optional[str] = None


class ChangeLeadStatusRequest(BaseModel):
    new_status: LeadStatusEnum
    reason: Optional[str] = None
    competitor_name: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class LeadStatusHistorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    changed_at: datetime
    reason: Optional[str] = None
    competitor_name: Optional[str] = None


class AddLeadNoteRequest(BaseModel):
    note: str = Field(..., min_length=2)


class LeadActivitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    activity_type: str
    title: str
    description: Optional[str] = None
    activity_metadata: Optional[dict] = None
    performed_by: Optional[str] = None
    performed_at: datetime
