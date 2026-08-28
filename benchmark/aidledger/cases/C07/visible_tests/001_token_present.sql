-- Visible test for C07.
--
-- Checks the column exists, is NOT NULL, and every row has a distinct token. All
-- true, and all reachable in milliseconds on a database nobody else is using.

DO $$
DECLARE
    distinct_tokens integer;
    total integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payments' AND column_name = 'reconciliation_token'
                     AND is_nullable = 'NO') THEN
        RAISE EXCEPTION 'reconciliation_token is missing or nullable';
    END IF;
    SELECT count(DISTINCT reconciliation_token), count(*) INTO distinct_tokens, total
    FROM payments;
    IF distinct_tokens <> total THEN
        RAISE EXCEPTION 'tokens are not distinct: % of %', distinct_tokens, total;
    END IF;
END $$;
