import psycopg2

conn = psycopg2.connect("postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require")
cur = conn.cursor()

sql = """
CREATE OR REPLACE FUNCTION public.handle_recording_uploaded()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_filename text;
  v_path_parts text[];
  v_hospital_code text;
  v_core10 text;
  v_rec_url text;
  v_call_id text;
  v_lead_id text;
  v_lead_name text;
  v_hosp_id text;
BEGIN
  IF NEW.bucket_id <> 'santasa-recordings' THEN
    RETURN NEW;
  END IF;

  v_filename := NEW.name;
  v_path_parts := string_to_array(v_filename, '/');
  
  -- Determine hospital code from folder path (e.g. 'SSM', 'SHH', 'SMH')
  IF array_length(v_path_parts, 1) > 1 THEN
    v_hospital_code := upper(v_path_parts[1]);
  ELSE
    v_hospital_code := 'SSM';
  END IF;

  -- Extract 10-digit phone number right before date underscore e.g. Call to +919876543210_261025...
  v_core10 := substring(v_filename from '([0-9]{10})_[0-9]{6}');
  IF v_core10 IS NULL THEN
    v_core10 := substring(regexp_replace(v_filename, '[^0-9]', '', 'g') from '([0-9]{10})');
  END IF;

  IF v_core10 IS NULL OR length(v_core10) < 10 THEN
    RETURN NEW;
  END IF;

  -- Construct public audio streaming URL
  v_rec_url := 'https://vdwpxcdpzhreonutitrc.supabase.co/storage/v1/object/public/santasa-recordings/' || v_filename;

  -- Map hospital id
  IF v_hospital_code = 'SHH' THEN
    v_hosp_id := 'hosp-shh-fd72cfcc';
  ELSIF v_hospital_code = 'SMH' THEN
    v_hosp_id := 'hosp-smh-42546563';
  ELSE
    v_hosp_id := 'hosp-ssm-c13526e4';
  END IF;

  -- 1. Find or create lead
  SELECT id, patient_name INTO v_lead_id, v_lead_name
  FROM public.leads
  WHERE hospital_code = v_hospital_code
    AND (primary_phone ILIKE '%' || v_core10 || '%' OR normalized_phone ILIKE '%' || v_core10 || '%')
  LIMIT 1;

  IF v_lead_id IS NULL THEN
    v_lead_id := gen_random_uuid()::text;
    v_lead_name := 'Inbound Patient (' || v_core10 || ')';
    INSERT INTO public.leads (
      id, patient_name, primary_phone, normalized_phone, hospital_code, hospital_id,
      lead_status, lead_source, treatment, notes, is_archived, created_at, updated_at
    ) VALUES (
      v_lead_id, v_lead_name, v_core10, '+91' || v_core10, v_hospital_code, v_hosp_id,
      'New', 'Call Recording Sync', 'IVF Consultation', 'Auto-created from phone audio upload', false, now(), now()
    );
  END IF;

  -- 2. Link recording URL to recent call or create one
  UPDATE public.calls
  SET recording_url = v_rec_url,
      recording_status = 'COMPLETED',
      updated_at = now()
  WHERE id = (
    SELECT id FROM public.calls
    WHERE phone_number ILIKE '%' || v_core10 || '%'
      AND hospital_id = v_hosp_id
    ORDER BY created_at DESC
    LIMIT 1
  );

  IF NOT FOUND THEN
    v_call_id := gen_random_uuid()::text;
    INSERT INTO public.calls (
      id, external_call_id, hospital_id, lead_id, phone_number, normalized_phone,
      direction, started_at, duration, status, recording_status, recording_url, provider,
      created_at, updated_at
    ) VALUES (
      v_call_id, 'rec-' || extract(epoch from now())::bigint || '-' || v_core10,
      v_hosp_id, v_lead_id, v_core10, '+91' || v_core10,
      'inbound', now(), 30, 'Completed', 'COMPLETED', v_rec_url, 'foldersync',
      now(), now()
    );
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_recording_uploaded ON storage.objects;
CREATE TRIGGER trg_recording_uploaded
AFTER INSERT ON storage.objects
FOR EACH ROW
EXECUTE FUNCTION public.handle_recording_uploaded();
"""

cur.execute(sql)
conn.commit()
print("Postgres handle_recording_uploaded trigger successfully updated!")
conn.close()
