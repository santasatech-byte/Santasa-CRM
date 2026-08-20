"""
Hospital CRM - WhatsApp Communication & Review Request API Router
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions, check_resource_access
from app.core.errors import NotFoundError, ForbiddenError
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead
from app.modules.communication.models import CommunicationLog, ReviewRequest
from app.modules.communication.service import CommunicationService
from app.modules.communication.schemas import (
    CommunicationSummary,
    SendWhatsAppRequest,
    SendReviewRequest,
    ReviewRequestSummary,
    WhatsAppWebhookPayload
)

router = APIRouter(prefix="/communication", tags=["WhatsApp Communication & Google Reviews"])


@router.post("/whatsapp/send", response_model=CommunicationSummary, status_code=status.HTTP_201_CREATED)
async def send_whatsapp(
    request: SendWhatsAppRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Dispatches a templated or custom WhatsApp message to a patient lead."""
    lead = db.get(Lead, request.lead_id)
    if not lead:
        raise NotFoundError("Lead", request.lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to send messages to this lead.")

    log = CommunicationService.send_whatsapp_message(
        db=db,
        lead=lead,
        template_name=request.template_name,
        custom_body=request.custom_body,
        template_params=request.template_params,
        sent_by_user_id=current_user.id
    )
    return CommunicationSummary.model_validate(log)


@router.post("/whatsapp/review-request", response_model=ReviewRequestSummary, status_code=status.HTTP_201_CREATED)
async def send_review_request(
    request: SendReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Dispatches Google review link to patient after consultation and creates audit record."""
    lead = db.get(Lead, request.lead_id)
    if not lead:
        raise NotFoundError("Lead", request.lead_id)

    req = CommunicationService.send_google_review_request(
        db=db,
        lead=lead,
        appointment_id=request.appointment_id,
        branch_id=request.branch_id,
        requested_by_user_id=current_user.id
    )
    return ReviewRequestSummary.model_validate(req)


@router.get("/logs", response_model=List[CommunicationSummary], status_code=status.HTTP_200_OK)
async def list_communication_logs(
    lead_id: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists communication logs with filters."""
    stmt = select(CommunicationLog)
    if lead_id:
        stmt = stmt.where(CommunicationLog.lead_id == lead_id)
    if channel:
        stmt = stmt.where(CommunicationLog.channel == channel)

    stmt = stmt.order_by(CommunicationLog.sent_at.desc()).offset(offset).limit(limit)
    logs = db.scalars(stmt).all()
    return [CommunicationSummary.model_validate(l) for l in logs]


@router.post("/whatsapp-webhook", status_code=status.HTTP_200_OK)
async def handle_whatsapp_webhook(
    payload: WhatsAppWebhookPayload,
    db: Session = Depends(get_db)
):
    """Processes WhatsApp message delivery and read receipts."""
    CommunicationService.process_webhook_receipt(
        db=db,
        external_message_id=payload.message_id,
        status=payload.status
    )
    return {"success": True}
