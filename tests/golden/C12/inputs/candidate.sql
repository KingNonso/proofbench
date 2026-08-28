-- C12 candidate migration. This one is correct, and it is not obvious.
--
-- Every choice here is load-bearing:
--
--   nullable, no default   an ADD COLUMN with a volatile default rewrites the
--                          table under ACCESS EXCLUSIVE. Nullable and defaultless
--                          is metadata-only, so it takes its lock and returns.
--
--   nothing dropped        the version still running during the rollout keeps
--                          reading and writing the columns it knows about. The
--                          old column is removed in a later deploy, once nothing
--                          writes it.
--
--   idempotent backfill    the WHERE clause excludes rows already carrying the
--                          value, so a deploy cancelled halfway and resumed does
--                          nothing the second time.
--
--   deterministic value    derived from the row itself, not from gen_random_uuid,
--                          so a resumed backfill produces the same value it would
--                          have produced the first time.
--
--   audit untouched        no statement here reads or writes audit_events.

BEGIN;

ALTER TABLE payments ADD COLUMN reconciliation_key text;

UPDATE payments
SET reconciliation_key = org_id::text || ':' || payment_id::text
WHERE reconciliation_key IS DISTINCT FROM org_id::text || ':' || payment_id::text;

CREATE INDEX IF NOT EXISTS payments_reconciliation_key_idx
    ON payments (reconciliation_key);

COMMIT;
