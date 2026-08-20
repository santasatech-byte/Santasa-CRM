"""
Module 6: Lead Management Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum, LeadPriorityEnum


@pytest.fixture
def exec_a(db_session):
    user = User(
        email="exec.a.leads@santasa.com",
        full_name="Executive A",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def exec_b(db_session):
    user = User(
        email="exec.b.leads@santasa.com",
        full_name="Executive B",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin.leads@santasa.com",
        full_name="Hospital Admin",
        hashed_password=hash_password("AdminPass123!"),
        role=UserRole.HOSPITAL_ADMIN.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}, user


def test_create_lead_with_phone_normalization(client, exec_a):
    """Test creating a lead auto-normalizes phone numbers to standard E.164 (+91)."""
    headers, user = exec_a
    resp = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Sayeda Tabasuma",
        "primary_phone": "76765 50644",
        "email": "sayeda.t@example.com",
        "city": "Hassan",
        "lead_source": "IVR",
        "department": "Fertility & IVF",
        "service_interested": "IVF 1st Cycle Package",
        "priority": "High",
        "notes": "Patient enquired about clinic timings and doctor appointment."
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["patient_name"] == "Sayeda Tabasuma"
    assert data["primary_phone"] == "76765 50644"
    assert data["normalized_phone"] == "+917676550644"
    assert data["lead_status"] == "New"
    assert data["assigned_executive_id"] == user.id


def test_fast_lead_search(client, exec_a):
    """Test fast search resolves matches by name, raw phone, and normalized phone."""
    headers, _ = exec_a
    # Create test lead
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Pooja Ramesh",
        "primary_phone": "98451 22345",
        "city": "Mysore",
        "lead_source": "Google Ads"
    }).json()

    # Search by partial name
    s1 = client.post("/api/v1/leads/search", headers=headers, json={"query": "Pooja"}).json()
    assert len(s1) >= 1
    assert s1[0]["patient_name"] == "Pooja Ramesh"

    # Search by raw phone
    s2 = client.post("/api/v1/leads/search", headers=headers, json={"query": "98451"}).json()
    assert len(s2) >= 1

    # Search by normalized E.164 phone
    s3 = client.post("/api/v1/leads/search", headers=headers, json={"query": "+919845122345"}).json()
    assert len(s3) >= 1


def test_executive_role_lead_isolation(client, exec_a, exec_b):
    """Test Executive A cannot access Executive B's private lead."""
    headers_a, _ = exec_a
    headers_b, _ = exec_b

    # Exec A creates Lead A
    lead_a = client.post("/api/v1/leads", headers=headers_a, json={
        "patient_name": "Confidential Patient A",
        "primary_phone": "9123456780"
    }).json()

    # Exec B attempts to view Lead A -> 403 Forbidden
    resp = client.get(f"/api/v1/leads/{lead_a['id']}", headers=headers_b)
    assert resp.status_code == 403


def test_lead_update_and_status_progression(client, exec_a):
    """Test updating lead status and notes."""
    headers, _ = exec_a
    lead = client.post("/api/v1/leads", headers=headers, json={
        "patient_name": "Deepika Gowda",
        "primary_phone": "9448088712"
    }).json()

    # Update to Follow-up
    update_resp = client.patch(f"/api/v1/leads/{lead['id']}", headers=headers, json={
        "lead_status": "Follow-up",
        "priority": "High",
        "notes": "Spoke to patient; callback scheduled for tomorrow."
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["lead_status"] == "Follow-up"
    assert update_resp.json()["priority"] == "High"
