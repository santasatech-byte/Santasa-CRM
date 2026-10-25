#!/usr/bin/env python3
"""
Santasa CRM - Batch Call Recordings Uploader
Uploads multiple audio recording files (.m4a, .mp3, etc.) from any local folder
directly into Supabase Storage under the specified hospital bucket.
The Postgres database trigger automatically:
  1. Identifies the hospital code (SSM, SHH, SMH).
  2. Extracts the exact 10-digit phone number.
  3. Parses the call direction (inbound / outbound).
  4. Parses the exact call timestamp (YYMMDD_HHMMSS).
  5. Links or creates the lead and individual call record with playable audio.
"""

import os
import sys
import argparse
import mimetypes
import urllib.request
import urllib.error
import ssl

SUPABASE_URL = "https://vdwpxcdpzhreonutitrc.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkd3B4Y2RwemhyZW9udXRpdHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY4MzkzMTEsImV4cCI6MjEwMjQxNTMxMX0."
    "tAuwylQZ29cXXopfWiQlqFTaD1jE7kK6EV4un66jCJE"
)
BUCKET_NAME = "santasa-recordings"

def upload_file(file_path: str, hospital_code: str = "SSM"):
    filename = os.path.basename(file_path)
    storage_path = f"{hospital_code}/{filename}"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{urllib.parse.quote(storage_path)}"
    
    # Guess mime type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "audio/mp4"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    req = urllib.request.Request(
        upload_url,
        data=file_bytes,
        method="POST"
    )
    req.add_header("apikey", SUPABASE_ANON_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_ANON_KEY}")
    req.add_header("Content-Type", content_type)
    req.add_header("x-upsert", "true")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            if response.status in (200, 201):
                return True, f"Uploaded: {filename}"
            return False, f"HTTP {response.status}: {response.read().decode('utf-8', errors='ignore')}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if "Duplicate" in err_body or "already exists" in err_body:
            return True, f"Already exists: {filename}"
        return False, f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return False, str(e)

def upload_folder(folder_path: str, hospital_code: str = "SSM"):
    if not os.path.isdir(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return

    valid_exts = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".3gp", ".amr"}
    files = [
        f for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in valid_exts
    ]

    if not files:
        print(f"No audio recording files found in '{folder_path}'.")
        return

    print(f"Found {len(files)} audio recordings in '{folder_path}'.")
    print(f"Target Hospital: {hospital_code}")
    print(f"Target Bucket: {BUCKET_NAME}/{hospital_code}/")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for idx, fname in enumerate(files, 1):
        fpath = os.path.join(folder_path, fname)
        print(f"[{idx}/{len(files)}] Processing: {fname}...", end=" ", flush=True)
        ok, msg = upload_file(fpath, hospital_code)
        if ok:
            print("DONE")
            success_count += 1
        else:
            print(f"FAILED ({msg})")
            fail_count += 1

    print("-" * 60)
    print(f"Upload Complete! Successfully synced: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload call recordings folder to Santasa CRM Supabase")
    parser.add_argument("folder", help="Path to folder containing call recordings")
    parser.add_argument("--hospital", default="SSM", choices=["SSM", "SHH", "SMH"], help="Hospital branch code (SSM, SHH, SMH)")
    args = parser.parse_args()

    upload_folder(args.folder, args.hospital)
