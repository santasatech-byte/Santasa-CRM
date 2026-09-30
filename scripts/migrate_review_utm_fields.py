import os
import sqlite3
from sqlalchemy import create_engine, text

def migrate_sqlite():
    db_path = "hospital_crm.db"
    if not os.path.exists(db_path):
        print("hospital_crm.db not found, skipping SQLite.")
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cols = [
        ("review_needed", "VARCHAR(20)"),
        ("review_period", "VARCHAR(100)"),
        ("next_review_date", "DATETIME"),
        ("review_details", "TEXT"),
        ("utm_source", "VARCHAR(255)"),
        ("utm_medium", "VARCHAR(255)"),
        ("utm_campaign", "VARCHAR(255)"),
        ("utm_term", "VARCHAR(255)"),
        ("utm_content", "VARCHAR(255)"),
        ("lead_url", "VARCHAR(500)")
    ]
    cur.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cur.fetchall()}
    for col, col_type in cols:
        if col not in existing:
            cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_type}")
            print(f"Added {col} to SQLite leads table")
    conn.commit()
    conn.close()

def migrate_postgres():
    from dotenv import load_dotenv
    load_dotenv("hospital_crm/backend/.env")
    DATABASE_URL = os.getenv("DATABASE_URL")
    print("Connecting to database...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            cols = [
                ("review_needed", "VARCHAR(20)"),
                ("review_period", "VARCHAR(100)"),
                ("next_review_date", "TIMESTAMP WITH TIME ZONE"),
                ("review_details", "TEXT"),
                ("utm_source", "VARCHAR(255)"),
                ("utm_medium", "VARCHAR(255)"),
                ("utm_campaign", "VARCHAR(255)"),
                ("utm_term", "VARCHAR(255)"),
                ("utm_content", "VARCHAR(255)"),
                ("lead_url", "VARCHAR(500)")
            ]
            for col, col_type in cols:
                try:
                    conn.execute(text(f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                    print(f"Added {col} to Postgres leads table")
                except Exception as e:
                    print(f"Postgres column {col} notice: {e}")
            conn.commit()
            print("Postgres review and UTM migration complete!")
    except Exception as e:
        print("Postgres connection error:", e)

if __name__ == "__main__":
    migrate_sqlite()
    migrate_postgres()
