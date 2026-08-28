-- C08 rollback.
--
-- Restores payments from the backup taken when the migration started, then drops
-- the objects the migration added. The foreign key from disbursements is dropped
-- and re-added around the restore, so the script runs cleanly.
--
-- It runs cleanly and still loses data. Every row committed between the backup
-- and this rollback is discarded, because the backup does not contain it and
-- this replaces the table wholesale. That is the difference between a rollback
-- and a restore, and it is invisible until someone actually rolls back.

BEGIN;

ALTER TABLE disbursements DROP CONSTRAINT disbursements_payment_id_fkey;

DELETE FROM payments;
INSERT INTO payments SELECT * FROM payments_backup;

ALTER TABLE payments DROP COLUMN IF EXISTS status_id;

ALTER TABLE disbursements
    ADD CONSTRAINT disbursements_payment_id_fkey
    FOREIGN KEY (payment_id) REFERENCES payments (payment_id);

DROP TABLE IF EXISTS payment_statuses;
DROP TABLE IF EXISTS payments_backup;

COMMIT;
