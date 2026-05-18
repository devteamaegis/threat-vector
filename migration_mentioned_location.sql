-- Stores geocoded coordinates of addresses *mentioned* in the call transcript
-- (e.g. "you live at 14158 Gallup Road") — separate from caller GPS (call_lat/call_lng)
-- Run in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tnyjqpxrxiihuafqaluh/sql/new

ALTER TABLE tips ADD COLUMN IF NOT EXISTS mentioned_lat  double precision;
ALTER TABLE tips ADD COLUMN IF NOT EXISTS mentioned_lng  double precision;
