import os
import sys
import uuid
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

print("Connecting to Supabase PostgreSQL...")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Connected to PostgreSQL successfully!")

    # 1. Ensure hospitals table
    conn.execute(text("""
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
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """))
    conn.commit()

    # 2. Add columns if not exist
    def add_col(tbl, col, typedef):
        try:
            conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typedef};"))
            conn.commit()
            print(f"Added {col} to {tbl}")
        except Exception as e:
            print(f"Note on {tbl}.{col}: {e}")

    add_col("users", "hospital_id", "VARCHAR(36)")
    add_col("leads", "hospital_id", "VARCHAR(36)")
    add_col("calls", "hospital_id", "VARCHAR(36)")

    add_col("leads", "patient_type", "VARCHAR(50) DEFAULT 'Enquiry'")
    add_col("leads", "patient_id_mrn", "VARCHAR(100)")
    add_col("leads", "registered_number", "VARCHAR(50)")
    add_col("leads", "treatment", "VARCHAR(255)")
    add_col("leads", "message", "TEXT")
    add_col("leads", "consultation_date", "TIMESTAMP WITH TIME ZONE")
    add_col("leads", "surgery_date", "TIMESTAMP WITH TIME ZONE")
    add_col("leads", "surgery_requirement", "VARCHAR(255)")
    add_col("leads", "surgery_details", "TEXT")
    add_col("leads", "destination_number", "VARCHAR(50)")

    # 3. Seed hospitals in Postgres
    hospitals = conn.execute(text("SELECT id, code FROM hospitals")).fetchall()
    hosp_map = {h[1]: h[0] for h in hospitals}

    if "SSM" not in hosp_map:
        ssm_id = "hosp-ssm-" + uuid.uuid4().hex[:8]
        conn.execute(text("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (:id, 'SSM Hospital', 'SSM', 'Bangalore', 'Karnataka', 'India', NOW(), NOW())"), {"id": ssm_id})
        hosp_map["SSM"] = ssm_id
        print("Created SSM Hospital in Supabase:", ssm_id)

    if "SHH" not in hosp_map:
        shh_id = "hosp-shh-" + uuid.uuid4().hex[:8]
        conn.execute(text("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (:id, 'Santasa Hassan Hospital', 'SHH', 'Hassan', 'Karnataka', 'India', NOW(), NOW())"), {"id": shh_id})
        hosp_map["SHH"] = shh_id
        print("Created Santasa Hassan Hospital in Supabase:", shh_id)

    if "SMH" not in hosp_map:
        smh_id = "hosp-smh-" + uuid.uuid4().hex[:8]
        conn.execute(text("INSERT INTO hospitals (id, name, code, city, state, country, created_at, updated_at) VALUES (:id, 'Santasa Mysore Hospital', 'SMH', 'Mysore', 'Karnataka', 'India', NOW(), NOW())"), {"id": smh_id})
        hosp_map["SMH"] = smh_id
        print("Created Santasa Mysore Hospital in Supabase:", smh_id)

    conn.commit()

    # 4. Seed users
    sys.path.append("hospital_crm/backend")
    from app.core.security import hash_password
    exec_hash = hash_password("Executive@2026!")
    admin_hash = hash_password("Admin@2026!")

    def upsert_user(email, name, role, pwhash, hosp_id):
        existing = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
        if not existing:
            uid = "user-" + uuid.uuid4().hex[:8]
            conn.execute(text("""
                INSERT INTO users (id, email, full_name, role, hashed_password, is_active, hospital_id, created_at, updated_at)
                VALUES (:id, :email, :name, :role, :pwhash, true, :hosp_id, NOW(), NOW())
            """), {"id": uid, "email": email, "name": name, "role": role, "pwhash": pwhash, "hosp_id": hosp_id})
            print(f"Created user {email} in Supabase")
        else:
            conn.execute(text("""
                UPDATE users SET hospital_id = :hosp_id, full_name = :name, hashed_password = :pwhash WHERE email = :email
            """), {"hosp_id": hosp_id, "name": name, "pwhash": pwhash, "email": email})
            print(f"Updated user {email} with hospital_id in Supabase")
        conn.commit()

    upsert_user("ssm@hospital.com", "SSM Hospital Executive", "CRM Executive", exec_hash, hosp_map["SSM"])
    upsert_user("executive@santasa.com", "Santasa Hassan Executive", "CRM Executive", exec_hash, hosp_map["SHH"])
    upsert_user("mysore@santasa.com", "Santasa Mysore Executive", "CRM Executive", exec_hash, hosp_map["SMH"])
    upsert_user("admin@santasa.com", "Super Administrator", "Super Admin", admin_hash, hosp_map["SHH"])

    # Update existing leads without hospital_id to SHH
    conn.execute(text("UPDATE leads SET hospital_id = :shh WHERE hospital_id IS NULL"), {"shh": hosp_map["SHH"]})
    conn.commit()

    # Seed SSM reference leads if SSM has no leads
    count_ssm = conn.execute(text("SELECT count(*) FROM leads WHERE hospital_id = :ssm"), {"ssm": hosp_map["SSM"]}).fetchone()[0]
    print(f"Current SSM Leads in Supabase: {count_ssm}")

    if count_ssm == 0:
        sample_ssm_leads = [
            ("Nending Asha", "7005940191", "Valid - Followup", "Digital Patient"),
            ("Somachar", "9086168095", "Valid - Consultation done", "Digital Patient"),
            ("NARETGR131607/NEYRTHYT", "8733439841", "New", "Enquiry"),
            ("JustinKoymn", "6622865748", "New", "Enquiry"),
            ("Humaira Fatima", "7760260139", "Valid - Followup", "Digital Patient"),
            ("Manglal", "9448847520", "Valid - Followup", "Digital Patient"),
            ("RobertGilze", "5575332797", "Invalid - Wrong number", "Enquiry"),
            ("Kokila S", "8197828515", "Valid - Followup", "Digital Patient"),
            ("Raghavendra R N", "9481622333", "Valid - Consultation done", "Digital Patient"),
            ("Subramaniam", "9353960631", "Valid - Followup", "Digital Patient")
        ]
        for name, phone, status_val, ptype in sample_ssm_leads:
            lid = "lead-" + uuid.uuid4().hex[:8]
            conn.execute(text("""
                INSERT INTO leads (
                    id, patient_name, primary_phone, normalized_phone, lead_status,
                    patient_type, hospital_id, city, department, is_archived,
                    created_at, updated_at
                ) VALUES (
                    :id, :name, :phone, :phone, :status,
                    :ptype, :hosp_id, 'Bangalore', 'Fertility & IVF', false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """), {"id": lid, "name": name, "phone": phone, "status": status_val, "ptype": ptype, "hosp_id": hosp_map["SSM"]})
        conn.commit()
        print("Seeded reference SSM leads in Supabase PostgreSQL!")

print("Postgres Migration & Seeding Complete!")
