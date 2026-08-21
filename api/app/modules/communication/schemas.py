"""
Hospital CRM - WhatsApp Communication & Review Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class CommunicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    channel: str
    template_name: Optional[str] = None
    recipient_phone: str
    message_body: str
    status: str
    external_message_id: Optional[str] = None
    sent_by: Optional[str] = None
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class SendWhatsAppRequest(BaseModel):
    lead_id: str
    template_name: Optional[str] = None
    custom_body: Optional[str] = None
    template_params: Optional[Dict[str, str]] = None


class SendReviewRequest(BaseModel):
    lead_id: str
    appointment_id: Optional[str] = None
    branch_id: Optional[str] = None


class ReviewRequestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    appointment_id: Optional[str] = None
    branch_id: Optional[str] = None
    google_review_url: str
    status: str
    requested_at: datetime
    requested_by: str


class WhatsAppWebhookPayload(BaseModel):
    message_id: str
    status: str
