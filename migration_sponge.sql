-- === migration_sponge.sql ===
-- Run in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tnyjqpxrxiihuafqaluh/sql/new

CREATE TABLE IF NOT EXISTS sponge_transactions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id       text,
  service       text NOT NULL,
  amount_cents  integer DEFAULT 0,
  subject       text,
  school        text,
  tx_id         text,
  threat_level  integer,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sponge_transactions_created_at_idx ON sponge_transactions (created_at DESC);
CREATE INDEX IF NOT EXISTS sponge_transactions_call_id_idx    ON sponge_transactions (call_id);

ALTER TABLE sponge_transactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon read sponge_transactions"    ON sponge_transactions;
DROP POLICY IF EXISTS "service write sponge_transactions" ON sponge_transactions;
CREATE POLICY "anon read sponge_transactions"    ON sponge_transactions FOR SELECT USING (true);
CREATE POLICY "service write sponge_transactions" ON sponge_transactions FOR ALL    USING (true);
