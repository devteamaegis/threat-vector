-- Run in Supabase SQL editor
CREATE TABLE IF NOT EXISTS live_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id text UNIQUE NOT NULL,
  words_so_far text DEFAULT '',
  probability_pct numeric DEFAULT 0.2,
  threat_level integer DEFAULT 1,
  top_features text[] DEFAULT '{}',
  status text DEFAULT 'active',
  school_name text,
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE live_calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read live_calls" ON live_calls FOR SELECT USING (true);
CREATE POLICY "service write live_calls" ON live_calls FOR ALL USING (true);
