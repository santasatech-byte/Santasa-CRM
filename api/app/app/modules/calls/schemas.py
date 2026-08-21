"""
Hospital CRM - Call Management Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class CallSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_call_id: str
    lead_id: Optional[str] = None
    phone_number: str
    normalized_phone: str
    direction: str
    executive_id: Optional[str] = None
    branch_id: Optional[str] = None
    started_at: datetime
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration: int
    status: str
    recording_status: str
    recording_url: Optional[str] = None
    recording_duration: int
    provider: str
    created_at: datetime


class IncomingCallWebhookPayload(BaseModel):
    CallSid: str
    From: str
    To: Optional[str] = None
    DialWhomNumber: Optional[str] = None
    Direction: Optional[str] = "incoming"


class CallStatusWebhookPayload(BaseModel):
    CallSid: str
    Status: str
    Duration: Optional[int] = 0
    RecordingUrl: Optional[str] = None


class ClickToCallRequest(BaseModel):
    lead_id: str
    executive_phone: Optional[str] = None
