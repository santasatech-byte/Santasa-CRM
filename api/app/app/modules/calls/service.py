"""
Hospital CRM - Call Processing & Webhook Service
Handles incoming caller lead resolution, auto-assignment, call state transitions,
and recording attachment with idempotency protection.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.core.config import settings
from app.adapters.telephony_factory import get_telephony_provider
from app.modules.calls.models import Call, CallDirectionEnum, CallStatusEnum, RecordingStatusEnum
from app.modules.leads.models import Lead, LeadStatusEnum, LeadPriorityEnum, LeadSourceEnum
from app.modules.leads.assignment_service import LeadAssignmentService
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import ActivityTypeEnum


class CallProcessingService:
    @classmethod
    def process_incoming_call(
        cls,
        db: Session,
        external_call_id: str,
        caller_phone: str,
        ivr_number: Optional[str] = None,
        branch_id: Optional[str] = None,
        provider_name: str = "exotel",
        raw_metadata: Optional[Dict[str, Any]] = None
    ) -> Call:
        """
        Main Incoming Call Pipeline:
        1. Check idempotency (existing external_call_id)
        2. Normalize caller phone
        3. Match existing lead or create fresh lead
        4. Assign executive via Round-Robin if unassigned
        5. Create & return Call record
        6. Append event to lead timeline
        """
        adapter = get_telephony_provider(provider_name)
        normalized_phone = adapter.normalize_phone_number(caller_phone)

        # 1. Idempotency check: if call already created for this external ID, return it
        stmt = select(Call).where(Call.external_call_id == external_call_id)
        existing_call = db.scalars(stmt).first()
        if existing_call:
            logger.info(f"Duplicate incoming call webhook received for external_call_id={external_call_id}. Reusing existing call record.")
            return existing_call

        # 2. Search existing lead by normalized phone
        lead_stmt = select(Lead).where(
            Lead.normalized_phone == normalized_phone,
            Lead.is_archived == False
        ).order_by(Lead.created_at.desc())
        lead = db.scalars(lead_stmt).first()

        assigned_exec_id = None

        if not lead:
            # 3. Create fresh lead
            lead = Lead(
                patient_name=f"Inquiry {caller_phone[-4:]}",
                primary_phone=caller_phone,
                normalized_phone=normalized_phone,
                city="Hassan",
                lead_source=LeadSourceEnum.INCOMING_CALL.value,
                department="Fertility & IVF",
                branch_id=branch_id,
                lead_status=LeadStatusEnum.NEW.value,
                priority=LeadPriorityEnum.HIGH.value,
                notes=f"Auto-created from Incoming IVR Call ({ivr_number or 'Main Line'})"
            )
            db.add(lead)
            db.flush()

            # 4. Auto-assign executive via round robin
            try:
                assigned_exec = LeadAssignmentService.assign_round_robin(
                    db=db,
                    lead=lead,
                    assigned_by_user_id="system_ivr",
                    reason="Automated Incoming IVR Lead Assignment"
                )
                assigned_exec_id = assigned_exec.id
            except Exception as e:
                logger.warning(f"Could not auto-assign executive for incoming call: {str(e)}")
        else:
            assigned_exec_id = lead.assigned_executive_id
            logger.info(f"Incoming call matched existing lead id={lead.id} ({lead.patient_name}).")

        # 5. Create Call Entity
        call = Call(
            external_call_id=external_call_id,
            lead_id=lead.id,
            phone_number=caller_phone,
            normalized_phone=normalized_phone,
            direction=CallDirectionEnum.INCOMING.value,
            executive_id=assigned_exec_id,
            branch_id=branch_id or lead.branch_id,
            started_at=datetime.now(timezone.utc),
            status=CallStatusEnum.RINGING.value,
            recording_status=RecordingStatusEnum.UNAVAILABLE.value,
            provider=provider_name,
            provider_metadata=raw_metadata or {}
        )
        db.add(call)
        db.commit()
        db.refresh(call)

        # 6. Log Timeline Activity
        LeadActivityService.log_activity(
            db=db,
            lead_id=lead.id,
            activity_type=ActivityTypeEnum.CALL_LOGGED,
            title="Incoming Call Received",
            description=f"Incoming call from {caller_phone} via {provider_name.upper()} (IVR: {ivr_number or 'Main'}). Status: Ringing.",
            performed_by_user_id=assigned_exec_id,
            metadata={"external_call_id": external_call_id, "direction": "Incoming"}
        )

        return call

    @classmethod
    def process_call_status_update(
        cls,
        db: Session,
        external_call_id: str,
        status: str,
        duration_seconds: int = 0,
        recording_url: Optional[str] = None,
        raw_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Call]:
        """
        Processes status update webhooks (Answered, Completed, Busy, No Answer, Recording Available).
        """
        stmt = select(Call).where(Call.external_call_id == external_call_id)
        call = db.scalars(stmt).first()
        if not call:
            logger.warning(f"Call status callback received for unknown external_call_id={external_call_id}.")
            return None

        status_lower = status.lower()
        if "completed" in status_lower:
            call.status = CallStatusEnum.COMPLETED.value
            call.ended_at = datetime.now(timezone.utc)
            call.duration = duration_seconds
        elif "busy" in status_lower:
            call.status = CallStatusEnum.BUSY.value
        elif "no-answer" in status_lower or "no_answer" in status_lower:
            call.status = CallStatusEnum.NO_ANSWER.value
        elif "answered" in status_lower:
            call.status = CallStatusEnum.ANSWERED.value
            if not call.answered_at:
                call.answered_at = datetime.now(timezone.utc)

        # Attach recording if provided
        if recording_url:
            call.recording_url = recording_url
            call.recording_status = RecordingStatusEnum.AVAILABLE.value
            call.recording_duration = duration_seconds

        if raw_metadata:
            call.provider_metadata.update(raw_metadata)

        db.commit()
        db.refresh(call)

        # Update timeline if lead is attached
        if call.lead_id and (recording_url or call.status == CallStatusEnum.COMPLETED.value):
            LeadActivityService.log_activity(
                db=db,
                lead_id=call.lead_id,
                activity_type=ActivityTypeEnum.CALL_LOGGED,
                title=f"Call {call.status.capitalize()} ({call.direction})",
                description=f"Call ended with status '{call.status}'. Duration: {call.duration}s.",
                performed_by_user_id=call.executive_id,
                metadata={
                    "external_call_id": call.external_call_id,
                    "duration": call.duration,
                    "recording_url": call.recording_url,
                    "recording_status": call.recording_status
                }
            )

        logger.info(f"Updated call external_call_id={external_call_id} to status={call.status} duration={call.duration}s.")
        return call
