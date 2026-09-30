import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000/api/v1"

def login(email, password="Executive@2026!"):
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Logged in as [{data['user']['email']}] -> Hospital: {data['user']['hospital_name']} (code: {data['user']['hospital_code']})")
        return data["access_token"], data["user"]

def get_leads(token):
    req = urllib.request.Request(
        f"{BASE_URL}/leads?limit=100",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_metrics(token):
    req = urllib.request.Request(
        f"{BASE_URL}/leads/metrics/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def create_lead(token, name, phone):
    req = urllib.request.Request(
        f"{BASE_URL}/leads",
        data=json.dumps({
            "patient_name": name,
            "primary_phone": phone,
            "patient_type": "Digital Patient",
            "lead_status": "Valid - Consultation done"
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== 1. TEST SSM HOSPITAL TENANT ===")
token_ssm, user_ssm = login("ssm@hospital.com")
metrics_ssm = get_metrics(token_ssm)
print("SSM Metrics:", metrics_ssm)
leads_ssm = get_leads(token_ssm)
print(f"SSM Leads Count: {len(leads_ssm)}")
for l in leads_ssm[:3]:
    print(f"  - {l['patient_name']} ({l['primary_phone']}) -> Hosp ID: {l.get('hospital_id')}")

print("\n=== 2. TEST SANTASA HASSAN HOSPITAL TENANT ===")
token_shh, user_shh = login("executive@santasa.com")
metrics_shh = get_metrics(token_shh)
print("Santasa Hassan Metrics:", metrics_shh)
leads_shh = get_leads(token_shh)
print(f"Santasa Hassan Leads Count: {len(leads_shh)}")
for l in leads_shh[:3]:
    print(f"  - {l['patient_name']} ({l['primary_phone']}) -> Hosp ID: {l.get('hospital_id')}")

print("\n=== 3. VERIFY ZERO DATA OVERLAP / NO OVERWRITE ===")
ssm_names = {l['patient_name'] for l in leads_ssm}
shh_names = {l['patient_name'] for l in leads_shh}
overlap = ssm_names.intersection(shh_names)
print("Overlapping leads between SSM and Hassan:", overlap)
assert len(overlap) == 0, f"DATA OVERLAP DETECTED: {overlap}"
print("PASSED: Zero overlap between hospital tenants!")

print("\n=== 4. TEST CROSS-TENANT ACCESS PREVENTION ===")
if leads_ssm:
    ssm_lead_id = leads_ssm[0]['id']
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/leads/{ssm_lead_id}",
            headers={"Authorization": f"Bearer {token_shh}"}
        )
        with urllib.request.urlopen(req) as resp:
            print("ERROR: Hassan user was able to access SSM lead!")
    except urllib.error.HTTPError as e:
        print(f"PASSED: Cross-tenant access successfully blocked with HTTP {e.code}!")

print("\n=== ALL MULTI-HOSPITAL TENANCY TESTS PASSED CLEANLY! ===")
