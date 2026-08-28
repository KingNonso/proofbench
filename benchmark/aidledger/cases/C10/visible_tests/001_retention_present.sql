-- Visible test for C10.
--
-- Checks the retention column exists and is populated for every remaining event.
-- It has no record of which events existed before, so it cannot notice that some
-- are missing.

DO $$
DECLARE
    unset integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'audit_events' AND column_name = 'retain_until') THEN
        RAISE EXCEPTION 'retain_until is missing';
    END IF;
    SELECT count(*) INTO unset FROM audit_events WHERE retain_until IS NULL;
    IF unset <> 0 THEN
        RAISE EXCEPTION '% audit events have no retention date', unset;
    END IF;
END $$;
