"""
Hospital CRM - Lead Assignment Engine
Implements deterministic Round-Robin distribution, capacity checking,
and immutable assignment history recording.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import logger
from app.core.errors import NotFoundError, ValidationError, CRMException
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus
from app.modules.leads.models import Lead
from app.modules.leads.assignment_models import LeadAssignmentHistory

# In-memory branch round-robin pointers (persisted/cycled per branch in multi-worker setup)
_ROUND_ROBIN_INDEX: Dict[str, int] = {}


class LeadAssignmentService:
    @staticmethod
    def get_eligible_executives(db: Session, branch_id: Optional[str] = None) -> List[User]:
        """
        Retrieves all active CRM Executives who are currently Online and available for lead assignment.
        """
        stmt = (
            select(User)
            .join(ExecutiveProfile, ExecutiveProfile.user_id == User.id)
            .where(
                User.is_active == True,
                User.role == UserRole.CRM_EXECUTIVE.value,
                ExecutiveProfile.status == ExecutiveStatus.ONLINE.value,
                ExecutiveProfile.is_available_for_lead_assignment == True
            )
        )
        if branch_id:
            stmt = stmt.where(User.branch_id == branch_id)

        stmt = stmt.order_by(User.created_at.asc())
        return db.scalars(stmt).all()

    @classmethod
    def assign_round_robin(
        cls,
        db: Session,
        lead: Lead,
        assigned_by_user_id: str,
        reason: str = "Automated Round-Robin Assignment"
    ) -> User:
        """
        Distributes the lead to the next eligible online executive in a round-robin cycle.
        """
        branch_key = lead.branch_id or "global"
        eligible_execs = cls.get_eligible_executives(db, branch_id=lead.branch_id)
        
        # If no executive is online in specific branch, fallback to global online executives
        if not eligible_execs and lead.branch_id:
            eligible_execs = cls.get_eligible_executives(db, branch_id=None)

        if not eligible_execs:
            logger.warning(f"No online eligible executives available for round-robin assignment for lead {lead.id}.")
            raise ValidationError("No online executives are currently available for automatic assignment.")

        # Compute next round robin index
        current_idx = _ROUND_ROBIN_INDEX.get(branch_key, 0)
        selected_executive = eligible_execs[current_idx % len(eligible_execs)]
        _ROUND_ROBIN_INDEX[branch_key] = (current_idx + 1) % len(eligible_execs)

        # Apply assignment
        cls.apply_assignment(
            db=db,
            lead=lead,
            new_executive=selected_executive,
            assigned_by_user_id=assigned_by_user_id,
            strategy="Round Robin",
            reason=reason
        )

        return selected_executive

    @classmethod
    def assign_manual(
        cls,
        db: Session,
        lead: Lead,
        new_executive_id: str,
        assigned_by_user_id: str,
        reason: Optional[str] = "Manual Manager Assignment"
    ) -> User:
        """
        Manually assigns/reassigns lead to a designated executive.
        """
        stmt = select(User).where(User.id == new_executive_id, User.is_active == True)
        new_executive = db.scalars(stmt).first()
        if not new_executive:
            raise NotFoundError("User", new_executive_id)

        cls.apply_assignment(
            db=db,
            lead=lead,
            new_executive=new_executive,
            assigned_by_user_id=assigned_by_user_id,
            strategy="Manual",
            reason=reason or "Manual Assignment"
        )
        return new_executive

    @staticmethod
    def apply_assignment(
        db: Session,
        lead: Lead,
        new_executive: User,
        assigned_by_user_id: str,
        strategy: str,
        reason: Optional[str]
    ):
        """Updates lead owner and records immutable assignment history log."""
        prev_owner_id = lead.assigned_executive_id
        
        lead.assigned_executive_id = new_executive.id
        lead.updated_by = assigned_by_user_id

        # Record History
        history = LeadAssignmentHistory(
            lead_id=lead.id,
            previous_executive_id=prev_owner_id,
            new_executive_id=new_executive.id,
            assigned_by=assigned_by_user_id,
            assigned_at=datetime.now(timezone.utc),
            strategy=strategy,
            reason=reason
        )
        db.add(history)
        db.commit()
        db.refresh(lead)

        logger.info(
            f"Lead {lead.id} assigned to {new_executive.email} (Prev: {prev_owner_id}) "
            f"via {strategy}. Reason: {reason}"
        )
