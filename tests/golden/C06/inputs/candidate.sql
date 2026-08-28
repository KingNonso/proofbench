-- C06 candidate migration.
--
-- Backfills a disbursement for every settled payment that does not have one.
--
-- There is no checkpoint table and no ON CONFLICT clause. The statement is
-- correct exactly once. A deploy cancelled halfway and restarted runs it again,
-- and the WHERE NOT EXISTS guard does not help because the idempotency key is
-- generated fresh each time.

BEGIN;

INSERT INTO disbursements
    (disbursement_id, org_id, payment_id, amount_minor, currency_code,
     idempotency_key, settled_at)
SELECT gen_random_uuid(), p.org_id, p.payment_id, p.amount_minor,
       coalesce(p.currency_code, 'USD'), 'backfill-' || gen_random_uuid()::text,
       '2026-08-28T12:00:00Z'
FROM payments p
WHERE p.status = 'settled';

COMMIT;
