-- C12 rollback.
--
-- Drops only what the migration added. It does not restore a snapshot, so a
-- payment written after the migration began is still there afterwards -- which
-- is the difference between a rollback and a restore.

BEGIN;

DROP INDEX IF EXISTS payments_reconciliation_key_idx;
ALTER TABLE payments DROP COLUMN IF EXISTS reconciliation_key;

COMMIT;
