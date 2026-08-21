"""
Santasa IVF CRM - Supabase 24/7 Keep-Alive Cron Script
Run this script periodically (e.g. daily/weekly) to ensure your Supabase PostgreSQL instance stays active.
"""
import os
import sys

def ping_supabase():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
    )
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        res = cur.fetchone()
        print(f"Supabase Heartbeat OK: {res}")
        conn.close()
    except Exception as e:
        print(f"Supabase connection error: {e}")

if __name__ == "__main__":
    ping_supabase()
