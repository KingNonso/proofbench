-- Visible test for C05.
--
-- Checks the new column exists, is populated, and the old one is gone -- exactly
-- what the migration set out to do. A single-version test cannot see a rollout.

DO $$
DECLARE
    nulls integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payments' AND column_name = 'amount_scaled') THEN
        RAISE EXCEPTION 'amount_scaled is missing';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'payments' AND column_name = 'amount_minor') THEN
        RAISE EXCEPTION 'amount_minor should have been dropped';
    END IF;
    SELECT count(*) INTO nulls FROM payments WHERE amount_scaled IS NULL;
    IF nulls <> 0 THEN
        RAISE EXCEPTION '% rows have no amount_scaled', nulls;
    END IF;
END $$;
