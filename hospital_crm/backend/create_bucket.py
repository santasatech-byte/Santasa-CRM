import psycopg2

conn = psycopg2.connect("postgresql://postgres.vdwpxcdpzhreonutitrc:cmW7zEtAJH5ziFyo@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require")
cur = conn.cursor()

# 1. Create public bucket
cur.execute("""
  INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  VALUES ('santasa-recordings', 'santasa-recordings', true, 52428800, ARRAY['audio/mp4', 'audio/x-m4a', 'audio/m4a', 'audio/mpeg', 'audio/wav', 'audio/aac'])
  ON CONFLICT (id) DO UPDATE SET public = true;
""")

# 2. Add storage policy
cur.execute("""
  DROP POLICY IF EXISTS "Public Access santasa-recordings" ON storage.objects;
  CREATE POLICY "Public Access santasa-recordings" ON storage.objects
  FOR ALL TO public
  USING (bucket_id = 'santasa-recordings')
  WITH CHECK (bucket_id = 'santasa-recordings');
""")

conn.commit()
print("santasa-recordings bucket successfully created and public access granted!")
conn.close()
