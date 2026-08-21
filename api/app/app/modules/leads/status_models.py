"""
Hospital CRM - Lead Status History Entity Model
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel


class LeadStatusHistory(BaseModel):
    __tablename__ = "lead_status_history"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    changer: Mapped["User"] = relationship("User", foreign_keys=[changed_by])
