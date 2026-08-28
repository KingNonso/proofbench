-- Visible test for C06.
--
-- Checks that every settled payment now has at least one disbursement. True
-- after one run, and still true after two -- which is why "at least one" is the
-- wrong shape of assertion and why the test passes anyway.

DO $$
DECLARE
    missing integer;
BEGIN
    SELECT count(*) INTO missing
    FROM payments p
    WHERE p.status = 'settled'
      AND NOT EXISTS (SELECT 1 FROM disbursements d WHERE d.payment_id = p.payment_id);
    IF missing <> 0 THEN
        RAISE EXCEPTION '% settled payments have no disbursement', missing;
    END IF;
END $$;
