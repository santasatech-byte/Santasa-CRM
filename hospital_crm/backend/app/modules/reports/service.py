"""
Hospital CRM - Analytics, Reporting & Conversion Funnel Engine
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, select, case
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum, LeadSourceEnum
from app.modules.calls.models import Call, CallDirectionEnum
from app.modules.followups.models import FollowUp, FollowUpStatusEnum
from app.modules.appointments.models import Appointment, AppointmentStatusEnum, Conversion


class ReportingService:
    @staticmethod
    def get_conversion_funnel(
        db: Session,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes the complete CRM conversion funnel:
        Leads -> Contacted -> Follow-ups -> Appointments -> Consultations -> Converted
        """
        base_lead = select(func.count(Lead.id)).where(Lead.is_archived == False)
        if branch_id:
            base_lead = base_lead.where(Lead.branch_id == branch_id)

        total_leads = db.scalar(base_lead) or 0
        
        # Stages
        contacted = db.scalar(base_lead.where(Lead.lead_status.in_([
            LeadStatusEnum.CONTACTED.value,
            LeadStatusEnum.FOLLOW_UP.value,
            LeadStatusEnum.APPOINTMENT_BOOKED.value,
            LeadStatusEnum.CONSULTATION_DONE.value,
            LeadStatusEnum.CONVERTED.value
        ]))) or 0

        followups = db.scalar(base_lead.where(Lead.lead_status.in_([
            LeadStatusEnum.FOLLOW_UP.value,
            LeadStatusEnum.APPOINTMENT_BOOKED.value,
            LeadStatusEnum.CONSULTATION_DONE.value,
            LeadStatusEnum.CONVERTED.value
        ]))) or 0

        appts = db.scalar(base_lead.where(Lead.lead_status.in_([
            LeadStatusEnum.APPOINTMENT_BOOKED.value,
            LeadStatusEnum.CONSULTATION_DONE.value,
            LeadStatusEnum.CONVERTED.value
        ]))) or 0

        consultations = db.scalar(base_lead.where(Lead.lead_status.in_([
            LeadStatusEnum.CONSULTATION_DONE.value,
            LeadStatusEnum.CONVERTED.value
        ]))) or 0

        converted = db.scalar(base_lead.where(Lead.lead_status == LeadStatusEnum.CONVERTED.value)) or 0

        return {
            "total_leads": total_leads,
            "contacted": contacted,
            "followups_scheduled": followups,
            "appointments_booked": appts,
            "consultations_done": consultations,
            "converted": converted,
            "conversion_rate_pct": round((converted / total_leads * 100), 2) if total_leads > 0 else 0.0,
            "lead_to_appt_pct": round((appts / total_leads * 100), 2) if total_leads > 0 else 0.0
        }

    @staticmethod
    def get_executive_performance(
        db: Session,
        branch_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Computes executive performance scorecard: calls count, talk time, completed follow-ups, and conversions.
        """
        exec_stmt = select(User).where(
            User.role == UserRole.CRM_EXECUTIVE.value,
            User.is_active == True
        )
        if branch_id:
            exec_stmt = exec_stmt.where(User.branch_id == branch_id)

        executives = db.scalars(exec_stmt).all()
        performance_list = []

        for e in executives:
            # 1. Total Leads Assigned
            leads_assigned = db.scalar(
                select(func.count(Lead.id)).where(Lead.assigned_executive_id == e.id)
            ) or 0

            # 2. Total Calls & Talk Time
            call_stats = db.execute(
                select(
                    func.count(Call.id).label("total_calls"),
                    func.coalesce(func.sum(Call.duration), 0).label("total_duration")
                ).where(Call.executive_id == e.id)
            ).first()
            total_calls = call_stats.total_calls if call_stats else 0
            total_duration = call_stats.total_duration if call_stats else 0

            # 3. Follow-ups
            f_stats = db.execute(
                select(
                    func.count(FollowUp.id).label("total_f"),
                    func.sum(case((FollowUp.status == FollowUpStatusEnum.COMPLETED.value, 1), else_=0)).label("comp_f")
                ).where(FollowUp.executive_id == e.id)
            ).first()
            total_f = f_stats.total_f if f_stats and f_stats.total_f else 0
            comp_f = f_stats.comp_f if f_stats and f_stats.comp_f else 0

            # 4. Conversions & Revenue
            conv_stats = db.execute(
                select(
                    func.count(Conversion.id).label("total_conv"),
                    func.coalesce(func.sum(Conversion.conversion_value), 0.0).label("total_revenue")
                ).where(Conversion.converted_by == e.id)
            ).first()
            total_conv = conv_stats.total_conv if conv_stats else 0
            total_revenue = conv_stats.total_revenue if conv_stats else 0.0

            performance_list.append({
                "executive_id": e.id,
                "executive_name": e.full_name,
                "email": e.email,
                "leads_assigned": leads_assigned,
                "total_calls": total_calls,
                "total_talk_time_minutes": round(total_duration / 60, 1),
                "followups_scheduled": total_f,
                "followups_completed": comp_f,
                "adherence_rate_pct": round((comp_f / total_f * 100), 1) if total_f > 0 else 100.0,
                "conversions_count": total_conv,
                "total_revenue_inr": total_revenue
            })

        return performance_list

    @staticmethod
    def get_source_attribution(db: Session) -> List[Dict[str, Any]]:
        """Computes conversion performance grouped by lead source."""
        results = db.execute(
            select(
                Lead.lead_source,
                func.count(Lead.id).label("total_leads"),
                func.sum(case((Lead.lead_status == LeadStatusEnum.CONVERTED.value, 1), else_=0)).label("conversions")
            )
            .where(Lead.is_archived == False)
            .group_by(Lead.lead_source)
        ).all()

        attribution = []
        for r in results:
            total = r.total_leads or 0
            conv = r.conversions or 0
            attribution.append({
                "source": r.lead_source,
                "total_leads": total,
                "conversions": conv,
                "conversion_rate_pct": round((conv / total * 100), 2) if total > 0 else 0.0
            })
        return attribution

    @staticmethod
    def get_revenue_summary(db: Session) -> Dict[str, Any]:
        """Calculates total CRM revenue, total conversion volume, and average package value."""
        stats = db.execute(
            select(
                func.count(Conversion.id).label("total_conversions"),
                func.coalesce(func.sum(Conversion.conversion_value), 0.0).label("total_revenue"),
                func.coalesce(func.avg(Conversion.conversion_value), 0.0).label("avg_ticket_size")
            )
        ).first()

        return {
            "total_conversions": stats.total_conversions if stats else 0,
            "total_revenue_inr": stats.total_revenue if stats else 0.0,
            "avg_package_value_inr": round(stats.avg_ticket_size, 2) if stats else 0.0
        }
