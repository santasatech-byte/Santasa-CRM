"""
Hospital CRM - Appointment & Conversion Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.modules.appointments.models import AppointmentStatusEnum, ConsultationOutcomeStatusEnum


class AppointmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    branch_id: Optional[str] = None
    doctor_id: Optional[str] = None
    booked_by: str
    appointment_at: datetime
    department: str
    service_type: str
    status: str
    notes: Optional[str] = None
    created_at: datetime


class BookAppointmentRequest(BaseModel):
    lead_id: str
    appointment_at: datetime
    service_type: str = "Initial Consultation"
    department: str = "Fertility & IVF"
    doctor_id: Optional[str] = None
    branch_id: Optional[str] = None
    notes: Optional[str] = None


class UpdateAppointmentStatusRequest(BaseModel):
    status: AppointmentStatusEnum
    notes: Optional[str] = None


class ConsultationOutcomeRequest(BaseModel):
    outcome_status: ConsultationOutcomeStatusEnum
    recommended_service: Optional[str] = None
    estimated_value: float = 0.0
    clinical_summary: Optional[str] = None


class ConsultationOutcomeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    appointment_id: str
    lead_id: str
    doctor_id: Optional[str] = None
    outcome_status: str
    recommended_service: Optional[str] = None
    estimated_value: float
    clinical_summary: Optional[str] = None
    recorded_by: str
    recorded_at: datetime


class RecordConversionRequest(BaseModel):
    lead_id: str
    converted_service: str
    conversion_value: float = Field(..., ge=0.0)
    appointment_id: Optional[str] = None
    notes: Optional[str] = None


class ConversionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    appointment_id: Optional[str] = None
    converted_service: str
    conversion_value: float
    converted_at: datetime
    converted_by: str
    notes: Optional[str] = None
