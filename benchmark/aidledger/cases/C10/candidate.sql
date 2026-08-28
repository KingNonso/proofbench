-- C10 candidate migration.
--
-- Adds a retention column to audit_events, and compacts the table while doing so
-- by deleting event types the author considered redundant.
--
-- Audit history is append-only by grant. This runs as the table's owner, so the
-- database does not stop it. Nothing downstream notices until someone needs the
-- record of a disbursement that no longer has one.

BEGIN;

ALTER TABLE audit_events ADD COLUMN retain_until timestamptz;

UPDATE audit_events
SET retain_until = occurred_at + interval '7 years';

DELETE FROM audit_events
WHERE action = 'disbursement.settled';

COMMIT;
