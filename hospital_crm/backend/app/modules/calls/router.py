"""
Hospital CRM - Telephony & Call Management API Router
Handles incoming provider webhooks, click-to-call, status callbacks, and call history.
"""
from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions, check_resource_access
from app.core.errors import NotFoundError, ForbiddenError, ValidationError
from app.core.logging import logger
from app.adapters.telephony_factory import get_telephony_provider
from app.adapters.telephony_base import CallInitiateRequest
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead
from app.modules.calls.models import Call, CallDirectionEnum, CallStatusEnum, RecordingStatusEnum
from app.modules.calls.service import CallProcessingService
from app.modules.calls.schemas import (
    CallSummary,
    IncomingCallWebhookPayload,
    CallStatusWebhookPayload,
    ClickToCallRequest
)

router = APIRouter(prefix="/telephony", tags=["Telephony & Call Management"])


# ==========================================
# Telephony Webhook Ingress (Rule 54)
# ==========================================

@router.post("/incoming-webhook", response_model=CallSummary, status_code=status.HTTP_200_OK)
async def handle_incoming_call_webhook(
    payload: IncomingCallWebhookPayload,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook ingress for incoming IVR calls from Exotel/Telephony provider.
    Verifies signature, matches/creates patient lead, auto-assigns executive, and logs call.
    """
    call = CallProcessingService.process_incoming_call(
        db=db,
        external_call_id=payload.CallSid,
        caller_phone=payload.From,
        ivr_number=payload.To,
        provider_name="exotel",
        raw_metadata=payload.model_dump()
    )
    return CallSummary.model_validate(call)


@router.post("/status-webhook", status_code=status.HTTP_200_OK)
async def handle_call_status_webhook(
    payload: CallStatusWebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Webhook callback for call state updates (answered, completed, duration, recording URL).
    """
    call = CallProcessingService.process_call_status_update(
        db=db,
        external_call_id=payload.CallSid,
        status=payload.Status,
        duration_seconds=payload.Duration or 0,
        recording_url=payload.RecordingUrl,
        raw_metadata=payload.model_dump()
    )
    return {"success": True, "call_id": call.id if call else None}


# ==========================================
# Click-to-Call Outbound Initiation (Rule 18)
# ==========================================

@router.post("/click-to-call", response_model=CallSummary, status_code=status.HTTP_201_CREATED)
async def click_to_call(
    req: ClickToCallRequest,
    current_user: User = Depends(require_permission(Permissions.MAKE_CALL)),
    db: Session = Depends(get_db)
):
    """
    Initiates outbound click-to-call between authenticated executive and patient lead.
    """
    lead_stmt = select(Lead).where(Lead.id == req.lead_id)
    lead = db.scalars(lead_stmt).first()
    if not lead:
        raise NotFoundError("Lead", req.lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to call this lead.")

    agent_phone = req.executive_phone or current_user.phone or "08047190000"
    
    # Request telephony adapter
    adapter = get_telephony_provider()
    call_request = CallInitiateRequest(
        agent_phone=agent_phone,
        patient_phone=lead.normalized_phone,
        lead_id=lead.id
    )
    provider_res = await adapter.make_call(call_request)

    # Create Outgoing Call Record
    call = Call(
        external_call_id=provider_res.provider_call_id,
        lead_id=lead.id,
        phone_number=lead.primary_phone,
        normalized_phone=lead.normalized_phone,
        direction=CallDirectionEnum.OUTGOING.value,
        executive_id=current_user.id,
        branch_id=lead.branch_id,
        started_at=datetime.now(timezone.utc),
        status=CallStatusEnum.INITIATED.value,
        recording_status=RecordingStatusEnum.UNAVAILABLE.value,
        provider=adapter.provider_name,
        provider_metadata=provider_res.raw_response
    )
    db.add(call)
    
    # Update lead last_contacted_at
    lead.last_contacted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(call)

    logger.info(f"Click-to-call initiated by {current_user.email} to patient {lead.normalized_phone} (Sid={call.external_call_id}).")
    return CallSummary.model_validate(call)


# ==========================================
# Call History & Logs
# ==========================================

@router.get("/calls", response_model=List[CallSummary], status_code=status.HTTP_200_OK)
async def list_calls(
    direction: Optional[str] = None,
    call_status: Optional[str] = None,
    lead_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists call history with role-based scoping."""
    stmt = select(Call)

    if current_user.role == UserRole.CRM_EXECUTIVE.value:
        stmt = stmt.where(Call.executive_id == current_user.id)
    elif current_user.role == UserRole.CRM_MANAGER.value and current_user.branch_id:
        stmt = stmt.where(Call.branch_id == current_user.branch_id)

    if direction:
        stmt = stmt.where(Call.direction == direction)
    if call_status:
        stmt = stmt.where(Call.status == call_status)
    if lead_id:
        stmt = stmt.where(Call.lead_id == lead_id)
    if branch_id:
        stmt = stmt.where(Call.branch_id == branch_id)

    stmt = stmt.order_by(Call.started_at.desc()).offset(offset).limit(limit)
    calls = db.scalars(stmt).all()
    return [CallSummary.model_validate(c) for c in calls]
