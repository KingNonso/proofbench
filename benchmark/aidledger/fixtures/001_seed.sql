-- Synthetic seed data. Every identifier, name, amount, and timestamp is fixed so
-- the initial state hash is identical on every machine (PRD-NFR-003).
--
-- Two organisations exist so a tenant isolation failure is observable: any query
-- scoped to Northwind that returns a Southgate row is a confirmed leak.

INSERT INTO currencies (code, name, minor_unit_scale) VALUES
    ('USD', 'United States dollar', 2),
    ('KES', 'Kenyan shilling',      2),
    ('JPY', 'Japanese yen',         0);

INSERT INTO organizations (org_id, name, created_at) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Northwind Relief',  '2024-01-15T09:00:00Z'),
    ('22222222-2222-4222-8222-222222222222', 'Southgate Aid',     '2024-02-20T09:00:00Z');

INSERT INTO beneficiaries (beneficiary_id, org_id, external_ref, full_name, created_at) VALUES
    ('aaaaaaa1-0000-4000-8000-000000000001',
     '11111111-1111-4111-8111-111111111111', 'NW-0001', 'Beneficiary One',   '2024-03-01T10:00:00Z'),
    ('aaaaaaa1-0000-4000-8000-000000000002',
     '11111111-1111-4111-8111-111111111111', 'NW-0002', 'Beneficiary Two',   '2024-03-02T10:00:00Z'),
    ('bbbbbbb2-0000-4000-8000-000000000001',
     '22222222-2222-4222-8222-222222222222', 'SG-0001', 'Beneficiary Three', '2024-03-03T10:00:00Z'),
    ('bbbbbbb2-0000-4000-8000-000000000002',
     '22222222-2222-4222-8222-222222222222', 'SG-0002', 'Beneficiary Four',  '2024-03-04T10:00:00Z');

-- Rows with a NULL currency_code are historical: they predate the currency
-- field. Whether they are USD is the C04 authority question, and nothing in this
-- fixture answers it.
INSERT INTO payments
    (payment_id, org_id, beneficiary_id, amount_minor, currency_code, status, created_at) VALUES
    ('ccccccc3-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111',
     'aaaaaaa1-0000-4000-8000-000000000001',  50000, 'USD', 'settled',  '2024-04-01T12:00:00Z'),
    ('ccccccc3-0000-4000-8000-000000000002', '11111111-1111-4111-8111-111111111111',
     'aaaaaaa1-0000-4000-8000-000000000002',  75000, 'USD', 'approved', '2024-04-02T12:00:00Z'),
    ('ccccccc3-0000-4000-8000-000000000003', '11111111-1111-4111-8111-111111111111',
     'aaaaaaa1-0000-4000-8000-000000000001',  12500, NULL,  'settled',  '2023-06-10T12:00:00Z'),
    ('ddddddd4-0000-4000-8000-000000000001', '22222222-2222-4222-8222-222222222222',
     'bbbbbbb2-0000-4000-8000-000000000001', 640000, 'KES', 'settled',  '2024-04-03T12:00:00Z'),
    ('ddddddd4-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222',
     'bbbbbbb2-0000-4000-8000-000000000002',  98000, NULL,  'settled',  '2023-07-11T12:00:00Z');

INSERT INTO disbursements
    (disbursement_id, org_id, payment_id, amount_minor, currency_code, idempotency_key, settled_at)
VALUES
    ('eeeeeee5-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111',
     'ccccccc3-0000-4000-8000-000000000001',  50000, 'USD', 'nw-settle-0001', '2024-04-01T13:00:00Z'),
    ('fffffff6-0000-4000-8000-000000000001', '22222222-2222-4222-8222-222222222222',
     'ddddddd4-0000-4000-8000-000000000001', 640000, 'KES', 'sg-settle-0001', '2024-04-03T13:00:00Z');

INSERT INTO audit_events
    (org_id, actor_role, action, entity_type, entity_id, occurred_at) VALUES
    ('11111111-1111-4111-8111-111111111111', 'aidledger_app',     'payment.created',
     'payment', 'ccccccc3-0000-4000-8000-000000000001', '2024-04-01T12:00:00Z'),
    ('11111111-1111-4111-8111-111111111111', 'aidledger_service', 'disbursement.settled',
     'disbursement', 'eeeeeee5-0000-4000-8000-000000000001', '2024-04-01T13:00:00Z'),
    ('22222222-2222-4222-8222-222222222222', 'aidledger_app',     'payment.created',
     'payment', 'ddddddd4-0000-4000-8000-000000000001', '2024-04-03T12:00:00Z'),
    ('22222222-2222-4222-8222-222222222222', 'aidledger_service', 'disbursement.settled',
     'disbursement', 'fffffff6-0000-4000-8000-000000000001', '2024-04-03T13:00:00Z');
