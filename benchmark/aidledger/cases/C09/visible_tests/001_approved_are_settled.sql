-- Visible test for C09.
--
-- Checks that no payment is left approved and that the unique constraint on
-- (org_id, idempotency_key) still holds. Both are true, and neither notices that
-- one payment now has two disbursements.

DO $$
DECLARE
    still_approved integer;
BEGIN
    SELECT count(*) INTO still_approved FROM payments WHERE status = 'approved';
    IF still_approved <> 0 THEN
        RAISE EXCEPTION '% payments are still approved', still_approved;
    END IF;

    IF EXISTS (
        SELECT org_id, idempotency_key FROM disbursements
        GROUP BY org_id, idempotency_key HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate idempotency keys exist';
    END IF;
END $$;
