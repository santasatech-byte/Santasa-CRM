import psycopg2

db_url = "postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# 1. Insert into storage.buckets if not exists
cur.execute("""
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('call-recordings', 'call-recordings', true, 52428800, ARRAY['audio/mp4', 'audio/x-m4a', 'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/aac', 'audio/amr'])
ON CONFLICT (id) DO UPDATE SET public = true;
""")

# 2. Allow public read/write access on storage.objects for call-recordings
cur.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Public Access for Call Recordings' AND tablename = 'objects'
    ) THEN
        CREATE POLICY "Public Access for Call Recordings" ON storage.objects
        FOR ALL USING (bucket_id = 'call-recordings')
        WITH CHECK (bucket_id = 'call-recordings');
    END IF;
END $$;
""")

conn.commit()
print("SUCCESSFULLY CREATED CALL-RECORDINGS BUCKET WITH PUBLIC ACCESS IN SUPABASE!")
conn.close()
