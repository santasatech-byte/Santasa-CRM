import sqlite3
import uuid

conn = sqlite3.connect('hospital_crm/backend/hospital_crm.db')
cur = conn.cursor()

def check_and_add_column(table, col_name, col_type):
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if col_name not in cols:
        print(f"Adding {col_name} to {table}...")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        conn.commit()
    else:
        print(f"{col_name} already in {table}")

# Check tables
print("Tables in DB:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])

# Ensure hospitals table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS hospitals (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) DEFAULT 'Karnataka',
    country VARCHAR(100) DEFAULT 'India',
    phone VARCHAR(50),
    email VARCHAR(255),
    website VARCHAR(255),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# Ensure branches table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS branches (
    id VARCHAR(36) PRIMARY KEY,
    hospital_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) DEFAULT 'Karnataka',
    country VARCHAR(100) DEFAULT 'India',
    phone VARCHAR(50),
    ivr_number VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# Add hospital_id to users, leads, calls
check_and_add_column("users", "hospital_id", "VARCHAR(36)")
check_and_add_column("leads", "hospital_id", "VARCHAR(36)")
check_and_add_column("calls", "hospital_id", "VARCHAR(36)")

# Add reference CRM fields to leads
check_and_add_column("leads", "patient_type", "VARCHAR(50)")
check_and_add_column("leads", "patient_id_mrn", "VARCHAR(100)")
check_and_add_column("leads", "registered_number", "VARCHAR(50)")
check_and_add_column("leads", "treatment", "VARCHAR(255)")
check_and_add_column("leads", "message", "TEXT")
check_and_add_column("leads", "consultation_date", "TIMESTAMP")
check_and_add_column("leads", "surgery_date", "TIMESTAMP")
check_and_add_column("leads", "surgery_requirement", "VARCHAR(255)")
check_and_add_column("leads", "surgery_details", "TEXT")
check_and_add_column("leads", "destination_number", "VARCHAR(50)")

# Check existing hospitals
hospitals = cur.execute("SELECT id, name, code FROM hospitals").fetchall()
print("Current hospitals:", hospitals)

# Seed hospitals if missing
hosp_map = {h[2]: h[0] for h in hospitals}
if "SSM" not in hosp_map:
    ssm_id = "hosp-ssm-" + uuid.uuid4().hex[:8]
    cur.execute("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (?, ?, ?, ?, 'Karnataka', 'India', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (ssm_id, "SSM Hospital", "SSM", "Bangalore"))
    hosp_map["SSM"] = ssm_id
    print("Created SSM Hospital:", ssm_id)

if "SHH" not in hosp_map:
    shh_id = "hosp-shh-" + uuid.uuid4().hex[:8]
    cur.execute("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (?, ?, ?, ?, 'Karnataka', 'India', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (shh_id, "Santasa Hassan Hospital", "SHH", "Hassan"))
    hosp_map["SHH"] = shh_id
    print("Created Santasa Hassan Hospital:", shh_id)

if "SMH" not in hosp_map:
    smh_id = "hosp-smh-" + uuid.uuid4().hex[:8]
    cur.execute("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (?, ?, ?, ?, 'Karnataka', 'India', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (smh_id, "Santasa Mysore Hospital", "SMH", "Mysore"))
    hosp_map["SMH"] = smh_id
    print("Created Santasa Mysore Hospital:", smh_id)

conn.commit()

# Seed or update users
from app.core.security import hash_password

exec_hash = hash_password("Executive@2026!")
admin_hash = hash_password("Admin@2026!")

# User 1: ssm@hospital.com -> SSM Hospital
user_ssm = cur.execute("SELECT id, email FROM users WHERE email = 'ssm@hospital.com'").fetchone()
if not user_ssm:
    u_id = "user-" + uuid.uuid4().hex[:8]
    cur.execute("""
        INSERT INTO users (id, email, full_name, role, hashed_password, is_active, hospital_id, created_at, updated_at)
        VALUES (?, 'ssm@hospital.com', 'SSM Hospital Executive', 'CRM Executive', ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (u_id, exec_hash, hosp_map["SSM"]))
    print("Created user ssm@hospital.com")
else:
    cur.execute("UPDATE users SET hospital_id = ?, full_name = 'SSM Hospital Executive' WHERE email = 'ssm@hospital.com'", (hosp_map["SSM"],))

# User 2: executive@santasa.com -> Santasa Hassan
user_exec = cur.execute("SELECT id, email FROM users WHERE email = 'executive@santasa.com'").fetchone()
if not user_exec:
    u_id = "user-" + uuid.uuid4().hex[:8]
    cur.execute("""
        INSERT INTO users (id, email, full_name, role, hashed_password, is_active, hospital_id, created_at, updated_at)
        VALUES (?, 'executive@santasa.com', 'Santasa Hassan Executive', 'CRM Executive', ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (u_id, exec_hash, hosp_map["SHH"]))
    print("Created user executive@santasa.com")
else:
    cur.execute("UPDATE users SET hospital_id = ?, full_name = 'Santasa Hassan Executive' WHERE email = 'executive@santasa.com'", (hosp_map["SHH"],))

# User 3: mysore@santasa.com -> Santasa Mysore
user_mysore = cur.execute("SELECT id, email FROM users WHERE email = 'mysore@santasa.com'").fetchone()
if not user_mysore:
    u_id = "user-" + uuid.uuid4().hex[:8]
    cur.execute("""
        INSERT INTO users (id, email, full_name, role, hashed_password, is_active, hospital_id, created_at, updated_at)
        VALUES (?, 'mysore@santasa.com', 'Santasa Mysore Executive', 'CRM Executive', ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (u_id, exec_hash, hosp_map["SMH"]))
    print("Created user mysore@santasa.com")
else:
    cur.execute("UPDATE users SET hospital_id = ? WHERE email = 'mysore@santasa.com'", (hosp_map["SMH"],))

# User 4: admin@santasa.com -> Super Admin
user_admin = cur.execute("SELECT id, email FROM users WHERE email = 'admin@santasa.com'").fetchone()
if not user_admin:
    u_id = "user-" + uuid.uuid4().hex[:8]
    cur.execute("""
        INSERT INTO users (id, email, full_name, role, hashed_password, is_active, hospital_id, created_at, updated_at)
        VALUES (?, 'admin@santasa.com', 'Super Administrator', 'Super Admin', ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (u_id, admin_hash, hosp_map["SHH"]))
    print("Created user admin@santasa.com")

conn.commit()

# Ensure all existing leads without hospital_id are set to Santasa Hassan by default
cur.execute("UPDATE leads SET hospital_id = ? WHERE hospital_id IS NULL", (hosp_map["SHH"],))

# Check if SSM has leads, if not seed sample leads matching the screenshots!
ssm_leads = cur.execute("SELECT count(*) FROM leads WHERE hospital_id = ?", (hosp_map["SSM"],)).fetchone()[0]
print(f"SSM Hospital lead count: {ssm_leads}")

if ssm_leads == 0:
    # Seed SSM Hospital leads matching the screenshot!
    # Screenshot shows:
    # Nending Asha, 7005940191, Valid - Followup
    # Somachar / Puttasomachar, 9086168095, Valid - Consultation done, Digital Patient
    # NARETGR131607NEYRT HYT, 8733439841
    # JustinKoymn, 6622865748
    # Humaira Fatima, 7760260139, Valid - Followup, Digital Patient
    # Manglal, 9448847520, Valid - Followup, Digital Patient
    # RobertGilze, 5575332797, Invalid - Wrong number
    # Kokila S, 8197828515, Valid - Followup, Digital Patient
    # Raghavendra R N, 9481622333, Valid - Consultation done, Digital Patient
    # Subramaniam, 9353960631, Valid - Followup, Digital Patient
    sample_ssm_leads = [
        ("Nending Asha", "7005940191", "Valid - Followup", "Digital Patient", "21-09-2026", "21-09-2026"),
        ("Somachar", "9086168095", "Valid - Consultation done", "Digital Patient", "20-09-2026", "21-09-2026"),
        ("NARETGR131607/NEYRTHYT", "8733439841", "New", "Enquiry", "20-09-2026", "20-09-2026"),
        ("JustinKoymn", "6622865748", "New", "Enquiry", "20-09-2026", "20-09-2026"),
        ("Humaira Fatima", "7760260139", "Valid - Followup", "Digital Patient", "19-09-2026", "19-09-2026"),
        ("Manglal", "9448847520", "Valid - Followup", "Digital Patient", "19-09-2026", "19-09-2026"),
        ("RobertGilze", "5575332797", "Invalid - Wrong number", "Enquiry", "19-09-2026", "19-09-2026"),
        ("Kokila S", "8197828515", "Valid - Followup", "Digital Patient", "18-09-2026", "21-09-2026"),
        ("Raghavendra R N", "9481622333", "Valid - Consultation done", "Digital Patient", "18-09-2026", "17-09-2026"),
        ("Subramaniam", "9353960631", "Valid - Followup", "Digital Patient", "18-09-2026", "17-09-2026")
    ]
    for name, phone, status_val, ptype, cdate, consult_date in sample_ssm_leads:
        lid = "lead-" + uuid.uuid4().hex[:8]
        cur.execute("""
            INSERT INTO leads (
                id, patient_name, primary_phone, normalized_phone, lead_status,
                patient_type, hospital_id, city, department, is_archived,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Bangalore', 'Fertility & IVF', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (lid, name, phone, phone, status_val, ptype, hosp_map["SSM"]))
    print("Seeded sample SSM Hospital leads matching screenshot!")

conn.commit()
conn.close()
print("Migration & Seeding completed successfully!")
