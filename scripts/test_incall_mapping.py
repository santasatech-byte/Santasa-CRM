import os
import sys
import uuid

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")
for p in [backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.modules.leads.models import Lead
from app.modules.calls.models import Call

client = TestClient(app)

def test_full_incall_lifecycle():
    print("\n--- [TEST] Starting Live In-Call Lead & Zero-Overlap Recording Sync Test ---")
    
    test_phone = f"+9198{uuid.uuid4().hex[:8]}"
    print(f"1. Executive dials or receives call on Samsung phone: {test_phone}")
    
    # 1. MacroDroid triggers Call Start
    res_start = client.get(f"/api/v1/telephony/mobile-sync/call-start?phone={test_phone}&direction=outgoing")
    assert res_start.status_code == 200, f"Call start failed: {res_start.text}"
    start_data = res_start.json()
    print(f"   -> Call Start response: {start_data}")
    lead_id = start_data["lead_id"]
    assert start_data["active"] is True
    assert start_data["is_new"] is True
    
    # 2. CRM UI polls active-call
    res_active = client.get("/api/v1/telephony/mobile-sync/active-call")
    assert res_active.status_code == 200
    active_data = res_active.json()
    print(f"   -> Active Call poll response: {active_data}")
    assert active_data["active"] is True
    assert active_data["call"]["lead_id"] == lead_id
    
    # 3. Executive clicks banner and fills patient information during the call
    print(f"3. Executive updates lead details live in CRM during call...")
    db = SessionLocal()
    try:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        lead.patient_name = "Smt. Renuka Devi"
        lead.patient_type = "New Patient"
        lead.patient_id_mrn = "SNT-2026-TEST"
        lead.treatment = "IVF Package with ICSI"
        lead.notes = "Patient called inquiring about 2nd cycle. Advised doctor consultation Friday."
        db.commit()
        db.refresh(lead)
        print(f"   -> Lead updated in DB: Name={lead.patient_name}, MRN={lead.patient_id_mrn}, Treatment={lead.treatment}")
    finally:
        db.close()
        
    # 4. Active call poller in UI reflects new patient name
    res_active_2 = client.get("/api/v1/telephony/mobile-sync/active-call")
    active_data_2 = res_active_2.json()
    print(f"   -> Active Call poll after edit: {active_data_2['call']['patient_name']}")
    assert active_data_2["call"]["patient_name"] == "Smt. Renuka Devi"
    
    # 5. Call ends after 118 seconds. MacroDroid sends call-log with audio recording
    print("5. Call ends. MacroDroid uploads call-log with duration and audio file...")
    dummy_audio = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00isomiso2" + b"\x00" * 600
    files = {
        "file": ("Call_Renuka_Devi_2026.m4a", dummy_audio, "audio/mp4")
    }
    data = {
        "phone_number": test_phone,
        "duration_seconds": "118",
        "direction": "Outgoing",
        "notes": "Completed direct call on SIM 1"
    }
    res_log = client.post("/api/v1/telephony/mobile-sync/call-log", data=data, files=files)
    assert res_log.status_code == 201, f"Call log failed: {res_log.text}"
    log_data = res_log.json()
    print(f"   -> Call Log response: {log_data}")
    
    # Verify exact mapping without overlap or data mixing
    assert log_data["lead_id"] == lead_id, "Mapped to wrong lead!"
    assert log_data["patient_name"] == "Smt. Renuka Devi", "Executive-entered patient name was overwritten!"
    assert log_data["duration_seconds"] == 118
    assert log_data["recording_url"] is not None
    print(f"   -> Call Recording URL: {log_data['recording_url']}")
    
    # 6. Verify Active Call is now cleared
    res_active_3 = client.get("/api/v1/telephony/mobile-sync/active-call")
    assert res_active_3.json()["active"] is False, "Active call was not cleared after call end!"
    print("   -> Active call successfully cleared from live banner.")
    
    # 7. Check database: Verify only 1 single lead exists (NO DUPLICATE)
    db = SessionLocal()
    try:
        lead_in_db = db.get(Lead, lead_id)
        assert lead_in_db is not None, "Lead was not found in database!"
        assert lead_in_db.patient_name == "Smt. Renuka Devi", "Patient name was modified after call end!"

        # Ensure NO duplicate lead was created for this phone
        all_matching = [l for l in db.query(Lead).filter(Lead.is_archived == False).all() if test_phone[-10:] in (l.primary_phone or "")]
        assert len(all_matching) == 1, f"Expected exactly 1 lead, found {len(all_matching)}: {[l.patient_name for l in all_matching]}"

        call_records = db.query(Call).filter(Call.lead_id == lead_id).all()
        assert len(call_records) == 1, f"Expected 1 call record, got {len(call_records)}"
        assert call_records[0].duration == 118
        assert call_records[0].recording_url is not None
        print(f"   -> DB Verification PASSED: 1 Lead ({lead_in_db.patient_name}), 1 Call Record ({call_records[0].duration}s), Zero Duplicates!")
    finally:
        db.close()
        
    print("\n[SUCCESS] ALL TESTS PASSED: Zero Overlap, In-Call Live Lead Creation & Audio Recording Mapping Working Perfectly!\n")

if __name__ == "__main__":
    test_full_incall_lifecycle()
