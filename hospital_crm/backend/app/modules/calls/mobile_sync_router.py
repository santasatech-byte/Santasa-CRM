"""
Hospital CRM - Direct Mobile Phone Call & Recording Sync Router
Handles direct mobile ingestion of calls and audio files without third-party cloud telephony.
"""
from datetime import datetime, timezone
import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.logging import logger
from app.adapters.telephony_base import MockTelephonyAdapter
from app.modules.calls.models import Call, CallDirectionEnum, CallStatusEnum, RecordingStatusEnum
from app.modules.leads.models import Lead, LeadStatusEnum, LeadPriorityEnum, LeadSourceEnum
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import ActivityTypeEnum
from app.adapters.supabase_storage import SupabaseStorageAdapter, LOCAL_MEDIA_DIR

router = APIRouter(prefix="/telephony/mobile-sync", tags=["Mobile Device Direct Telephony Sync"])
telephony_adapter = MockTelephonyAdapter()
storage_adapter = SupabaseStorageAdapter()
MEDIA_DIR = LOCAL_MEDIA_DIR


@router.api_route("/call-log", methods=["GET", "POST"], status_code=status.HTTP_201_CREATED)
async def sync_mobile_call_log(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Universal mobile sync endpoint:
    Accepts GET, POST (Form-data, URL-encoded, Query params, or JSON body) from MacroDroid, Automate, or Tasker.
    Zero-422 error guarantee: All fields are parsed dynamically.
    """
    # 1. Gather all inputs from query parameters
    raw_data = dict(request.query_params)
    file_bytes = None
    file_name = None
    content_type = request.headers.get("content-type", "")

    # 2. Check JSON payload if applicable
    try:
        if "application/json" in content_type:
            json_body = await request.json()
            if isinstance(json_body, dict):
                raw_data.update(json_body)
    except Exception:
        pass

    # 3. Check Form / Multipart body if applicable
    try:
        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            for k, v in form_data.items():
                if hasattr(v, "file") and hasattr(v, "filename") and v.filename:
                    # UploadFile object
                    try:
                        file_bytes = await v.read()
                        file_name = v.filename
                    except Exception:
                        pass
                elif isinstance(v, str):
                    raw_data[k] = v
    except Exception:
        pass

    # Extract phone number
    raw_phone = str(
        raw_data.get("phone_number")
        or raw_data.get("phone")
        or raw_data.get("caller")
        or raw_data.get("number")
        or raw_data.get("from_number")
        or ""
    ).strip()

    # Clean phone if placeholder passed
    if "[" in raw_phone or "call_num" in raw_phone:
        raw_phone = ""

    if not raw_phone:
        return {
            "status": "ready",
            "message": "Santasa IVF Mobile Sync Ingestion Gateway is Active & Online. Send phone_number & duration_seconds to log calls."
        }

    # Extract duration
    raw_dur = str(raw_data.get("duration_seconds") or raw_data.get("duration") or "0").strip()
    try:
        if "[" in raw_dur or "call_dur" in raw_dur:
            dur_sec = 0
        else:
            dur_sec = int(float(raw_dur))
    except Exception:
        dur_sec = 0

    # Extract direction
    raw_dir = str(raw_data.get("direction") or raw_data.get("call_type") or "Incoming").strip()
    if "[" in raw_dir or "call_type" in raw_dir:
        raw_dir = "Incoming"
    dir_enum = CallDirectionEnum.INCOMING.value if "in" in raw_dir.lower() else CallDirectionEnum.OUTGOING.value

    # Extract notes
    raw_notes = raw_data.get("notes") or "Auto-synced via Mobile Phone"

    # Normalize phone
    normalized_phone = telephony_adapter.normalize_phone_number(raw_phone)
    if not normalized_phone or len(normalized_phone) < 8:
        normalized_phone = raw_phone.replace("+", "").replace(" ", "").replace("-", "")

    # 1. Match or Create Lead in Database
    lead_stmt = select(Lead).where(
        Lead.normalized_phone == normalized_phone,
        Lead.is_archived == False
    ).order_by(Lead.created_at.desc())
    lead = db.scalars(lead_stmt).first()

    suffix = raw_phone[-4:] if len(raw_phone) >= 4 else raw_phone
    if not lead:
        lead = Lead(
            patient_name=f"Mobile Inquiry {suffix}",
            primary_phone=raw_phone,
            normalized_phone=normalized_phone,
            city="Hassan",
            lead_source=LeadSourceEnum.INCOMING_CALL.value if dir_enum == CallDirectionEnum.INCOMING.value else LeadSourceEnum.MANUAL.value,
            department="Fertility & IVF",
            lead_status=LeadStatusEnum.NEW.value,
            priority=LeadPriorityEnum.HIGH.value,
            notes=f"Auto-created from Mobile Phone Sync ({dir_enum})"
        )
        db.add(lead)
        db.flush()
        logger.info(f"Auto-created new lead id={lead.id} from mobile sync.")

    # 2. Save Recording File (Supabase Storage or Local)
    recording_url = None
    rec_status = RecordingStatusEnum.UNAVAILABLE.value
    saved_filename = None

    if file_bytes and len(file_bytes) > 256:
        try:
            recording_url, saved_filename = await storage_adapter.upload_recording(
                file_bytes=file_bytes,
                original_filename=file_name or f"rec_{suffix}_{uuid.uuid4().hex[:6]}.mp3",
                content_type="audio/mpeg"
            )
            rec_status = RecordingStatusEnum.AVAILABLE.value
        except Exception as e:
            logger.warning(f"Recording upload error: {e}")
    else:
        # Check if raw binary audio file was sent in raw body
        try:
            if not ("application/x-www-form-urlencoded" in content_type or "application/json" in content_type):
                raw_bytes = await request.body()
                if len(raw_bytes) > 512:
                    ext = ".m4a" if ("mp4" in content_type or "m4a" in content_type) else ".mp3"
                    recording_url, saved_filename = await storage_adapter.upload_recording(
                        file_bytes=raw_bytes,
                        original_filename=f"rec_{suffix}_{uuid.uuid4().hex[:6]}{ext}",
                        content_type="audio/mpeg"
                    )
                    rec_status = RecordingStatusEnum.AVAILABLE.value
        except Exception as e:
            logger.warning(f"Binary body recording upload note: {e}")

    # 3. Create Call Entity
    external_call_id = f"mob_{uuid.uuid4().hex[:12]}"
    call = Call(
        external_call_id=external_call_id,
        lead_id=lead.id,
        phone_number=raw_phone,
        normalized_phone=normalized_phone,
        direction=dir_enum,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration=dur_sec,
        status=CallStatusEnum.COMPLETED.value,
        recording_status=rec_status,
        recording_url=recording_url,
        recording_duration=dur_sec,
        provider="mobile_sim_direct",
        provider_metadata={"notes": raw_notes, "filename": saved_filename}
    )
    db.add(call)

    # 4. Update Lead last contacted timestamp
    lead.last_contacted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(call)

    # 5. Append Activity Timeline Event
    LeadActivityService.log_activity(
        db=db,
        lead_id=lead.id,
        activity_type=ActivityTypeEnum.CALL_LOGGED,
        title=f"Direct Mobile Call ({dir_enum})",
        description=f"Direct SIM call on mobile phone. Duration: {dur_sec}s. {'Recording attached.' if recording_url else 'No recording.'}",
        metadata={
            "call_id": call.id,
            "duration": dur_sec,
            "recording_url": recording_url,
            "recording_status": rec_status,
            "direction": dir_enum
        }
    )

    return {
        "success": True,
        "call_id": call.id,
        "lead_id": lead.id,
        "patient_name": lead.patient_name,
        "phone_number": raw_phone,
        "direction": dir_enum,
        "duration_seconds": dur_sec,
        "recording_url": recording_url
    }


@router.get("/recordings/{filename}", status_code=status.HTTP_200_OK)
async def stream_call_recording(filename: str):
    """Streams the local call recording audio file (.mp3/.m4a/.wav) for playback in CRM."""
    clean_filename = os.path.basename(filename)
    filepath = os.path.join(MEDIA_DIR, clean_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Recording audio file not found.")

    media_type = "audio/mpeg"
    if filename.endswith(".m4a"):
        media_type = "audio/mp4"
    elif filename.endswith(".wav"):
        media_type = "audio/wav"

    return FileResponse(filepath, media_type=media_type)
