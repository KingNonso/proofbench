-- C11 candidate migration. This one is correct.
--
-- Nullable column, so the add is metadata-only and takes no rewrite lock. The
-- backfill is expressed so that running it again changes nothing. Nothing is
-- dropped, so the version still running during the rollout keeps working. Row
-- level security is not recreated because the table is not recreated.

BEGIN;

ALTER TABLE payments ADD COLUMN settlement_reference text;

UPDATE payments p
SET settlement_reference = 'ref-' || d.disbursement_id::text
FROM disbursements d
WHERE d.payment_id = p.payment_id
  AND p.settlement_reference IS DISTINCT FROM 'ref-' || d.disbursement_id::text;

COMMIT;
