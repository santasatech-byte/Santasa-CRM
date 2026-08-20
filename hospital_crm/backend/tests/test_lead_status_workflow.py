"""
Module 8: Lead Status Workflow & State Machine Test Suite
"""
from datetime import datetime, timedelta, timezone
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum


@pytest.fixture
def exec_user(db_session):
    user = User(
        email="exec.status@santasa.com",
        full_name="Status Executive",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}, user


def test_followup_status_requires_next_followup_date(client, exec_user):
    """Test transition to 'Follow-up' without next_followup_at is rejected with 422."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Followup Test Patient",
        "primary_phone": "9876500331"
    }).json()

    # Attempt Follow-up without date -> 422
    resp = client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Follow-up"
    })
    assert resp.status_code == 422
    assert "required" in resp.json()["error"]["message"].lower()

    # Provide date -> 200 Success
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    success_resp = client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Follow-up",
        "next_followup_at": future_time,
        "reason": "Callback requested tomorrow"
    })
    assert success_resp.status_code == 200
    assert success_resp.json()["lead_status"] == "Follow-up"


def test_lost_to_competition_requires_competitor_and_reason(client, exec_user):
    """Test 'Lost to Competition' requires competitor name and reason."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Competition Test Patient",
        "primary_phone": "9876500332"
    }).json()

    # Attempt without competitor info -> 422
    fail_resp = client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Lost to Competition"
    })
    assert fail_resp.status_code == 422

    # Provide competitor name and reason -> 200
    success_resp = client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Lost to Competition",
        "competitor_name": "Apex Fertility Clinic",
        "reason": "Offered package discount closer to patient location."
    })
    assert success_resp.status_code == 200
    assert success_resp.json()["lead_status"] == "Lost to Competition"


def test_status_progression_and_audit_history(client, exec_user):
    """Test multi-step status lifecycle and retrieve immutable history log."""
    headers, user = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Progression Test Patient",
        "primary_phone": "9876500333"
    }).json()

    # 1. New -> Contacted
    client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Contacted",
        "reason": "First outbound call answered"
    })

    # 2. Contacted -> Appointment Booked
    client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Appointment Booked",
        "reason": "Consultation scheduled with Dr. Soumya"
    })

    # 3. Appointment Booked -> Converted
    client.post(f"/api/v1/leads/{lead['id']}/status", headers=headers, json={
        "new_status": "Converted",
        "reason": "Patient initiated IVF treatment cycle"
    })

    # Query Status History
    hist_resp = client.get(f"/api/v1/leads/{lead['id']}/status-history", headers=headers)
    assert hist_resp.status_code == 200
    histories = hist_resp.json()
    assert len(histories) == 3
    assert histories[0]["new_status"] == "Converted"
    assert histories[0]["old_status"] == "Appointment Booked"
    assert histories[1]["new_status"] == "Appointment Booked"
    assert histories[2]["new_status"] == "Contacted"
    assert histories[0]["changed_by"] == user.id
