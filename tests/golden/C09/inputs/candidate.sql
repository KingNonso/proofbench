-- C09 candidate migration.
--
-- Settles approved payments by creating disbursements, retrying once so a
-- transient failure does not abort the whole deploy.
--
-- Each attempt generates a new idempotency key. The UNIQUE (org_id,
-- idempotency_key) constraint is therefore satisfied by both attempts, and the
-- beneficiary is paid twice. The constraint that exists to prevent exactly this
-- is doing its job on a key that no longer identifies the operation.

BEGIN;

INSERT INTO disbursements
    (disbursement_id, org_id, payment_id, amount_minor, currency_code,
     idempotency_key, settled_at)
SELECT gen_random_uuid(), p.org_id, p.payment_id, p.amount_minor,
       coalesce(p.currency_code, 'USD'), 'settle-attempt-1-' || gen_random_uuid()::text,
       '2026-08-28T12:00:00Z'
FROM payments p
WHERE p.status = 'approved';

-- Retry of the same logical operation, as the deploy script would issue it.
INSERT INTO disbursements
    (disbursement_id, org_id, payment_id, amount_minor, currency_code,
     idempotency_key, settled_at)
SELECT gen_random_uuid(), p.org_id, p.payment_id, p.amount_minor,
       coalesce(p.currency_code, 'USD'), 'settle-attempt-2-' || gen_random_uuid()::text,
       '2026-08-28T12:00:00Z'
FROM payments p
WHERE p.status = 'approved';

UPDATE payments SET status = 'settled' WHERE status = 'approved';

COMMIT;
