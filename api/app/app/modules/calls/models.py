"""
Hospital CRM - Call & Recording Entity Models
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class CallDirectionEnum(str, enum.Enum):
    INCOMING = "Incoming"
    OUTGOING = "Outgoing"


class CallStatusEnum(str, enum.Enum):
    INITIATED = "Initiated"
    RINGING = "Ringing"
    ANSWERED = "Answered"
    COMPLETED = "Completed"
    BUSY = "Busy"
    NO_ANSWER = "No Answer"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class RecordingStatusEnum(str, enum.Enum):
    UNAVAILABLE = "Unavailable"
    PROCESSING = "Processing"
    AVAILABLE = "Available"
    FAILED = "Failed"


class Call(BaseModel):
    __tablename__ = "calls"

    external_call_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_phone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    
    direction: Mapped[str] = mapped_column(String(20), default=CallDirectionEnum.INCOMING.value, index=True, nullable=False)
    executive_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default=CallStatusEnum.INITIATED.value, index=True, nullable=False)
    recording_status: Mapped[str] = mapped_column(String(50), default=RecordingStatusEnum.UNAVAILABLE.value, nullable=False)
    recording_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recording_duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    provider_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    lead: Mapped[Optional["Lead"]] = relationship("Lead", foreign_keys=[lead_id])
    executive: Mapped[Optional["User"]] = relationship("User", foreign_keys=[executive_id])
    branch: Mapped[Optional["Branch"]] = relationship("Branch", foreign_keys=[branch_id])
