import sys
import os
import uuid
root_dir = r'D:\Santasa IVF\CRM'
backend_dir = os.path.join(root_dir, 'hospital_crm', 'backend')
sys.path.insert(0, backend_dir)
sys.path.insert(0, root_dir)
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
count_smh = db.execute(text("SELECT count(*) FROM leads WHERE hospital_code = 'SMH'")).scalar()
print("Current SMH leads:", count_smh)

if count_smh == 0:
    sample_smh = [
        ("Lakshmi Devi M", "9845112233", "Valid - Followup", "Digital Patient", "Mysore", "IVF & Infertility"),
        ("Anitha Suresh", "9741223344", "Valid - Consultation done", "Digital Patient", "Mysore", "IUI Consultation"),
        ("Pradeep Kumar G", "9900334455", "New", "Enquiry", "Mysore", "Fertility Workup"),
        ("Deepa R", "9448445566", "Valid - Followup", "Digital Patient", "Mysore", "Laparoscopy Evaluation"),
        ("Kavitha Manjunath", "9148556677", "Valid - Consultation done", "Digital Patient", "Mysore", "IVF Cycle Review")
    ]
    for name, phone, status_val, ptype, city, treatment in sample_smh:
        lid = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO leads (
                id, patient_name, primary_phone, normalized_phone, lead_status,
                patient_type, hospital_id, hospital_code, city, department, treatment,
                is_archived, created_at, updated_at
            ) VALUES (
                :id, :name, :phone, :phone, :status,
                :ptype, 'hosp-smh-42546563', 'SMH', :city, 'Fertility & IVF', :treatment,
                false, NOW(), NOW()
            )
        """), {
            "id": lid, "name": name, "phone": phone, "status": status_val,
            "ptype": ptype, "city": city, "treatment": treatment
        })
    db.commit()
    print("Seeded 5 sample Mysore leads!")

count_smh = db.execute(text("SELECT count(*) FROM leads WHERE hospital_code = 'SMH'")).scalar()
print("New SMH leads count in Supabase:", count_smh)
db.close()
