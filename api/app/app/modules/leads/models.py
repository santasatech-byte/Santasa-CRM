"""
Hospital CRM - Lead Management Entity Models
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import BaseModel
import enum


class LeadSourceEnum(str, enum.Enum):
    INCOMING_CALL = "Incoming Call"
    IVR = "IVR"
    WEBSITE = "Website"
    GOOGLE_ADS = "Google Ads"
    META_ADS = "Meta Ads"
    WHATSAPP = "WhatsApp"
    WALK_IN = "Walk-in"
    REFERRAL = "Referral"
    EXISTING_PATIENT = "Existing Patient"
    CAMPAIGN = "Campaign"
    MANUAL = "Manual"
    OTHER = "Other"


class LeadPriorityEnum(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class LeadStatusEnum(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    FOLLOW_UP = "Follow-up"
    APPOINTMENT_BOOKED = "Appointment Booked"
    CONSULTATION_DONE = "Consultation Done"
    CONVERTED = "Converted"
    NO_RESPONSE = "No Response"
    NOT_INTERESTED = "Not Interested"
    WRONG_NUMBER = "Wrong Number"
    LOST_TO_COMPETITION = "Lost to Competition"
    DUPLICATE = "Duplicate"
    CLOSED = "Closed"


class Lead(BaseModel):
    __tablename__ = "leads"

    patient_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    primary_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_phone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    secondary_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Hassan", nullable=False)
    
    lead_source: Mapped[str] = mapped_column(String(50), default=LeadSourceEnum.MANUAL.value, index=True, nullable=False)
    campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[str] = mapped_column(String(100), default="Fertility & IVF", index=True, nullable=False)
    service_interested: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_executive_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    lead_status: Mapped[str] = mapped_column(String(50), default=LeadStatusEnum.NEW.value, index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=LeadPriorityEnum.MEDIUM.value, index=True, nullable=False)
    
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    branch: Mapped[Optional["Branch"]] = relationship("Branch", foreign_keys=[branch_id])
    assigned_executive: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_executive_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
