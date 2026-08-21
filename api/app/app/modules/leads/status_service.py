"""
Hospital CRM - Lead Status State Machine & Workflow Service
Enforces status transition rules, closure outcome requirements, and audit logging.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.core.errors import ValidationError, NotFoundError
from app.modules.leads.models import Lead, LeadStatusEnum
from app.modules.leads.status_models import LeadStatusHistory


class LeadStatusService:
    @classmethod
    def change_lead_status(
        cls,
        db: Session,
        lead: Lead,
        new_status: LeadStatusEnum,
        changed_by_user_id: str,
        reason: Optional[str] = None,
        competitor_name: Optional[str] = None,
        next_followup_at: Optional[datetime] = None
    ) -> Lead:
        """
        Validates and transitions lead status while recording immutable status history.
        """
        old_status = lead.lead_status

        # 1. Rule: When moving to Follow-up, require next_followup_at
        if new_status == LeadStatusEnum.FOLLOW_UP:
            if not next_followup_at and not lead.next_followup_at:
                raise ValidationError("Next follow-up date and time is required when setting status to 'Follow-up'.")
            if next_followup_at:
                lead.next_followup_at = next_followup_at

        # 2. Rule: Lost to Competition requires reason and competitor
        if new_status == LeadStatusEnum.LOST_TO_COMPETITION:
            if not reason or not competitor_name:
                raise ValidationError("Competitor name and reason are required when marking lead as 'Lost to Competition'.")

        # 3. Rule: Not Interested / Wrong Number / Insurance Enquiry requires reason
        if new_status in [
            LeadStatusEnum.NOT_INTERESTED,
            LeadStatusEnum.WRONG_NUMBER,
            LeadStatusEnum.CLOSED
        ]:
            if not reason:
                raise ValidationError(f"A reason is required when closing lead as '{new_status.value}'.")

        # Apply status change
        lead.lead_status = new_status.value
        lead.updated_by = changed_by_user_id

        # Record History
        history = LeadStatusHistory(
            lead_id=lead.id,
            old_status=old_status,
            new_status=new_status.value,
            changed_by=changed_by_user_id,
            changed_at=datetime.now(timezone.utc),
            reason=reason,
            competitor_name=competitor_name
        )
        db.add(history)
        db.commit()
        db.refresh(lead)

        logger.info(
            f"Lead {lead.id} status transitioned: '{old_status}' -> '{new_status.value}' "
            f"by user {changed_by_user_id}. Reason: {reason}"
        )
        return lead
