"""
Hospital CRM - Lead Activity Timeline Service
Records and retrieves unified chronological activity events for leads.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.modules.leads.activity_models import LeadActivity, ActivityTypeEnum
from app.modules.leads.models import Lead


class LeadActivityService:
    @staticmethod
    def log_activity(
        db: Session,
        lead_id: str,
        activity_type: ActivityTypeEnum,
        title: str,
        description: Optional[str] = None,
        performed_by_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LeadActivity:
        """Records an immutable activity item on the lead's timeline."""
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type=activity_type.value,
            title=title,
            description=description,
            activity_metadata=metadata or {},
            performed_by=performed_by_user_id,
            performed_at=datetime.now(timezone.utc)
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        logger.info(f"Timeline event recorded: [{activity.activity_type}] '{activity.title}' for lead {lead_id}.")
        return activity

    @staticmethod
    def get_timeline(
        db: Session,
        lead_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[LeadActivity]:
        """Retrieves chronological activities for a lead sorted latest first."""
        stmt = (
            select(LeadActivity)
            .where(LeadActivity.lead_id == lead_id)
            .order_by(LeadActivity.performed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return db.scalars(stmt).all()
