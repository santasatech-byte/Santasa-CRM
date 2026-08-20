"""
Module 9: Activity Timeline Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.activity_models import ActivityTypeEnum
from app.modules.leads.activity_service import LeadActivityService


@pytest.fixture
def exec_user(db_session):
    user = User(
        email="exec.timeline@santasa.com",
        full_name="Timeline Executive",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}, user


def test_add_note_and_query_timeline(client, exec_user, db_session):
    """Test adding executive notes and querying chronological timeline entries."""
    headers, user = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Timeline Test Patient",
        "primary_phone": "9876500441"
    }).json()

    # 1. Add Note 1
    n1_resp = client.post(f"/api/v1/leads/{lead['id']}/notes", headers=headers, json={
        "note": "First consultation enquiry received via phone."
    })
    assert n1_resp.status_code == 201
    assert n1_resp.json()["activity_type"] == "note_added"

    # 2. Add Note 2
    n2_resp = client.post(f"/api/v1/leads/{lead['id']}/notes", headers=headers, json={
        "note": "Patient requested WhatsApp brochure on IVF packages."
    })
    assert n2_resp.status_code == 201

    # 3. Query Timeline
    t_resp = client.get(f"/api/v1/leads/{lead['id']}/timeline", headers=headers)
    assert t_resp.status_code == 200
    timeline = t_resp.json()
    assert len(timeline) >= 2
    assert timeline[0]["description"] == "Patient requested WhatsApp brochure on IVF packages."
    assert timeline[1]["description"] == "First consultation enquiry received via phone."


def test_timeline_pagination(client, exec_user, db_session):
    """Test pagination over timeline items."""
    headers, _ = exec_user
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Pagination Patient",
        "primary_phone": "9876500442"
    }).json()

    for i in range(5):
        client.post(f"/api/v1/leads/{lead['id']}/notes", headers=headers, json={
            "note": f"Timeline note number {i}"
        })

    # Page 1 (limit 2)
    p1 = client.get(f"/api/v1/leads/{lead['id']}/timeline?limit=2&offset=0", headers=headers).json()
    assert len(p1) == 2
    assert "number 4" in p1[0]["description"]

    # Page 2 (limit 2, offset 2)
    p2 = client.get(f"/api/v1/leads/{lead['id']}/timeline?limit=2&offset=2", headers=headers).json()
    assert len(p2) == 2
    assert "number 2" in p2[0]["description"]
