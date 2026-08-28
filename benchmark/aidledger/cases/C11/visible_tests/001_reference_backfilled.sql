-- Visible test for C11.

DO $$
DECLARE
    settled_without_reference integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payments' AND column_name = 'settlement_reference') THEN
        RAISE EXCEPTION 'settlement_reference is missing';
    END IF;

    SELECT count(*) INTO settled_without_reference
    FROM payments p
    WHERE EXISTS (SELECT 1 FROM disbursements d WHERE d.payment_id = p.payment_id)
      AND p.settlement_reference IS NULL;
    IF settled_without_reference <> 0 THEN
        RAISE EXCEPTION '% disbursed payments have no reference', settled_without_reference;
    END IF;
END $$;
