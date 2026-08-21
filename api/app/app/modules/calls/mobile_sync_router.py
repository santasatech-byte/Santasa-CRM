"""
Hospital CRM - Direct Mobile Phone Call & Recording Sync Router
Handles direct mobile ingestion of calls and audio files without third-party cloud telephony.
"""
from datetime import datetime, timezone
import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, HTTPException
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
    phone_number: Optional[str] = Form(None),
    direction: Optional[str] = Form("Incoming"),
    duration_seconds: Optional[int] = Form(0),
    call_timestamp: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    recording_file: Optional[UploadFile] = File(None),
    # Also support Query parameters for GET or simple webhooks
    phone: Optional[str] = None,
    caller: Optional[str] = None,
    number: Optional[str] = None,
    duration: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Universal mobile sync endpoint:
    Accepts GET, POST (Form-data, URL-encoded, or Query params) from MacroDroid, Automate, or Tasker.
    """
    raw_phone = phone_number or phone or caller or number or ""
    if not raw_phone:
        return {
            "status": "ready",
            "message": "Santasa IVF Mobile Sync Ingestion Gateway is Active & Online. Send phone_number & duration_seconds to log calls."
        }

    dur_sec = duration_seconds if duration_seconds is not None else (duration or 0)
    normalized_phone = telephony_adapter.normalize_phone_number(raw_phone)
    if not normalized_phone or len(normalized_phone) < 8:
        normalized_phone = raw_phone.replace("+", "").replace(" ", "")

    # 1. Match or Create Lead
    lead_stmt = select(Lead).where(
        Lead.normalized_phone == normalized_phone,
        Lead.is_archived == False
    ).order_by(Lead.created_at.desc())
    lead = db.scalars(lead_stmt).first()

    if not lead:
        lead = Lead(
            patient_name=f"Mobile Inquiry {phone_number[-4:]}",
            primary_phone=phone_number,
            normalized_phone=normalized_phone,
            city="Hassan",
            lead_source=LeadSourceEnum.INCOMING_CALL.value if "in" in direction.lower() else LeadSourceEnum.MANUAL.value,
            department="Fertility & IVF",
            lead_status=LeadStatusEnum.NEW.value,
            priority=LeadPriorityEnum.HIGH.value,
            notes=f"Auto-created from Mobile Phone Sync ({direction})"
        )
        db.add(lead)
        db.flush()
        logger.info(f"Auto-created new lead id={lead.id} from mobile sync.")

    # 2. Save Recording File (Supabase Storage or Local)
    recording_url = None
    rec_status = RecordingStatusEnum.UNAVAILABLE.value
    saved_filename = None

    if recording_file and recording_file.filename:
        file_bytes = await recording_file.read()
        if len(file_bytes) > 0:
            recording_url, saved_filename = await storage_adapter.upload_recording(
                file_bytes=file_bytes,
                original_filename=recording_file.filename,
                content_type=recording_file.content_type or "audio/mpeg"
            )
            rec_status = RecordingStatusEnum.AVAILABLE.value

    # 3. Create Call Entity
    external_call_id = f"mob_{uuid.uuid4().hex[:12]}"
    dir_enum = CallDirectionEnum.INCOMING.value if "in" in direction.lower() else CallDirectionEnum.OUTGOING.value
    
    call = Call(
        external_call_id=external_call_id,
        lead_id=lead.id,
        phone_number=phone_number,
        normalized_phone=normalized_phone,
        direction=dir_enum,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration=duration_seconds,
        status=CallStatusEnum.COMPLETED.value,
        recording_status=rec_status,
        recording_url=recording_url,
        recording_duration=duration_seconds,
        provider="mobile_sim_direct",
        provider_metadata={"notes": notes, "filename": saved_filename}
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
        description=f"Direct SIM call on mobile phone. Duration: {duration_seconds}s. {'Recording attached.' if recording_url else 'No recording.'}",
        metadata={
            "call_id": call.id,
            "duration": duration_seconds,
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
        "recording_url": recording_url,
        "duration_seconds": duration_seconds
    }


@router.get("/recordings/{filename}", status_code=status.HTTP_200_OK)
async def stream_call_recording(filename: str):
    """Streams the local call recording audio file (.mp3/.m4a/.wav) for playback in CRM."""
    # Prevent path traversal attacks
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
