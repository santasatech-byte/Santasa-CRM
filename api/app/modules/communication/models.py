"""
Hospital CRM - WhatsApp Communication & Google Review Models
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class CommunicationChannelEnum(str, enum.Enum):
    WHATSAPP = "WhatsApp"
    SMS = "SMS"
    EMAIL = "Email"


class MessageStatusEnum(str, enum.Enum):
    SENT = "Sent"
    DELIVERED = "Delivered"
    READ = "Read"
    FAILED = "Failed"


class ReviewStatusEnum(str, enum.Enum):
    REQUESTED = "Requested"
    CLICKED = "Clicked"
    COMPLETED = "Completed"
    DECLINED = "Declined"


class CommunicationLog(BaseModel):
    __tablename__ = "communication_logs"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default=CommunicationChannelEnum.WHATSAPP.value, index=True, nullable=False)
    template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default=MessageStatusEnum.SENT.value, index=True, nullable=False)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    
    sent_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])


class ReviewRequest(BaseModel):
    __tablename__ = "review_requests"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    appointment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    
    google_review_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=ReviewStatusEnum.REQUESTED.value, nullable=False)
    
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", foreign_keys=[appointment_id])
