import urllib.request
import json

SUPABASE_URL = 'https://vdwpxcdpzhreonutitrc.supabase.co'
ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkd3B4Y2RwemhyZW9udXRpdHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY4MzkzMTEsImV4cCI6MjEwMjQxNTMxMX0.tAuwylQZ29cXXopfWiQlqFTaD1jE7kK6EV4un66jCJE'

def get_token(email, pwd='Executive@2026!'):
    req = urllib.request.Request(
        f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
        data=json.dumps({'email': email, 'password': pwd}).encode('utf-8'),
        headers={'apikey': ANON_KEY, 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))['access_token']

def fetch_leads(token, hosp_code):
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/leads?select=*&hospital_code=eq.{hosp_code}',
        headers={
            'apikey': ANON_KEY,
            'Authorization': f'Bearer {token}'
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

tok_ssm = get_token('ssm@hospital.com')
leads_ssm = fetch_leads(tok_ssm, 'SSM')

tok_shh = get_token('executive@santasa.com')
leads_shh = fetch_leads(tok_shh, 'SHH')

tok_smh = get_token('mysore@santasa.com')
leads_smh = fetch_leads(tok_smh, 'SMH')

print(f"SSM Leads Count: {len(leads_ssm)}")
print(f"SHH Leads Count: {len(leads_shh)}")
print(f"SMH Leads Count: {len(leads_smh)}")

ids_ssm = {l['id'] for l in leads_ssm}
ids_shh = {l['id'] for l in leads_shh}
ids_smh = {l['id'] for l in leads_smh}

overlap_ssm_shh = ids_ssm.intersection(ids_shh)
overlap_ssm_smh = ids_ssm.intersection(ids_smh)
overlap_shh_smh = ids_shh.intersection(ids_smh)

print("Overlap SSM vs SHH:", len(overlap_ssm_shh))
print("Overlap SSM vs SMH:", len(overlap_ssm_smh))
print("Overlap SHH vs SMH:", len(overlap_shh_smh))

assert len(overlap_ssm_shh) == 0
assert len(overlap_ssm_smh) == 0
assert len(overlap_shh_smh) == 0

print("PASSED: Zero data overlap across all 3 hospitals verified successfully!")
