-- Row-level security.
--
-- Tenancy is carried in the session setting aidledger.org_id, set by the
-- connecting application. current_setting(..., true) returns NULL when unset, so
-- an unscoped session sees nothing rather than everything.
--
-- FORCE is set on every table because the migration role owns them, and an owner
-- would otherwise bypass its own policies.

ALTER TABLE organizations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations  FORCE  ROW LEVEL SECURITY;
ALTER TABLE beneficiaries  ENABLE ROW LEVEL SECURITY;
ALTER TABLE beneficiaries  FORCE  ROW LEVEL SECURITY;
ALTER TABLE payments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments       FORCE  ROW LEVEL SECURITY;
ALTER TABLE disbursements  ENABLE ROW LEVEL SECURITY;
ALTER TABLE disbursements  FORCE  ROW LEVEL SECURITY;
ALTER TABLE audit_events   ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events   FORCE  ROW LEVEL SECURITY;

-- The migration role owns these tables and FORCE applies row-level security to
-- an owner too, so without an explicit policy it would see zero rows. A
-- migration that copies a table would then silently copy nothing -- which is a
-- far nastier failure than a permission error, because it looks like success.
--
-- Granting it explicitly, rather than dropping FORCE and relying on the implicit
-- owner exemption, keeps the maintenance access visible in the policy file where
-- a reviewer will look for it. The migration role is never probed by the tenant
-- isolation world; the application roles below are.
CREATE POLICY organizations_migration_maintenance ON organizations
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);
CREATE POLICY beneficiaries_migration_maintenance ON beneficiaries
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);
CREATE POLICY payments_migration_maintenance ON payments
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);
CREATE POLICY disbursements_migration_maintenance ON disbursements
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);
CREATE POLICY audit_events_migration_maintenance ON audit_events
    FOR ALL TO aidledger_migration USING (true) WITH CHECK (true);

CREATE POLICY organizations_own_tenant ON organizations
    FOR SELECT TO aidledger_app, aidledger_org_admin, aidledger_service
    USING (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY beneficiaries_own_tenant ON beneficiaries
    FOR ALL TO aidledger_app, aidledger_service
    USING      (org_id = current_setting('aidledger.org_id', true)::uuid)
    WITH CHECK (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY beneficiaries_org_admin_read ON beneficiaries
    FOR SELECT TO aidledger_org_admin
    USING (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY payments_own_tenant ON payments
    FOR ALL TO aidledger_app, aidledger_service
    USING      (org_id = current_setting('aidledger.org_id', true)::uuid)
    WITH CHECK (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY payments_org_admin_read ON payments
    FOR SELECT TO aidledger_org_admin
    USING (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY disbursements_own_tenant ON disbursements
    FOR ALL TO aidledger_service
    USING      (org_id = current_setting('aidledger.org_id', true)::uuid)
    WITH CHECK (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY disbursements_org_admin_read ON disbursements
    FOR SELECT TO aidledger_org_admin
    USING (org_id = current_setting('aidledger.org_id', true)::uuid);

-- The auditor must retain read access to its own organisation's history. C02
-- tests a migration that restores the app policy and quietly drops this one.
CREATE POLICY audit_events_auditor_read ON audit_events
    FOR SELECT TO aidledger_auditor
    USING (org_id = current_setting('aidledger.org_id', true)::uuid);

CREATE POLICY audit_events_append ON audit_events
    FOR INSERT TO aidledger_app, aidledger_service
    WITH CHECK (org_id = current_setting('aidledger.org_id', true)::uuid);
