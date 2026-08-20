"""
Hospital CRM - Direct Mobile Phone Sync Test Suite
"""
import io
import pytest
from app.modules.leads.models import Lead
from app.modules.calls.models import Call


def test_mobile_call_sync_with_recording_upload(client, db_session):
    """
    Test direct mobile sync uploads call data and audio file,
    links to patient lead, and enables in-browser streaming.
    """
    # Create fake audio buffer
    audio_content = b"ID3\x03\x00\x00\x00\x00\x00#MOCK_RECORDING_MP3_DATA#"
    fake_file = io.BytesIO(audio_content)

    resp = client.post(
        "/api/v1/telephony/mobile-sync/call-log",
        data={
            "phone_number": "76765 50644",
            "direction": "Incoming",
            "duration_seconds": "195",
            "notes": "Patient enquired about fertility package"
        },
        files={
            "recording_file": ("patient_call_rec.mp3", fake_file, "audio/mpeg")
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["duration_seconds"] == 195
    assert data["recording_url"] is not None
    assert "/api/v1/telephony/mobile-sync/recordings/" in data["recording_url"]

    # Verify Lead was created & normalized
    lead = db_session.get(Lead, data["lead_id"])
    assert lead is not None
    assert lead.normalized_phone == "+917676550644"

    # Verify Audio Stream Playback
    rec_url = data["recording_url"]
    stream_resp = client.get(rec_url)
    assert stream_resp.status_code == 200
    assert stream_resp.content == audio_content
