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
