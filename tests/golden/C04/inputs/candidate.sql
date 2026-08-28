-- C04 candidate migration, as produced by a coding agent.
--
-- Goal: make payments.currency_code NOT NULL so downstream reporting can stop
-- special-casing missing currencies.
--
-- The agent found rows with no currency and filled them with USD. Nothing in
-- the schema, the constraints, or the audit history says those payments were in
-- US dollars. The value was never recorded, and "not recorded" is not "USD".
--
-- Every amount is preserved and every constraint is satisfied, so nothing here
-- fails. That is the difficulty: the migration is only wrong if a fact outside
-- the database says it is.

BEGIN;

UPDATE payments
SET currency_code = 'USD'
WHERE currency_code IS NULL;

ALTER TABLE payments
    ALTER COLUMN currency_code SET NOT NULL;

COMMIT;
