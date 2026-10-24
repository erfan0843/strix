BEGIN;

-- Running upgrade 0027_ticket_checkin_account -> 0028_certificates

CREATE TABLE certificates (
    id VARCHAR(36) NOT NULL, 
    account_id VARCHAR(36) NOT NULL, 
    bale_user_id VARCHAR(40) NOT NULL, 
    external_key VARCHAR(120) NOT NULL, 
    source VARCHAR(16) DEFAULT 'bot' NOT NULL, 
    source_id VARCHAR(36) DEFAULT '' NOT NULL, 
    legacy_id INTEGER, 
    status VARCHAR(16) DEFAULT 'issued' NOT NULL, 
    serial VARCHAR(80) DEFAULT '' NOT NULL, 
    full_code VARCHAR(120) DEFAULT '' NOT NULL, 
    doc_no VARCHAR(80) DEFAULT '' NOT NULL, 
    person_code VARCHAR(80) DEFAULT '' NOT NULL, 
    kind VARCHAR(16) DEFAULT 'event' NOT NULL, 
    event_ref VARCHAR(40) DEFAULT '' NOT NULL, 
    event_title VARCHAR(200) DEFAULT '' NOT NULL, 
    title VARCHAR(200) DEFAULT '' NOT NULL, 
    holder_name VARCHAR(160) DEFAULT '' NOT NULL, 
    issued_on VARCHAR(32) DEFAULT '' NOT NULL, 
    expires_on VARCHAR(32) DEFAULT '' NOT NULL, 
    issued_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    issued_by_bale_user_id VARCHAR(40) DEFAULT '' NOT NULL, 
    verify_count INTEGER DEFAULT '0' NOT NULL, 
    file_id VARCHAR(36), 
    preview_file_id VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_certificates_status CHECK (status IN ('issued', 'revoked')), 
    CONSTRAINT ck_certificates_source CHECK (source IN ('bot', 'bot_legacy')), 
    CONSTRAINT uq_certificates_external_key UNIQUE (external_key), 
    FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE, 
    FOREIGN KEY(file_id) REFERENCES private_files (id) ON DELETE SET NULL, 
    FOREIGN KEY(preview_file_id) REFERENCES private_files (id) ON DELETE SET NULL
);

CREATE INDEX ix_certificates_account_created ON certificates (account_id, created_at);

CREATE INDEX ix_certificates_status_created ON certificates (status, created_at);

CREATE INDEX ix_certificates_serial ON certificates (serial);

CREATE INDEX ix_certificates_full_code ON certificates (full_code);

CREATE INDEX ix_certificates_event_ref ON certificates (event_ref);

UPDATE alembic_version SET version_num='0028_certificates' WHERE alembic_version.version_num = '0027_ticket_checkin_account';

-- Running upgrade 0028_certificates -> 0029_public_media

CREATE TABLE public_media (
    id VARCHAR(36) NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    content_type VARCHAR(80) NOT NULL, 
    content_size INTEGER NOT NULL, 
    width INTEGER DEFAULT '0' NOT NULL, 
    height INTEGER DEFAULT '0' NOT NULL, 
    file_name VARCHAR(120) DEFAULT '' NOT NULL, 
    uploaded_by_kind VARCHAR(16) DEFAULT '' NOT NULL, 
    uploaded_by_id VARCHAR(64) DEFAULT '' NOT NULL, 
    content BYTEA NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_public_media_size CHECK (content_size BETWEEN 1 AND 3145728), 
    CONSTRAINT ck_public_media_content_type CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')), 
    CONSTRAINT uq_public_media_hash UNIQUE (content_hash)
);

CREATE INDEX ix_public_media_created ON public_media (created_at);

UPDATE alembic_version SET version_num='0029_public_media' WHERE alembic_version.version_num = '0028_certificates';

COMMIT;

