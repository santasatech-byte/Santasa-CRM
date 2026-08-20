"""
Module 21 & 22: Reports, Analytics & Revenue Metrics Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum, LeadSourceEnum
from app.modules.appointments.models import Conversion


@pytest.fixture
def manager_user(db_session):
    u = User(
        email="mgr.reports@santasa.com",
        full_name="Report Manager",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_MANAGER.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


@pytest.fixture
def exec_user(db_session):
    u = User(
        email="exec.reports@santasa.com",
        full_name="Report Exec",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(data={"sub": u.id, "email": u.email, "role": u.role})
    return {"Authorization": f"Bearer {token}"}, u


def test_conversion_funnel_and_revenue_summary(client, manager_user, db_session):
    """Test funnel metrics calculation and revenue summary."""
    mgr_headers, mgr = manager_user

    # Create 3 Leads: 1 New, 1 Appointment Booked, 1 Converted
    l1 = client.post("/api/v1/leads", headers=mgr_headers, json={
        "patient_name": "Funnel Lead 1",
        "primary_phone": "9876500771",
        "lead_source": "Google Ads"
    }).json()

    l2 = client.post("/api/v1/leads", headers=mgr_headers, json={
        "patient_name": "Funnel Lead 2",
        "primary_phone": "9876500772",
        "lead_source": "Google Ads"
    }).json()
    client.post(f"/api/v1/leads/{l2['id']}/status", headers=mgr_headers, json={
        "new_status": "Appointment Booked"
    })

    l3 = client.post("/api/v1/leads", headers=mgr_headers, json={
        "patient_name": "Funnel Lead 3",
        "primary_phone": "9876500773",
        "lead_source": "IVR"
    }).json()
    client.post("/api/v1/conversions", headers=mgr_headers, json={
        "lead_id": l3["id"],
        "converted_service": "IVF Package",
        "conversion_value": 150000.0
    })

    # 1. Funnel API
    f_resp = client.get("/api/v1/reports/funnel", headers=mgr_headers)
    assert f_resp.status_code == 200
    funnel = f_resp.json()
    assert funnel["total_leads"] >= 3
    assert funnel["converted"] >= 1
    assert funnel["conversion_rate_pct"] > 0

    # 2. Revenue Summary API
    rev_resp = client.get("/api/v1/reports/revenue-summary", headers=mgr_headers)
    assert rev_resp.status_code == 200
    rev = rev_resp.json()
    assert rev["total_conversions"] >= 1
    assert rev["total_revenue_inr"] >= 150000.0


def test_source_attribution_and_executive_performance(client, manager_user):
    """Test source attribution and executive scorecard."""
    mgr_headers, _ = manager_user

    # Create lead to populate source
    client.post("/api/v1/leads", headers=mgr_headers, json={
        "patient_name": "Attribution Patient",
        "primary_phone": "9876500774",
        "lead_source": "Website"
    })

    # Source Attribution
    src_resp = client.get("/api/v1/reports/source-attribution", headers=mgr_headers)
    assert src_resp.status_code == 200
    sources = src_resp.json()
    assert len(sources) >= 1

    # Executive Performance
    perf_resp = client.get("/api/v1/reports/executive-performance", headers=mgr_headers)
    assert perf_resp.status_code == 200
    perf = perf_resp.json()
    assert isinstance(perf, list)


def test_executive_cannot_view_reports(client, exec_user):
    """Test executive without report permissions is denied (403 Forbidden)."""
    exec_headers, _ = exec_user
    resp = client.get("/api/v1/reports/funnel", headers=exec_headers)
    assert resp.status_code == 403
