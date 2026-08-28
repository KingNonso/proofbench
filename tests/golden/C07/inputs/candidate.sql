-- C07 candidate migration.
--
-- Adds a NOT NULL column with a volatile default. A constant default would be
-- metadata-only since PostgreSQL 11; a volatile one forces a full table rewrite
-- and holds ACCESS EXCLUSIVE for its duration.
--
-- The final schema is exactly what was intended, and on a quiet database it
-- returns immediately. The cost only appears when something else is holding a
-- lock, which on a production table is most of the time.

BEGIN;

ALTER TABLE payments
    ADD COLUMN reconciliation_token uuid NOT NULL DEFAULT gen_random_uuid();

COMMIT;
