"""
Hospital CRM - Appointments, Consultation Outcomes & Conversions Models
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class AppointmentStatusEnum(str, enum.Enum):
    BOOKED = "Booked"
    CONFIRMED = "Confirmed"
    ARRIVED = "Arrived"
    IN_CONSULTATION = "In Consultation"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    NO_SHOW = "No Show"
    RESCHEDULED = "Rescheduled"


class ConsultationOutcomeStatusEnum(str, enum.Enum):
    RECOMMENDED_TREATMENT = "Recommended Treatment"
    FOLLOW_UP_NEEDED = "Follow-up Needed"
    TESTS_PRESCRIBED = "Tests Prescribed"
    NOT_SUITABLE = "Not Suitable for Treatment"
    SECOND_OPINION = "Second Opinion Needed"
    DECLINED = "Declined"


class Appointment(BaseModel):
    __tablename__ = "appointments"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    doctor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    booked_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)

    appointment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(100), default="Fertility & IVF", nullable=False)
    service_type: Mapped[str] = mapped_column(String(255), default="Initial Consultation", nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default=AppointmentStatusEnum.BOOKED.value, index=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    branch: Mapped[Optional["Branch"]] = relationship("Branch", foreign_keys=[branch_id])
    doctor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[doctor_id])
    booker: Mapped["User"] = relationship("User", foreign_keys=[booked_by])


class ConsultationOutcome(BaseModel):
    __tablename__ = "consultation_outcomes"

    appointment_id: Mapped[str] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    outcome_status: Mapped[str] = mapped_column(String(100), nullable=False)
    recommended_service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    clinical_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    recorded_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    appointment: Mapped["Appointment"] = relationship("Appointment", foreign_keys=[appointment_id])
    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])


class Conversion(BaseModel):
    __tablename__ = "conversions"

    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False)
    appointment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)

    converted_service: Mapped[str] = mapped_column(String(255), nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    converted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    converted_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", foreign_keys=[appointment_id])
