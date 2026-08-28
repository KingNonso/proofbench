-- AidLedger base schema.
--
-- Synthetic humanitarian cash-assistance system. No real organisation, person,
-- or transaction is represented here.
--
-- Money is integer minor units everywhere. There is deliberately no numeric or
-- floating point amount column: a migration that introduces one is the defect
-- under test in C03, not a schema this fixture ever permits.

CREATE TABLE organizations (
    org_id      uuid        PRIMARY KEY,
    name        text        NOT NULL,
    created_at  timestamptz NOT NULL
);

CREATE TABLE currencies (
    code              char(3)  PRIMARY KEY,
    name              text     NOT NULL,
    minor_unit_scale  smallint NOT NULL CHECK (minor_unit_scale BETWEEN 0 AND 4)
);

CREATE TABLE beneficiaries (
    beneficiary_id  uuid        PRIMARY KEY,
    org_id          uuid        NOT NULL REFERENCES organizations (org_id),
    external_ref    text        NOT NULL,
    full_name       text        NOT NULL,
    created_at      timestamptz NOT NULL,
    UNIQUE (org_id, external_ref)
);

-- The table C01 recreates. currency_code is nullable because historical rows
-- predate the currency field; whether those rows are USD is the C04 question and
-- cannot be settled from the data.
CREATE TABLE payments (
    payment_id      uuid        PRIMARY KEY,
    org_id          uuid        NOT NULL REFERENCES organizations (org_id),
    beneficiary_id  uuid        NOT NULL REFERENCES beneficiaries (beneficiary_id),
    amount_minor    bigint      NOT NULL CHECK (amount_minor > 0),
    currency_code   char(3)     REFERENCES currencies (code),
    status          text        NOT NULL
                                CHECK (status IN ('pending', 'approved', 'settled', 'cancelled')),
    created_at      timestamptz NOT NULL
);

CREATE TABLE disbursements (
    disbursement_id  uuid        PRIMARY KEY,
    org_id           uuid        NOT NULL REFERENCES organizations (org_id),
    payment_id       uuid        NOT NULL REFERENCES payments (payment_id),
    amount_minor     bigint      NOT NULL CHECK (amount_minor > 0),
    currency_code    char(3)     NOT NULL REFERENCES currencies (code),
    idempotency_key  text        NOT NULL,
    settled_at       timestamptz NOT NULL,
    UNIQUE (org_id, idempotency_key)
);

-- Append-only. No role is granted UPDATE or DELETE; C10 tests a migration that
-- removes or mutates history anyway.
CREATE TABLE audit_events (
    event_id     bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id       uuid        NOT NULL REFERENCES organizations (org_id),
    actor_role   text        NOT NULL,
    action       text        NOT NULL,
    entity_type  text        NOT NULL,
    entity_id    text        NOT NULL,
    occurred_at  timestamptz NOT NULL,
    payload      jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX payments_org_idx      ON payments (org_id);
CREATE INDEX disbursements_org_idx ON disbursements (org_id);
CREATE INDEX audit_events_org_idx  ON audit_events (org_id, occurred_at);
