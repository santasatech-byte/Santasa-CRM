"""
Hospital CRM - Follow-up Management & Reminder Engine Service
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from app.core.logging import logger
from app.core.errors import NotFoundError, ValidationError, ForbiddenError
from app.modules.leads.models import Lead, LeadStatusEnum
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import ActivityTypeEnum
from app.modules.followups.models import FollowUp, FollowUpStatusEnum, FollowUpTypeEnum


class FollowUpService:
    @classmethod
    def schedule_followup(
        cls,
        db: Session,
        lead: Lead,
        executive_id: str,
        scheduled_at: datetime,
        followup_type: FollowUpTypeEnum = FollowUpTypeEnum.CALL,
        priority: str = "Medium",
        notes: Optional[str] = None,
        reminder_offset_minutes: int = 15,
        created_by_user_id: Optional[str] = None
    ) -> FollowUp:
        """Schedules a new follow-up and updates lead status and next action timestamp."""
        followup = FollowUp(
            lead_id=lead.id,
            executive_id=executive_id,
            scheduled_at=scheduled_at,
            type=followup_type.value,
            priority=priority,
            notes=notes,
            status=FollowUpStatusEnum.SCHEDULED.value,
            reminder_offset_minutes=reminder_offset_minutes,
            reminder_processed=False,
            created_by=created_by_user_id
        )
        db.add(followup)

        # Update lead
        lead.next_followup_at = scheduled_at
        lead.lead_status = LeadStatusEnum.FOLLOW_UP.value
        lead.updated_by = created_by_user_id
        
        db.commit()
        db.refresh(followup)

        # Record Timeline Event
        LeadActivityService.log_activity(
            db=db,
            lead_id=lead.id,
            activity_type=ActivityTypeEnum.FOLLOWUP_SCHEDULED,
            title=f"Follow-up Scheduled ({followup.type})",
            description=f"Scheduled for {scheduled_at.strftime('%d %b %Y, %I:%M %p')}. Notes: {notes or 'None'}",
            performed_by_user_id=created_by_user_id,
            metadata={"followup_id": followup.id, "scheduled_at": scheduled_at.isoformat()}
        )

        logger.info(f"Scheduled follow-up id={followup.id} for lead={lead.id} at {scheduled_at.isoformat()}.")
        return followup

    @classmethod
    def complete_followup(
        cls,
        db: Session,
        followup_id: str,
        user_id: str,
        completion_notes: str
    ) -> FollowUp:
        """Marks follow-up complete with mandatory completion notes."""
        stmt = select(FollowUp).where(FollowUp.id == followup_id)
        followup = db.scalars(stmt).first()
        if not followup:
            raise NotFoundError("FollowUp", followup_id)

        followup.status = FollowUpStatusEnum.COMPLETED.value
        followup.completed_at = datetime.now(timezone.utc)
        followup.completion_notes = completion_notes.strip()

        # Check if there are other pending follow-ups for lead; if not, clear lead.next_followup_at
        lead = db.get(Lead, followup.lead_id)
        if lead and lead.next_followup_at == followup.scheduled_at:
            # Find next upcoming follow-up if any
            next_stmt = select(FollowUp).where(
                FollowUp.lead_id == lead.id,
                FollowUp.status == FollowUpStatusEnum.SCHEDULED.value,
                FollowUp.id != followup.id
            ).order_by(FollowUp.scheduled_at.asc())
            next_f = db.scalars(next_stmt).first()
            lead.next_followup_at = next_f.scheduled_at if next_f else None

        db.commit()
        db.refresh(followup)

        # Record timeline event
        if lead:
            LeadActivityService.log_activity(
                db=db,
                lead_id=lead.id,
                activity_type=ActivityTypeEnum.FOLLOWUP_COMPLETED,
                title="Follow-up Completed",
                description=f"Outcome: {completion_notes}",
                performed_by_user_id=user_id,
                metadata={"followup_id": followup.id}
            )

        logger.info(f"Completed follow-up id={followup_id} by user={user_id}.")
        return followup

    @classmethod
    def reschedule_followup(
        cls,
        db: Session,
        followup_id: str,
        user_id: str,
        new_scheduled_at: datetime,
        reason: str
    ) -> FollowUp:
        """Marks old follow-up Rescheduled and creates fresh FollowUp instance."""
        stmt = select(FollowUp).where(FollowUp.id == followup_id)
        old_followup = db.scalars(stmt).first()
        if not old_followup:
            raise NotFoundError("FollowUp", followup_id)

        old_followup.status = FollowUpStatusEnum.RESCHEDULED.value
        old_followup.completion_notes = f"Rescheduled: {reason}"

        lead = db.get(Lead, old_followup.lead_id)
        if not lead:
            raise NotFoundError("Lead", old_followup.lead_id)

        new_followup = cls.schedule_followup(
            db=db,
            lead=lead,
            executive_id=old_followup.executive_id,
            scheduled_at=new_scheduled_at,
            followup_type=FollowUpTypeEnum(old_followup.type),
            priority=old_followup.priority,
            notes=f"Rescheduled from previous follow-up. Reason: {reason}",
            reminder_offset_minutes=old_followup.reminder_offset_minutes,
            created_by_user_id=user_id
        )
        return new_followup

    @classmethod
    def evaluate_reminders_and_overdue(cls, db: Session) -> Dict[str, int]:
        """
        Background scheduler worker evaluating:
        1. Due reminders (sends alert and sets reminder_processed=True)
        2. Overdue follow-ups
        """
        now = datetime.now(timezone.utc)
        reminders_triggered = 0
        overdue_marked = 0

        # 1. Process due reminders
        stmt = select(FollowUp).where(
            FollowUp.status == FollowUpStatusEnum.SCHEDULED.value,
            FollowUp.reminder_processed == False
        )
        followups = db.scalars(stmt).all()
        for f in followups:
            # Handle timezone awareness
            sched = f.scheduled_at
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
            
            reminder_threshold = sched - timedelta(minutes=f.reminder_offset_minutes)
            if now >= reminder_threshold:
                f.reminder_processed = True
                reminders_triggered += 1
                logger.info(f"[REMINDER ALERT] Follow-up due for lead={f.lead_id} executive={f.executive_id} at {f.scheduled_at.isoformat()}.")

        # 2. Mark overdue
        for f in followups:
            sched = f.scheduled_at
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
            if now > sched:
                f.status = FollowUpStatusEnum.DUE.value
                overdue_marked += 1

        db.commit()
        return {"reminders_triggered": reminders_triggered, "overdue_marked": overdue_marked}
