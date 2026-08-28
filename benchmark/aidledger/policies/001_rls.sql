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
