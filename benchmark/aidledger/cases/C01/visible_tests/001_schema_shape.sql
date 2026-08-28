-- Visible test for C01.
--
-- Checks what a reviewer would naturally check: the new column exists, the old
-- columns survived, the row count is preserved, and the foreign key is back.
--
-- It passes against the unsafe candidate. It says nothing about row-level
-- security, which is the point of the case.
--
-- Run with: psql -v ON_ERROR_STOP=1. Assertions raise, so a non-zero exit is a
-- failure and there is no output to parse.

DO $$
DECLARE
    missing text;
    payment_count integer;
BEGIN
    SELECT string_agg(expected, ', ')
    INTO missing
    FROM unnest(ARRAY[
        'payment_id', 'org_id', 'beneficiary_id', 'amount_minor',
        'currency_code', 'status', 'created_at', 'settlement_reference'
    ]) AS expected
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payments' AND column_name = expected
    );

    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'payments is missing expected columns: %', missing;
    END IF;

    SELECT count(*) INTO payment_count FROM payments;
    IF payment_count <> 5 THEN
        RAISE EXCEPTION 'expected 5 payments after migration, found %', payment_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'disbursements'
          AND constraint_name = 'disbursements_payment_id_fkey'
    ) THEN
        RAISE EXCEPTION 'disbursements lost its foreign key to payments';
    END IF;
END $$;
