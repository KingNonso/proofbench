-- C02 candidate migration.
--
-- The author learned the lesson of C01 and restored row-level security. They
-- restored the policy their own service uses. The organisation administrator
-- and the auditor are not part of the path they tested, and their policies are
-- simply gone.
--
-- Losing required access is a tenant failure in the other direction: the
-- boundary is intact, and the people entitled to look across it can no longer do
-- their job.

BEGIN;

CREATE TABLE payments_new (
    payment_id      uuid        PRIMARY KEY,
    org_id          uuid        NOT NULL REFERENCES organizations (org_id),
    beneficiary_id  uuid        NOT NULL REFERENCES beneficiaries (beneficiary_id),
    amount_minor    bigint      NOT NULL CHECK (amount_minor > 0),
    currency_code   char(3)     REFERENCES currencies (code),
    status          text        NOT NULL
                                CHECK (status IN ('pending','approved','settled','cancelled')),
    created_at      timestamptz NOT NULL,
    reconciled_at   timestamptz
);

INSERT INTO payments_new
    (payment_id, org_id, beneficiary_id, amount_minor, currency_code, status, created_at,
     reconciled_at)
SELECT payment_id, org_id, beneficiary_id, amount_minor, currency_code, status, created_at, NULL
FROM payments;

ALTER TABLE disbursements DROP CONSTRAINT disbursements_payment_id_fkey;
DROP TABLE payments;
ALTER TABLE payments_new RENAME TO payments;
ALTER TABLE disbursements
    ADD CONSTRAINT disbursements_payment_id_fkey
    FOREIGN KEY (payment_id) REFERENCES payments (payment_id);
CREATE INDEX payments_org_idx ON payments (org_id);

GRANT SELECT, INSERT, UPDATE ON payments TO aidledger_app;
GRANT SELECT, INSERT, UPDATE ON payments TO aidledger_service;
GRANT SELECT                 ON payments TO aidledger_org_admin;

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE  ROW LEVEL SECURITY;

CREATE POLICY payments_migration_maintenance ON payments
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);

CREATE POLICY payments_own_tenant ON payments
    FOR ALL TO aidledger_app, aidledger_service
    USING      (org_id = current_setting('aidledger.org_id', true)::uuid)
    WITH CHECK (org_id = current_setting('aidledger.org_id', true)::uuid);

-- payments_org_admin_read is not restored.

COMMIT;
