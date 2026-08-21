"""
Hospital CRM - Lead Activity Timeline Entity Model
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class ActivityTypeEnum(str, enum.Enum):
    LEAD_CREATED = "lead_created"
    LEAD_ASSIGNED = "lead_assigned"
    STATUS_CHANGED = "status_changed"
    NOTE_ADDED = "note_added"
    CALL_LOGGED = "call_logged"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    FOLLOWUP_COMPLETED = "followup_completed"
    APPOINTMENT_BOOKED = "appointment_booked"
    CONSULTATION_RECORDED = "consultation_recorded"
    WHATSAPP_MESSAGE = "whatsapp_message"
    EMAIL_SENT = "email_sent"


class LeadActivity(BaseModel):
    __tablename__ = "lead_activities"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Store arbitrary structured payload (audio URL, duration, custom tags)
    activity_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)
    
    performed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    performer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[performed_by])
