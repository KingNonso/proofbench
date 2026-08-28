-- Visible test for C12.

DO $$
DECLARE
    unset integer;
    total integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payments' AND column_name = 'reconciliation_key') THEN
        RAISE EXCEPTION 'reconciliation_key is missing';
    END IF;

    SELECT count(*) INTO unset FROM payments WHERE reconciliation_key IS NULL;
    IF unset <> 0 THEN
        RAISE EXCEPTION '% payments have no reconciliation key', unset;
    END IF;

    SELECT count(DISTINCT reconciliation_key), count(*) INTO unset, total FROM payments;
    IF unset <> total THEN
        RAISE EXCEPTION 'reconciliation keys are not unique: % of %', unset, total;
    END IF;
END $$;
