-- C05 candidate migration.
--
-- Expand, migrate, and contract -- all three in one deploy. The contract step is
-- the problem: dropping amount_minor is safe only once every instance writing it
-- has been replaced, and during a rolling deploy that is not yet true.

BEGIN;

ALTER TABLE payments ADD COLUMN amount_scaled bigint;
UPDATE payments SET amount_scaled = amount_minor;
ALTER TABLE payments ALTER COLUMN amount_scaled SET NOT NULL;
ALTER TABLE payments DROP COLUMN amount_minor;

COMMIT;
