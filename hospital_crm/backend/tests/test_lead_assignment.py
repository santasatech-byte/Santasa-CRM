"""
Module 7: Lead Assignment & Round-Robin Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus
from app.modules.leads.models import Lead


@pytest.fixture
def manager_user(db_session):
    mgr = User(
        email="manager.assign@santasa.com",
        full_name="CRM Manager",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_MANAGER.value,
        is_active=True
    )
    db_session.add(mgr)
    db_session.commit()
    db_session.refresh(mgr)
    token = create_access_token(data={"sub": mgr.id, "email": mgr.email, "role": mgr.role})
    return {"Authorization": f"Bearer {token}"}, mgr


@pytest.fixture
def executive_pool(db_session):
    """Creates two online executives and one offline executive."""
    execs = []
    for i, name in enumerate(["Alex Online", "Ben Online", "Charlie Offline"]):
        u = User(
            email=f"exec.{i}@santasa.com",
            full_name=name,
            hashed_password=hash_password("ValidPass123!"),
            role=UserRole.CRM_EXECUTIVE.value,
            is_active=True
        )
        db_session.add(u)
        db_session.flush()

        is_online = "Online" in name
        prof = ExecutiveProfile(
            user_id=u.id,
            employee_id=f"EMP-RR-{i}",
            status=ExecutiveStatus.ONLINE.value if is_online else ExecutiveStatus.OFFLINE.value,
            is_available_for_lead_assignment=is_online
        )
        db_session.add(prof)
        execs.append(u)

    db_session.commit()
    return execs


def test_round_robin_distribution(client, manager_user, executive_pool):
    """Test round robin cycles between online executives and skips offline executives."""
    mgr_headers, _ = manager_user
    alex, ben, charlie = executive_pool

    # Create 4 leads
    lead_ids = []
    for i in range(4):
        resp = client.post("/api/v1/leads", headers=mgr_headers, json={
            "patient_name": f"Patient RR {i}",
            "primary_phone": f"987654320{i}"
        })
        lead_ids.append(resp.json()["id"])

    # Auto-assign leads
    assigned_owners = []
    for lid in lead_ids:
        auto_resp = client.post(f"/api/v1/leads/{lid}/auto-assign", headers=mgr_headers, json={
            "reason": "Test Round Robin"
        })
        assert auto_resp.status_code == 200
        assigned_owners.append(auto_resp.json()["assigned_executive_id"])

    # Expect alternating distribution between Alex and Ben; Charlie (offline) never assigned
    assert charlie.id not in assigned_owners
    assert assigned_owners[0] in [alex.id, ben.id]
    assert assigned_owners[1] in [alex.id, ben.id]
    assert assigned_owners[0] != assigned_owners[1]  # Alternating round-robin


def test_manual_reassignment_with_history(client, manager_user, executive_pool):
    """Test manual reassignment updates owner and writes immutable history log."""
    mgr_headers, mgr = manager_user
    alex, ben, _ = executive_pool

    # Create Lead assigned to Alex
    lead = client.post("/api/v1/leads", headers=mgr_headers, json={
        "patient_name": "Reassignment Patient",
        "primary_phone": "9988776655",
        "assigned_executive_id": alex.id
    }).json()

    # Reassign to Ben
    reassign_resp = client.post(f"/api/v1/leads/{lead['id']}/assign", headers=mgr_headers, json={
        "new_executive_id": ben.id,
        "reason": "Workload rebalancing by manager"
    })
    assert reassign_resp.status_code == 200
    assert reassign_resp.json()["assigned_executive_id"] == ben.id

    # Retrieve Assignment History
    hist_resp = client.get(f"/api/v1/leads/{lead['id']}/assignment-history", headers=mgr_headers)
    assert hist_resp.status_code == 200
    histories = hist_resp.json()
    assert len(histories) >= 1
    latest = histories[0]
    assert latest["previous_executive_id"] == alex.id
    assert latest["new_executive_id"] == ben.id
    assert latest["assigned_by"] == mgr.id
    assert latest["strategy"] == "Manual"
    assert "rebalancing" in latest["reason"]


def test_executive_cannot_reassign_leads(client, executive_pool):
    """Test CRM Executive cannot reassign leads (403 Forbidden)."""
    alex, ben, _ = executive_pool
    alex_token = create_access_token(data={"sub": alex.id, "email": alex.email, "role": "CRM Executive"})
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    lead = client.post("/api/v1/leads", headers=alex_headers, json={
        "patient_name": "Test Exec Lead",
        "primary_phone": "9876500112"
    }).json()

    resp = client.post(f"/api/v1/leads/{lead['id']}/assign", headers=alex_headers, json={
        "new_executive_id": ben.id
    })
    assert resp.status_code == 403
