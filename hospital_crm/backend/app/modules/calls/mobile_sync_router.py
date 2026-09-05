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
from fastapi.responses import FileResponse, RedirectResponse
import re
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
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

# In-memory registry for active in-progress calls: { core_10: { lead_id, phone, direction, started_at, ... } }
ACTIVE_CALLS: dict[str, dict] = {}


def clean_phone_10(phone: str) -> str:
    """Extracts the last 10 significant digits from any phone string."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    return digits[-10:] if len(digits) >= 10 else digits


def find_lead_by_phone(db: Session, raw_phone: str) -> Optional[Lead]:
    """
    Bulletproof phone matcher:
    Matches by 10-digit suffix across primary_phone, normalized_phone, registered_number, secondary_phone.
    Avoids duplicate leads, data mixing, and missing call recordings.
    """
    core_10 = clean_phone_10(raw_phone)
    if not core_10 or len(core_10) < 7:
        return None

    # 1. SQL ILIKE query across all contact columns
    stmt = select(Lead).where(
        or_(
            Lead.normalized_phone.ilike(f"%{core_10}%"),
            Lead.primary_phone.ilike(f"%{core_10}%"),
            Lead.registered_number.ilike(f"%{core_10}%"),
            Lead.secondary_phone.ilike(f"%{core_10}%")
        ),
        Lead.is_archived == False
    ).order_by(Lead.updated_at.desc(), Lead.created_at.desc())
    lead = db.scalars(stmt).first()
    if lead:
        return lead

    # 2. Fallback: check recent active leads in Python (handles spaced numbers like "+91 96323 58709")
    recent_leads = db.scalars(
        select(Lead).where(Lead.is_archived == False).order_by(Lead.updated_at.desc()).limit(200)
    ).all()
    for l in recent_leads:
        for p in [l.primary_phone, l.normalized_phone, l.secondary_phone, l.registered_number]:
            if p and clean_phone_10(p) == core_10:
                return l

    return None


@router.api_route("/call-start", methods=["GET", "POST"])
async def notify_call_start(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Real-Time Call Start Notification endpoint:
    Invoked when phone begins dialing (Outgoing) or rings/answers (Incoming).
    Allows executive to create / edit lead details live in CRM during the call.
    """
    raw_data = dict(request.query_params)
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                raw_data.update(body)
        elif "form" in content_type:
            form = await request.form()
            for k, v in form.items():
                if isinstance(v, str):
                    raw_data[k] = v
    except Exception:
        pass

    raw_phone = str(
        raw_data.get("phone_number")
        or raw_data.get("phone")
        or raw_data.get("caller")
        or raw_data.get("number")
        or raw_data.get("from_number")
        or raw_data.get("to_number")
        or ""
    ).strip()

    if "[" in raw_phone or "call_num" in raw_phone:
        raw_phone = ""

    if raw_phone:
        clean_d = re.sub(r"\D", "", raw_phone)
        if len(clean_d) == 10:
            raw_phone = f"+91{clean_d}"
        elif len(clean_d) == 12 and clean_d.startswith("91"):
            raw_phone = f"+{clean_d}"

    if not raw_phone:
        return {"status": "ready", "message": "Santasa Call Start Gateway ready. Pass ?phone=... to register active call."}

    raw_dir = str(raw_data.get("direction") or raw_data.get("call_type") or "Incoming").strip()
    raw_dir_lower = raw_dir.lower()
    if raw_dir_lower.startswith("out") or "dial" in raw_dir_lower or "made" in raw_dir_lower:
        dir_enum = CallDirectionEnum.OUTGOING.value
    else:
        dir_enum = CallDirectionEnum.INCOMING.value

    core_10 = clean_phone_10(raw_phone)
    normalized_phone = telephony_adapter.normalize_phone_number(raw_phone)
    if not normalized_phone or len(normalized_phone) < 8:
        normalized_phone = raw_phone.replace("+", "").replace(" ", "").replace("-", "")

    # Match existing lead or create placeholder
    lead = find_lead_by_phone(db, raw_phone)
    is_new = False
    suffix = raw_phone[-4:] if len(raw_phone) >= 4 else raw_phone

    if not lead:
        is_new = True
        lead = Lead(
            patient_name=f"In-Call Lead {suffix}",
            primary_phone=raw_phone,
            normalized_phone=normalized_phone,
            city="Hassan",
            lead_source=LeadSourceEnum.INCOMING_CALL.value if dir_enum == CallDirectionEnum.INCOMING.value else LeadSourceEnum.MANUAL.value,
            department="Fertility & IVF",
            lead_status=LeadStatusEnum.NEW.value,
            priority=LeadPriorityEnum.HIGH.value,
            notes=f"Active call in progress ({dir_enum})"
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        logger.info(f"Auto-created in-call lead id={lead.id} ({raw_phone})")

    # Record in active calls
    call_info = {
        "lead_id": lead.id,
        "phone_number": raw_phone,
        "normalized_phone": lead.normalized_phone or normalized_phone,
        "patient_name": lead.patient_name,
        "direction": dir_enum,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "is_new": is_new,
        "treatment": lead.treatment or "",
        "status": lead.lead_status or "New"
    }
    ACTIVE_CALLS[core_10] = call_info

    return {
        "success": True,
        "active": True,
        "lead_id": lead.id,
        "patient_name": lead.patient_name,
        "phone_number": raw_phone,
        "direction": dir_enum,
        "is_new": is_new
    }


@router.get("/active-call")
async def get_active_call(db: Session = Depends(get_db)):
    """
    Returns the current in-progress call for real-time CRM executive notification.
    Auto-expires calls older than 15 minutes.
    """
    now = datetime.now(timezone.utc)
    expired_keys = []
    latest_call = None

    for k, call_data in list(ACTIVE_CALLS.items()):
        try:
            started = datetime.fromisoformat(call_data["started_at"])
            age_sec = (now - started).total_seconds()
            if age_sec > 900:  # 15 minutes expiry
                expired_keys.append(k)
            else:
                call_data["duration_elapsed"] = int(age_sec)
                # Keep latest lead info refreshed from DB if updated by executive
                lead = db.get(Lead, call_data["lead_id"])
                if lead:
                    call_data["patient_name"] = lead.patient_name
                    call_data["treatment"] = lead.treatment or ""
                    call_data["status"] = lead.lead_status or "New"
                    call_data["phone_number"] = lead.primary_phone or call_data["phone_number"]
                latest_call = call_data
        except Exception:
            expired_keys.append(k)

    for k in expired_keys:
        ACTIVE_CALLS.pop(k, None)

    if latest_call:
        return {"active": True, "call": latest_call}
    return {"active": False, "call": None}


@router.post("/active-call/dismiss")
async def dismiss_active_call():
    """Dismisses active call from real-time alert banner."""
    ACTIVE_CALLS.clear()
    return {"success": True, "message": "Active call alert cleared."}



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

    if raw_phone:
        clean_d = re.sub(r"\D", "", raw_phone)
        if len(clean_d) == 10:
            raw_phone = f"+91{clean_d}"
        elif len(clean_d) == 12 and clean_d.startswith("91"):
            raw_phone = f"+{clean_d}"

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

    # Extract direction (Correctly check prefix to avoid 'in' substring inside 'outgoing')
    raw_dir = str(raw_data.get("direction") or raw_data.get("call_type") or "Incoming").strip()
    if "[" in raw_dir or "call_type" in raw_dir:
        raw_dir = "Incoming"
    raw_dir_lower = raw_dir.lower()
    if raw_dir_lower.startswith("out") or "dial" in raw_dir_lower or "made" in raw_dir_lower:
        dir_enum = CallDirectionEnum.OUTGOING.value
    else:
        dir_enum = CallDirectionEnum.INCOMING.value

    # Extract notes
    raw_notes = raw_data.get("notes") or "Auto-synced via Mobile Phone"

    # Normalize phone
    normalized_phone = telephony_adapter.normalize_phone_number(raw_phone)
    if not normalized_phone or len(normalized_phone) < 8:
        normalized_phone = raw_phone.replace("+", "").replace(" ", "").replace("-", "")

    # Retrieve and clear active call session if present
    core_10 = clean_phone_10(raw_phone)
    active_info = ACTIVE_CALLS.pop(core_10, None)

    # 1. Match or Create Lead in Database (Zero Overlap / Zero Mixing)
    lead = None
    if active_info and active_info.get("lead_id"):
        lead = db.get(Lead, active_info["lead_id"])

    if not lead:
        lead = find_lead_by_phone(db, raw_phone)

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
    else:
        # If the executive already entered real patient details during active call, PRESERVE THEM!
        if lead.patient_name.startswith("In-Call Lead") and not raw_data.get("patient_name"):
            lead.patient_name = f"Mobile Inquiry {suffix}"
        logger.info(f"Matched existing lead id={lead.id} ({lead.patient_name}) for call sync.")

    # 2. Save Recording File (Supabase Storage or Local)
    recording_url = None
    rec_status = RecordingStatusEnum.UNAVAILABLE.value
    saved_filename = None

    if file_bytes and len(file_bytes) > 256:
        try:
            recording_url, saved_filename = await storage_adapter.upload_recording(
                file_bytes=file_bytes,
                original_filename=file_name or f"rec_{suffix}_{uuid.uuid4().hex[:6]}.m4a",
                content_type="audio/mp4" if (file_name and file_name.endswith(".m4a")) else "audio/mpeg"
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
                        content_type="audio/mp4" if ext == ".m4a" else "audio/mpeg"
                    )
                    rec_status = RecordingStatusEnum.AVAILABLE.value
        except Exception as e:
            logger.warning(f"Binary body recording upload note: {e}")

    # Set streaming recording URL through our local router
    if saved_filename:
        recording_url = f"/api/v1/telephony/mobile-sync/recordings/{saved_filename}"

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


@router.get("/recordings/{filename}")
async def stream_call_recording(filename: str):
    """Streams the call recording audio file (.mp3/.m4a/.wav) for playback in CRM."""
    clean_filename = os.path.basename(filename)
    filepath = os.path.join(MEDIA_DIR, clean_filename)
    if os.path.exists(filepath):
        media_type = "audio/mp4" if filename.endswith(".m4a") else "audio/mpeg"
        return FileResponse(filepath, media_type=media_type)

    # Redirect to Supabase Public Storage CDN
    supabase_public_url = f"{storage_adapter.supabase_url}/storage/v1/object/public/{storage_adapter.bucket_name}/{clean_filename}"
    return RedirectResponse(url=supabase_public_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
