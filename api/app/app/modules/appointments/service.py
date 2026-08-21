"""
Hospital CRM - Appointment & Conversion Management Service
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.core.errors import NotFoundError, ValidationError
from app.modules.leads.models import Lead, LeadStatusEnum
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import ActivityTypeEnum
from app.modules.appointments.models import (
    Appointment,
    AppointmentStatusEnum,
    ConsultationOutcome,
    ConsultationOutcomeStatusEnum,
    Conversion
)


class AppointmentService:
    @classmethod
    def book_appointment(
        cls,
        db: Session,
        lead: Lead,
        appointment_at: datetime,
        service_type: str,
        department: str = "Fertility & IVF",
        doctor_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        notes: Optional[str] = None,
        booked_by_user_id: str = None
    ) -> Appointment:
        """Books an appointment, updates lead status to 'Appointment Booked', and records timeline."""
        appointment = Appointment(
            lead_id=lead.id,
            branch_id=branch_id or lead.branch_id,
            doctor_id=doctor_id,
            booked_by=booked_by_user_id,
            appointment_at=appointment_at,
            department=department,
            service_type=service_type,
            status=AppointmentStatusEnum.BOOKED.value,
            notes=notes
        )
        db.add(appointment)

        # Transition lead status
        lead.lead_status = LeadStatusEnum.APPOINTMENT_BOOKED.value
        lead.updated_by = booked_by_user_id

        db.commit()
        db.refresh(appointment)

        # Log Activity Timeline
        LeadActivityService.log_activity(
            db=db,
            lead_id=lead.id,
            activity_type=ActivityTypeEnum.APPOINTMENT_BOOKED,
            title="Appointment Booked",
            description=f"{service_type} on {appointment_at.strftime('%d %b %Y, %I:%M %p')}. Doctor ID: {doctor_id or 'General'}",
            performed_by_user_id=booked_by_user_id,
            metadata={"appointment_id": appointment.id, "appointment_at": appointment_at.isoformat()}
        )

        logger.info(f"Booked appointment id={appointment.id} for lead={lead.id} on {appointment_at.isoformat()}.")
        return appointment

    @classmethod
    def record_consultation_outcome(
        cls,
        db: Session,
        appointment_id: str,
        outcome_status: str,
        recommended_service: Optional[str],
        estimated_value: float,
        clinical_summary: Optional[str],
        recorded_by_user_id: str
    ) -> ConsultationOutcome:
        """Records doctor consultation outcome and marks appointment and lead as 'Consultation Done'."""
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        appointment = db.scalars(stmt).first()
        if not appointment:
            raise NotFoundError("Appointment", appointment_id)

        outcome = ConsultationOutcome(
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            doctor_id=appointment.doctor_id,
            outcome_status=outcome_status,
            recommended_service=recommended_service,
            estimated_value=estimated_value,
            clinical_summary=clinical_summary,
            recorded_by=recorded_by_user_id,
            recorded_at=datetime.now(timezone.utc)
        )
        db.add(outcome)

        appointment.status = AppointmentStatusEnum.COMPLETED.value
        
        lead = db.get(Lead, appointment.lead_id)
        if lead:
            lead.lead_status = LeadStatusEnum.CONSULTATION_DONE.value
            lead.updated_by = recorded_by_user_id

        db.commit()
        db.refresh(outcome)

        # Log timeline
        if lead:
            LeadActivityService.log_activity(
                db=db,
                lead_id=lead.id,
                activity_type=ActivityTypeEnum.CONSULTATION_RECORDED,
                title="Doctor Consultation Completed",
                description=f"Outcome: {outcome_status}. Recommended: {recommended_service or 'N/A'}. Est Value: ₹{estimated_value:,.2f}",
                performed_by_user_id=recorded_by_user_id,
                metadata={"outcome_id": outcome.id, "estimated_value": estimated_value}
            )

        logger.info(f"Recorded consultation outcome for appointment={appointment_id}. Outcome={outcome_status}.")
        return outcome

    @classmethod
    def record_conversion(
        cls,
        db: Session,
        lead_id: str,
        converted_service: str,
        conversion_value: float,
        appointment_id: Optional[str],
        converted_by_user_id: str,
        notes: Optional[str]
    ) -> Conversion:
        """Records patient treatment conversion/revenue and transitions lead to 'Converted'."""
        lead = db.get(Lead, lead_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)

        conversion = Conversion(
            lead_id=lead.id,
            appointment_id=appointment_id,
            converted_service=converted_service,
            conversion_value=conversion_value,
            converted_at=datetime.now(timezone.utc),
            converted_by=converted_by_user_id,
            notes=notes
        )
        db.add(conversion)

        lead.lead_status = LeadStatusEnum.CONVERTED.value
        lead.updated_by = converted_by_user_id

        db.commit()
        db.refresh(conversion)

        # Log timeline
        LeadActivityService.log_activity(
            db=db,
            lead_id=lead.id,
            activity_type=ActivityTypeEnum.STATUS_CHANGED,
            title="Patient Converted to Treatment",
            description=f"Package: {converted_service}. Revenue: ₹{conversion_value:,.2f}. Notes: {notes or 'N/A'}",
            performed_by_user_id=converted_by_user_id,
            metadata={"conversion_id": conversion.id, "conversion_value": conversion_value}
        )

        logger.info(f"Recorded conversion for lead={lead_id}: service='{converted_service}' value=₹{conversion_value}.")
        return conversion
