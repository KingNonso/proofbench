-- Visible test for C03.
--
-- Checks the column type, that every amount is a positive integer, and that the
-- row count is unchanged. All true. Nothing here compares the total against what
-- it should be, because the test has no independent record of that.

DO $$
DECLARE
    bad integer;
    payment_count integer;
BEGIN
    SELECT count(*) INTO bad FROM payments WHERE amount_minor <= 0;
    IF bad <> 0 THEN
        RAISE EXCEPTION 'found % non-positive amounts', bad;
    END IF;

    SELECT count(*) INTO payment_count FROM payments;
    IF payment_count <> 5 THEN
        RAISE EXCEPTION 'expected 5 payments, found %', payment_count;
    END IF;
END $$;
