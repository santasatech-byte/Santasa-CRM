"""
Hospital CRM - Appointments, Outcomes & Conversions API Router
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions, check_resource_access
from app.core.errors import NotFoundError, ForbiddenError, ValidationError
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead
from app.modules.appointments.models import Appointment, ConsultationOutcome, Conversion
from app.modules.appointments.service import AppointmentService
from app.modules.appointments.schemas import (
    AppointmentSummary,
    BookAppointmentRequest,
    UpdateAppointmentStatusRequest,
    ConsultationOutcomeRequest,
    ConsultationOutcomeSummary,
    RecordConversionRequest,
    ConversionSummary
)

router = APIRouter(tags=["Appointments, Outcomes & Conversions"])


# ==========================================
# Appointments
# ==========================================

@router.post("/appointments", response_model=AppointmentSummary, status_code=status.HTTP_201_CREATED)
async def book_appointment(
    request: BookAppointmentRequest,
    current_user: User = Depends(require_permission(Permissions.BOOK_APPOINTMENT)),
    db: Session = Depends(get_db)
):
    """Books an appointment, sets lead status to 'Appointment Booked', and logs timeline."""
    lead = db.get(Lead, request.lead_id)
    if not lead:
        raise NotFoundError("Lead", request.lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to book appointments for this lead.")

    appointment = AppointmentService.book_appointment(
        db=db,
        lead=lead,
        appointment_at=request.appointment_at,
        service_type=request.service_type,
        department=request.department,
        doctor_id=request.doctor_id,
        branch_id=request.branch_id or lead.branch_id,
        notes=request.notes,
        booked_by_user_id=current_user.id
    )
    return AppointmentSummary.model_validate(appointment)


@router.get("/appointments", response_model=List[AppointmentSummary], status_code=status.HTTP_200_OK)
async def list_appointments(
    doctor_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    appointment_status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists appointments with doctor and branch scoping."""
    stmt = select(Appointment)

    if current_user.role == UserRole.DOCTOR.value:
        stmt = stmt.where(Appointment.doctor_id == current_user.id)
    elif current_user.role == UserRole.CRM_MANAGER.value and current_user.branch_id:
        stmt = stmt.where(Appointment.branch_id == current_user.branch_id)

    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if branch_id:
        stmt = stmt.where(Appointment.branch_id == branch_id)
    if lead_id:
        stmt = stmt.where(Appointment.lead_id == lead_id)
    if appointment_status:
        stmt = stmt.where(Appointment.status == appointment_status)

    stmt = stmt.order_by(Appointment.appointment_at.asc()).offset(offset).limit(limit)
    appointments = db.scalars(stmt).all()
    return [AppointmentSummary.model_validate(a) for a in appointments]


@router.post("/appointments/{appointment_id}/outcome", response_model=ConsultationOutcomeSummary, status_code=status.HTTP_201_CREATED)
async def record_consultation_outcome(
    appointment_id: str,
    request: ConsultationOutcomeRequest,
    current_user: User = Depends(require_permission(Permissions.RECORD_CONSULTATION_OUTCOME)),
    db: Session = Depends(get_db)
):
    """Doctor records consultation outcome, transitions lead to 'Consultation Done'."""
    outcome = AppointmentService.record_consultation_outcome(
        db=db,
        appointment_id=appointment_id,
        outcome_status=request.outcome_status.value,
        recommended_service=request.recommended_service,
        estimated_value=request.estimated_value,
        clinical_summary=request.clinical_summary,
        recorded_by_user_id=current_user.id
    )
    return ConsultationOutcomeSummary.model_validate(outcome)


# ==========================================
# Conversions & Revenue
# ==========================================

@router.post("/conversions", response_model=ConversionSummary, status_code=status.HTTP_201_CREATED)
async def record_conversion(
    request: RecordConversionRequest,
    current_user: User = Depends(require_permission(Permissions.RECORD_CONVERSION)),
    db: Session = Depends(get_db)
):
    """Records patient treatment conversion/revenue, transitions lead to 'Converted'."""
    conversion = AppointmentService.record_conversion(
        db=db,
        lead_id=request.lead_id,
        converted_service=request.converted_service,
        conversion_value=request.conversion_value,
        appointment_id=request.appointment_id,
        converted_by_user_id=current_user.id,
        notes=request.notes
    )
    return ConversionSummary.model_validate(conversion)


@router.get("/conversions", response_model=List[ConversionSummary], status_code=status.HTTP_200_OK)
async def list_conversions(
    lead_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists conversion records with scoping."""
    stmt = select(Conversion)
    if lead_id:
        stmt = stmt.where(Conversion.lead_id == lead_id)
    stmt = stmt.order_by(Conversion.converted_at.desc()).offset(offset).limit(limit)
    conversions = db.scalars(stmt).all()
    return [ConversionSummary.model_validate(c) for c in conversions]
