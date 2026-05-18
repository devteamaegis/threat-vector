-- === migration.sql ===
-- Run this in the Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tnyjqpxrxiihuafqaluh/sql/new

ALTER TABLE tips
  ADD COLUMN IF NOT EXISTS caller_emotion text,
  ADD COLUMN IF NOT EXISTS caller_tone text,
  ADD COLUMN IF NOT EXISTS escalation_risk text,
  ADD COLUMN IF NOT EXISTS credibility_signals jsonb,
  ADD COLUMN IF NOT EXISTS key_facts jsonb,
  ADD COLUMN IF NOT EXISTS timeline text,
  ADD COLUMN IF NOT EXISTS location_detail text,
  ADD COLUMN IF NOT EXISTS subject_description text,
  ADD COLUMN IF NOT EXISTS call_duration_seconds integer,
  ADD COLUMN IF NOT EXISTS caller_language text,
  ADD COLUMN IF NOT EXISTS multilingual_call boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS english_translation text,
  ADD COLUMN IF NOT EXISTS gemini_level integer,
  ADD COLUMN IF NOT EXISTS gemini_reasoning text,
  ADD COLUMN IF NOT EXISTS consensus boolean,
  ADD COLUMN IF NOT EXISTS three_model_consensus boolean,
  ADD COLUMN IF NOT EXISTS bayes_probability_pct numeric,
  ADD COLUMN IF NOT EXISTS bayes_ci_low_pct numeric,
  ADD COLUMN IF NOT EXISTS bayes_ci_high_pct numeric,
  ADD COLUMN IF NOT EXISTS bayes_top_drivers jsonb,
  ADD COLUMN IF NOT EXISTS bayes_features_hit jsonb,
  ADD COLUMN IF NOT EXISTS s3_archive_uri text,
  ADD COLUMN IF NOT EXISTS deepgram_confidence numeric,
  ADD COLUMN IF NOT EXISTS deepgram_language text,
  ADD COLUMN IF NOT EXISTS cross_school_alert text,
  ADD COLUMN IF NOT EXISTS threat_window text,
  ADD COLUMN IF NOT EXISTS threat_window_confidence text,
  ADD COLUMN IF NOT EXISTS dispatch_brief text,
  ADD COLUMN IF NOT EXISTS osint_findings text,
  ADD COLUMN IF NOT EXISTS prior_tips_context text,
  ADD COLUMN IF NOT EXISTS pipeline_errors jsonb,
  ADD COLUMN IF NOT EXISTS call_lat float8,
  ADD COLUMN IF NOT EXISTS call_lng float8,
  ADD COLUMN IF NOT EXISTS location_context text;


-- === migration_attendance_logs.sql ===
-- Attendance calls are logged here instead of entering the threat pipeline.
CREATE TABLE IF NOT EXISTS attendance_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id text,
  school_name text,
  student_name text,
  teacher_name text,
  grade text,
  absence_date date DEFAULT current_date,
  reason text,
  submitted_at timestamptz DEFAULT now()
);

ALTER TABLE attendance_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon read attendance_logs" ON attendance_logs;
DROP POLICY IF EXISTS "service write attendance_logs" ON attendance_logs;
CREATE POLICY "anon read attendance_logs" ON attendance_logs FOR SELECT USING (true);
CREATE POLICY "service write attendance_logs" ON attendance_logs FOR ALL USING (true);


-- === migration_live_calls.sql ===
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
DROP POLICY IF EXISTS "anon read live_calls" ON live_calls;
DROP POLICY IF EXISTS "service write live_calls" ON live_calls;
CREATE POLICY "anon read live_calls" ON live_calls FOR SELECT USING (true);
CREATE POLICY "service write live_calls" ON live_calls FOR ALL USING (true);

