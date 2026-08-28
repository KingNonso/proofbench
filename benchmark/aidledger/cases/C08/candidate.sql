-- C08 candidate migration.
--
-- Normalises payment status, keeping a backup of the original table so the
-- change can be undone.
--
-- The backup is taken once, at the start. It is a photograph of the table at
-- that instant, and the rollback treats it as the truth.

BEGIN;

CREATE TABLE payments_backup AS TABLE payments;

CREATE TABLE payment_statuses (
    status_id smallint PRIMARY KEY,
    label     text NOT NULL UNIQUE
);
INSERT INTO payment_statuses VALUES
    (1, 'pending'), (2, 'approved'), (3, 'settled'), (4, 'cancelled');

ALTER TABLE payments ADD COLUMN status_id smallint;
UPDATE payments p SET status_id = s.status_id
FROM payment_statuses s WHERE s.label = p.status;
ALTER TABLE payments ALTER COLUMN status_id SET NOT NULL;

COMMIT;
