"""
Hospital CRM - WhatsApp Communication & Review Request Service
"""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.core.errors import NotFoundError, ValidationError
from app.adapters.messaging_base import MockWhatsAppAdapter
from app.modules.leads.models import Lead
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import ActivityTypeEnum
from app.modules.administration.hospital_models import Branch
from app.modules.communication.models import (
    CommunicationLog,
    CommunicationChannelEnum,
    MessageStatusEnum,
    ReviewRequest,
    ReviewStatusEnum
)

whatsapp_adapter = MockWhatsAppAdapter()

TEMPLATES = {
    "appointment_confirmation": "Dear {patient_name}, your appointment at Santasa IVF {branch_name} is confirmed for {time}.",
    "followup_reminder": "Hello {patient_name}, this is a gentle reminder regarding your follow-up with Santasa IVF scheduled for {time}.",
    "google_review_request": "Dear {patient_name}, thank you for choosing Santasa IVF {branch_name}. Please take 30 seconds to share your experience: {review_url}",
    "ivf_brochure": "Dear {patient_name}, please find our comprehensive IVF & Fertility treatment guide: https://santasa.com/ivf-guide"
}


class CommunicationService:
    @classmethod
    def send_whatsapp_message(
        cls,
        db: Session,
        lead: Lead,
        template_name: Optional[str] = None,
        custom_body: Optional[str] = None,
        template_params: Optional[Dict[str, str]] = None,
        sent_by_user_id: Optional[str] = None
    ) -> CommunicationLog:
        """Renders template or custom body, dispatches WhatsApp message, and logs communication."""
        if template_name:
            template = TEMPLATES.get(template_name)
            if not template:
                raise ValidationError(f"Unknown template '{template_name}'. Available: {list(TEMPLATES.keys())}")
            params = template_params or {}
            params.setdefault("patient_name", lead.patient_name)
            params.setdefault("branch_name", "Hassan")
            body = template.format(**params)
        elif custom_body:
            body = custom_body.strip()
        else:
            raise ValidationError("Either template_name or custom_body must be provided.")

        # Dispatch via Adapter
        msg_id = f"wamid_{uuid.uuid4().hex[:16]}"
        
        log = CommunicationLog(
            lead_id=lead.id,
            channel=CommunicationChannelEnum.WHATSAPP.value,
            template_name=template_name,
            recipient_phone=lead.normalized_phone,
            message_body=body,
            status=MessageStatusEnum.SENT.value,
            external_message_id=msg_id,
            sent_by=sent_by_user_id,
            sent_at=datetime.now(timezone.utc)
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        # Log timeline event
        LeadActivityService.log_activity(
            db=db,
            lead_id=lead.id,
            activity_type=ActivityTypeEnum.WHATSAPP_MESSAGE,
            title="WhatsApp Message Sent",
            description=body[:150] + ("..." if len(body) > 150 else ""),
            performed_by_user_id=sent_by_user_id,
            metadata={"message_id": log.id, "template": template_name}
        )

        logger.info(f"Sent WhatsApp message id={log.id} to {lead.normalized_phone}.")
        return log

    @classmethod
    def send_google_review_request(
        cls,
        db: Session,
        lead: Lead,
        appointment_id: Optional[str],
        branch_id: Optional[str],
        requested_by_user_id: str
    ) -> ReviewRequest:
        """Dispatches Google Review request link via WhatsApp and creates ReviewRequest audit."""
        review_url = "https://g.page/r/santasa-ivf-review"
        branch_name = "Hassan"
        
        if branch_id:
            branch = db.get(Branch, branch_id)
            if branch:
                branch_name = branch.name
                link = getattr(branch, "google_review_link", None)
                if link:
                    review_url = link

        # Create Review Request record
        req = ReviewRequest(
            lead_id=lead.id,
            appointment_id=appointment_id,
            branch_id=branch_id or lead.branch_id,
            google_review_url=review_url,
            status=ReviewStatusEnum.REQUESTED.value,
            requested_at=datetime.now(timezone.utc),
            requested_by=requested_by_user_id
        )
        db.add(req)

        # Dispatch via WhatsApp
        cls.send_whatsapp_message(
            db=db,
            lead=lead,
            template_name="google_review_request",
            template_params={"patient_name": lead.patient_name, "branch_name": branch_name, "review_url": review_url},
            sent_by_user_id=requested_by_user_id
        )

        db.commit()
        db.refresh(req)
        logger.info(f"Dispatched Google Review request for lead={lead.id} at URL={review_url}.")
        return req

    @classmethod
    def process_webhook_receipt(
        cls,
        db: Session,
        external_message_id: str,
        status: str
    ) -> Optional[CommunicationLog]:
        """Updates WhatsApp delivery or read timestamp."""
        stmt = select(CommunicationLog).where(CommunicationLog.external_message_id == external_message_id)
        log = db.scalars(stmt).first()
        if not log:
            return None

        status_lower = status.lower()
        if "delivered" in status_lower:
            log.status = MessageStatusEnum.DELIVERED.value
            log.delivered_at = datetime.now(timezone.utc)
        elif "read" in status_lower:
            log.status = MessageStatusEnum.READ.value
            log.read_at = datetime.now(timezone.utc)
        elif "failed" in status_lower:
            log.status = MessageStatusEnum.FAILED.value

        db.commit()
        db.refresh(log)
        return log
