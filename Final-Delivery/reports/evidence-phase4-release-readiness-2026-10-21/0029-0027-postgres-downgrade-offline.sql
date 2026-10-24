BEGIN;

-- Running downgrade 0029_public_media -> 0028_certificates

DROP INDEX ix_public_media_created;

DROP TABLE public_media;

UPDATE alembic_version SET version_num='0028_certificates' WHERE alembic_version.version_num = '0029_public_media';

-- Running downgrade 0028_certificates -> 0027_ticket_checkin_account

DROP INDEX ix_certificates_event_ref;

DROP INDEX ix_certificates_full_code;

DROP INDEX ix_certificates_serial;

DROP INDEX ix_certificates_status_created;

DROP INDEX ix_certificates_account_created;

DROP TABLE certificates;

UPDATE alembic_version SET version_num='0027_ticket_checkin_account' WHERE alembic_version.version_num = '0028_certificates';

COMMIT;

