-- Visible test for C02.
--
-- Checks that row-level security is enabled and that the application can still
-- read its own organisation. Both are true. Whether every *other* declared role
-- kept its access is not something this test looks at, which is the point.

DO $$
DECLARE
    rls_on boolean;
    policies integer;
BEGIN
    SELECT relrowsecurity INTO rls_on FROM pg_class WHERE relname = 'payments';
    IF NOT rls_on THEN
        RAISE EXCEPTION 'row-level security is not enabled on payments';
    END IF;

    SELECT count(*) INTO policies FROM pg_policies WHERE tablename = 'payments';
    IF policies < 2 THEN
        RAISE EXCEPTION 'expected policies on payments, found %', policies;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payments' AND column_name = 'reconciled_at') THEN
        RAISE EXCEPTION 'reconciled_at was not added';
    END IF;
END $$;
