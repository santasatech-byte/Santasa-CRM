"""
Hospital CRM - Lead Assignment History Entity Model
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel


class LeadAssignmentHistory(BaseModel):
    __tablename__ = "lead_assignment_history"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    previous_executive_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    new_executive_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    assigned_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(50), default="Manual", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    previous_executive: Mapped[Optional["User"]] = relationship("User", foreign_keys=[previous_executive_id])
    new_executive: Mapped["User"] = relationship("User", foreign_keys=[new_executive_id])
    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])
