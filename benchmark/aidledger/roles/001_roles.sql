-- Cluster-wide roles.
--
-- Created once at container bootstrap by the container administrator and
-- immutable for the life of the container. That immutability is what makes the
-- database-per-world optimisation safe: roles are not cloned by
-- CREATE DATABASE ... TEMPLATE, so they must never be world-specific.
--
-- The candidate migration runs as aidledger_migration, which is deliberately
-- unprivileged. A candidate that needs more than this is a containment failure.

CREATE ROLE aidledger_migration LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE aidledger_app LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE aidledger_org_admin LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE aidledger_auditor LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE aidledger_service LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- The migration role owns the tables it may alter. Ownership matters for RLS:
-- an owner bypasses row-level security unless FORCE is set, which is why
-- policies/001_rls.sql sets FORCE on every tenant-scoped table.
ALTER TABLE organizations  OWNER TO aidledger_migration;
ALTER TABLE currencies     OWNER TO aidledger_migration;
ALTER TABLE beneficiaries  OWNER TO aidledger_migration;
ALTER TABLE payments       OWNER TO aidledger_migration;
ALTER TABLE disbursements  OWNER TO aidledger_migration;
ALTER TABLE audit_events   OWNER TO aidledger_migration;

GRANT USAGE ON SCHEMA public TO
    aidledger_app, aidledger_org_admin, aidledger_auditor, aidledger_service;

-- Tenant worker: reads and writes its own organisation's operational data.
GRANT SELECT                       ON organizations, currencies TO aidledger_app;
GRANT SELECT, INSERT, UPDATE       ON beneficiaries, payments   TO aidledger_app;
GRANT INSERT                       ON audit_events              TO aidledger_app;

-- Organisation administrator: wider read within its own organisation.
GRANT SELECT ON organizations, currencies, beneficiaries, payments, disbursements
    TO aidledger_org_admin;

-- Auditor: history only, and only its own organisation's history.
GRANT SELECT ON audit_events TO aidledger_auditor;

-- Background settlement and backfill process.
GRANT SELECT                 ON organizations, currencies, beneficiaries TO aidledger_service;
GRANT SELECT, INSERT, UPDATE ON payments                                 TO aidledger_service;
GRANT SELECT, INSERT         ON disbursements                            TO aidledger_service;
GRANT INSERT                 ON audit_events                             TO aidledger_service;

-- No role anywhere is granted UPDATE or DELETE on audit_events.
