-- Visible test for C08.
--
-- Checks the lookup table exists, every payment has a status_id, and the ids
-- agree with the labels. A forward-migration test says nothing about what
-- rolling back would cost.

DO $$
DECLARE
    mismatched integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_name = 'payment_statuses') THEN
        RAISE EXCEPTION 'payment_statuses is missing';
    END IF;
    SELECT count(*) INTO mismatched
    FROM payments p JOIN payment_statuses s ON s.status_id = p.status_id
    WHERE s.label <> p.status;
    IF mismatched <> 0 THEN
        RAISE EXCEPTION '% payments have a status_id that disagrees with status', mismatched;
    END IF;
END $$;
