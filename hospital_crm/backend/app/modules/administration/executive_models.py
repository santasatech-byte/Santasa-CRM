"""
Hospital CRM - Executive Profile Entity Model
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class ExecutiveStatus(str, enum.Enum):
    ONLINE = "Online"
    AWAY = "Away"
    BUSY = "Busy"
    OFFLINE = "Offline"


class ExecutiveProfile(BaseModel):
    __tablename__ = "executive_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    manager_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    telephony_agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telephony_extension: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default=ExecutiveStatus.ONLINE.value, nullable=False)
    last_status_change_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    max_active_leads_capacity: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    is_available_for_lead_assignment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[manager_id])
