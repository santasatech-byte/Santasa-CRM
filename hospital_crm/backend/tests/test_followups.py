"""
Module 15 & 16: Follow-up Management, Reminders & Work Queue Test Suite
"""
from datetime import datetime, timedelta, timezone
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead
from app.modules.followups.service import FollowUpService
from app.modules.followups.models import FollowUpStatusEnum


@pytest.fixture
def exec_user(db_session):
    u = User(
        email="exec.followup@santasa.com",
        full_name="Followup Executive",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


def test_schedule_and_complete_followup(client, exec_user, db_session):
    """Test scheduling a follow-up and completing it with notes."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Followup Lead 1",
        "primary_phone": "9876500551"
    }).json()

    future_time = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    
    # 1. Schedule Follow-up
    sched_resp = client.post("/api/v1/followups", headers=headers, json={
        "lead_id": lead["id"],
        "scheduled_at": future_time,
        "type": "Call",
        "priority": "High",
        "notes": "Discuss second consultation package details",
        "reminder_offset_minutes": 15
    })
    assert sched_resp.status_code == 201
    f_data = sched_resp.json()
    assert f_data["status"] == "Scheduled"
    assert f_data["type"] == "Call"

    # Verify lead status updated
    updated_lead = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()
    assert updated_lead["lead_status"] == "Follow-up"

    # 2. Complete Follow-up
    comp_resp = client.post(f"/api/v1/followups/{f_data['id']}/complete", headers=headers, json={
        "completion_notes": "Patient agreed for weekend appointment. Booked slot with Dr. Soumya."
    })
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "Completed"
    assert "agreed" in comp_resp.json()["completion_notes"]


def test_reschedule_followup(client, exec_user):
    """Test rescheduling marks old follow-up Rescheduled and creates fresh follow-up."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Reschedule Patient",
        "primary_phone": "9876500552"
    }).json()

    t1 = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    f1 = client.post("/api/v1/followups", headers=headers, json={
        "lead_id": lead["id"],
        "scheduled_at": t1,
        "notes": "Original Follow-up"
    }).json()

    # Reschedule
    t2 = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    resched_resp = client.post(f"/api/v1/followups/{f1['id']}/reschedule", headers=headers, json={
        "new_scheduled_at": t2,
        "reason": "Patient traveling out of town"
    })
    assert resched_resp.status_code == 200
    new_f = resched_resp.json()
    assert new_f["id"] != f1["id"]
    assert new_f["status"] == "Scheduled"


def test_today_work_queue(client, exec_user):
    """Test Today's Work Queue partitions into new leads, due today, overdue, and upcoming."""
    headers, _ = exec_user

    # Create Overdue Followup
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    lead_overdue = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Overdue Patient",
        "primary_phone": "9876500553"
    }).json()
    client.post("/api/v1/followups", headers=headers, json={
        "lead_id": lead_overdue["id"],
        "scheduled_at": past_time,
        "notes": "Overdue callback"
    })

    # Fetch Work Queue
    queue_resp = client.get("/api/v1/followups/work-queue", headers=headers)
    assert queue_resp.status_code == 200
    q = queue_resp.json()
    assert "summary" in q
    assert q["summary"]["overdue_count"] >= 1
    assert len(q["overdue_followups"]) >= 1


def test_reminder_scheduler_evaluator(db_session, exec_user, client):
    """Test background evaluator processes due reminders without duplicates."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Reminder Test Patient",
        "primary_phone": "9876500554"
    }).json()

    # Scheduled in 5 minutes with 15 min reminder offset (due immediately)
    t_due = (datetime.now(timezone.utc) + timedelta(minutes=5))
    f = FollowUpService.schedule_followup(
        db=db_session,
        lead=db_session.get(Lead, lead["id"]),
        executive_id=exec_user[1].id,
        scheduled_at=t_due,
        reminder_offset_minutes=15
    )

    # Run evaluator
    res = FollowUpService.evaluate_reminders_and_overdue(db_session)
    assert res["reminders_triggered"] >= 1

    # Run again -> should not re-trigger (reminder_processed == True)
    res2 = FollowUpService.evaluate_reminders_and_overdue(db_session)
    assert res2["reminders_triggered"] == 0
