import psycopg2

conn = psycopg2.connect("postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require")
cur = conn.cursor()

sql = """
CREATE OR REPLACE FUNCTION public.sync_mobile_call(
  p_phone text,
  p_hospital_code text DEFAULT 'SSM',
  p_direction text DEFAULT 'inbound',
  p_duration int DEFAULT 0,
  p_notes text DEFAULT ''
) RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_clean text;
  v_core10 text;
  v_norm text;
  v_lead_id text;
  v_lead_name text;
  v_call_id text;
  v_hosp_id text;
  v_ext_id text;
BEGIN
  v_clean := regexp_replace(p_phone, '[^0-9]', '', 'g');
  IF length(v_clean) >= 10 THEN
    v_core10 := right(v_clean, 10);
    v_norm := '+91' || v_core10;
  ELSE
    v_core10 := v_clean;
    v_norm := '+91' || v_clean;
  END IF;

  -- Map hospital id
  IF upper(p_hospital_code) = 'SHH' THEN
    v_hosp_id := 'hosp-shh-fd72cfcc';
  ELSIF upper(p_hospital_code) = 'SMH' THEN
    v_hosp_id := 'hosp-smh-42546563';
  ELSE
    v_hosp_id := 'hosp-ssm-c13526e4';
  END IF;

  -- 1. Look up existing lead
  SELECT id, patient_name INTO v_lead_id, v_lead_name
  FROM public.leads
  WHERE hospital_code = upper(p_hospital_code)
    AND (primary_phone ILIKE '%' || v_core10 || '%' OR normalized_phone ILIKE '%' || v_core10 || '%')
  LIMIT 1;

  -- 2. Create new lead if not found
  IF v_lead_id IS NULL THEN
    v_lead_id := gen_random_uuid()::text;
    v_lead_name := 'Inbound Patient (' || v_core10 || ')';
    INSERT INTO public.leads (
      id, patient_name, primary_phone, normalized_phone, hospital_code, hospital_id,
      lead_status, lead_source, treatment, notes, is_archived, created_at, updated_at
    ) VALUES (
      v_lead_id, v_lead_name, v_core10, v_norm, upper(p_hospital_code), v_hosp_id,
      'New', 'Mobile Inbound Call', 'IVF Consultation', p_notes, false, now(), now()
    );
  END IF;

  -- 3. Create Call record in calls table
  v_call_id := gen_random_uuid()::text;
  v_ext_id := 'mob-' || extract(epoch from now())::bigint || '-' || v_core10;
  INSERT INTO public.calls (
    id, external_call_id, hospital_id, lead_id, phone_number, normalized_phone,
    direction, started_at, duration, status, recording_status, provider,
    created_at, updated_at
  ) VALUES (
    v_call_id, v_ext_id, v_hosp_id, v_lead_id, v_core10, v_norm,
    lower(p_direction), now(), p_duration,
    CASE WHEN p_duration = 0 OR lower(p_direction) LIKE '%miss%' THEN 'Missed' ELSE 'Completed' END,
    'COMPLETED', 'mobile-sync',
    now(), now()
  );

  RETURN json_build_object(
    'success', true,
    'lead_id', v_lead_id,
    'patient_name', v_lead_name,
    'call_id', v_call_id,
    'external_call_id', v_ext_id,
    'hospital_code', upper(p_hospital_code)
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.sync_mobile_call(text, text, text, int, text) TO anon, authenticated, service_role;
"""

cur.execute(sql)
conn.commit()
print("Postgres sync_mobile_call RPC successfully updated with started_at!")
conn.close()
