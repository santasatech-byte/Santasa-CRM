"""
Hospital CRM - Follow-up Management Entity Models
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class FollowUpTypeEnum(str, enum.Enum):
    CALL = "Call"
    WHATSAPP = "WhatsApp"
    APPOINTMENT_CONFIRMATION = "Appointment Confirmation"
    GENERAL = "General"


class FollowUpStatusEnum(str, enum.Enum):
    SCHEDULED = "Scheduled"
    DUE = "Due"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    RESCHEDULED = "Rescheduled"
    MISSED = "Missed"


class FollowUp(BaseModel):
    __tablename__ = "followups"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    executive_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), default=FollowUpTypeEnum.CALL.value, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="Medium", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default=FollowUpStatusEnum.SCHEDULED.value, index=True, nullable=False)
    reminder_offset_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    reminder_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    executive: Mapped["User"] = relationship("User", foreign_keys=[executive_id])
