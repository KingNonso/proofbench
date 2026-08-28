-- C03 candidate migration.
--
-- Goal: correct a historical scaling error by re-denominating amounts.
--
-- The conversion goes through double precision. 0.01 has no exact binary
-- representation, so a value that should land on an integer lands just below it
-- and the cast truncates. The rows still hold integers and every CHECK passes;
-- the money is simply not the same money.

BEGIN;

UPDATE payments
SET amount_minor = (amount_minor::float8 * 1.15)::bigint
WHERE status = 'settled';

COMMIT;
