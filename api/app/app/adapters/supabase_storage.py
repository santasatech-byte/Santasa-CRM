"""
Hospital CRM - Supabase Storage Adapter
Handles uploading, streaming, and signed URLs for call recording audio files in Supabase Storage.
"""
import os
import shutil
import uuid
from typing import Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import logger

if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    LOCAL_MEDIA_DIR = "/tmp/recordings"
else:
    LOCAL_MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "recordings")

try:
    os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)
except Exception:
    LOCAL_MEDIA_DIR = "/tmp/recordings"
    try:
        os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)
    except Exception:
        pass


class SupabaseStorageAdapter:
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        bucket_name: Optional[str] = None
    ):
        self.supabase_url = (supabase_url or settings.SUPABASE_URL or "").rstrip("/")
        self.supabase_key = supabase_key or settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
        self.bucket_name = bucket_name or settings.SUPABASE_STORAGE_BUCKET or "call-recordings"
        self.is_configured = bool(self.supabase_url and self.supabase_key)

    async def upload_recording(
        self,
        file_bytes: bytes,
        original_filename: str,
        content_type: str = "audio/mpeg"
    ) -> Tuple[str, str]:
        """
        Uploads audio recording.
        If Supabase is configured, uploads to Supabase Storage bucket.
        Otherwise, saves to local media directory.
        Returns: (recording_url, storage_key)
        """
        file_ext = os.path.splitext(original_filename)[1] or ".mp3"
        storage_filename = f"rec_{uuid.uuid4().hex[:16]}{file_ext}"

        if self.is_configured:
            # Upload to Supabase Storage REST API
            upload_endpoint = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{storage_filename}"
            headers = {
                "Authorization": f"Bearer {self.supabase_key}",
                "apikey": self.supabase_key,
                "Content-Type": content_type
            }

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(upload_endpoint, content=file_bytes, headers=headers)
                    if resp.status_code in [200, 201]:
                        public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{storage_filename}"
                        logger.info(f"Successfully uploaded recording to Supabase Storage: {public_url}")
                        return public_url, storage_filename
                    else:
                        logger.warning(f"Supabase upload returned HTTP {resp.status_code}: {resp.text}. Falling back to local storage.")
            except Exception as e:
                logger.error(f"Failed to upload to Supabase: {str(e)}. Falling back to local storage.", exc_info=True)

        # Fallback / Local Storage
        local_path = os.path.join(LOCAL_MEDIA_DIR, storage_filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        local_url = f"/api/v1/telephony/mobile-sync/recordings/{storage_filename}"
        logger.info(f"Saved recording to local storage: {local_url}")
        return local_url, storage_filename
