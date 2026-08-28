-- Visible test for C04.
--
-- Checks what a reviewer would check: the column is now NOT NULL, every row has
-- a currency, no row was lost, and no amount moved.
--
-- It passes. It cannot do otherwise: whether 'USD' is the *right* value is not a
-- property of the database.

DO $$
DECLARE
    null_currencies integer;
    payment_count   integer;
    total_minor     bigint;
    is_nullable     text;
BEGIN
    SELECT count(*) INTO null_currencies FROM payments WHERE currency_code IS NULL;
    IF null_currencies <> 0 THEN
        RAISE EXCEPTION 'expected no null currencies, found %', null_currencies;
    END IF;

    SELECT is_nullable INTO is_nullable
    FROM information_schema.columns
    WHERE table_name = 'payments' AND column_name = 'currency_code';
    IF is_nullable <> 'NO' THEN
        RAISE EXCEPTION 'currency_code should be NOT NULL, found is_nullable=%', is_nullable;
    END IF;

    SELECT count(*), sum(amount_minor) INTO payment_count, total_minor FROM payments;
    IF payment_count <> 5 THEN
        RAISE EXCEPTION 'expected 5 payments, found %', payment_count;
    END IF;
    IF total_minor <> 875500 THEN
        RAISE EXCEPTION 'expected total 875500 minor units, found %', total_minor;
    END IF;
END $$;
