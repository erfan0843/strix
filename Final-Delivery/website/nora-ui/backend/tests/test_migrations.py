from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = BACKEND_ROOT.parent
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))


def test_public_response_and_cooperation_migrations_upgrade_and_downgrade(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {
            "forms", "form_fields", "form_response_drafts", "form_responses",
            "public_write_throttles", "cooperation_requests", "site_content",
            "accounts", "platform_identities", "account_sessions", "miniapp_auth_replays",
            "phone_otp_challenges", "account_roles", "manager_credentials", "admin_tasks", "user_notifications", "private_files",
            "form_receipt_uploads",
        } <= tables
        assert {
            "account_id", "answers", "companions", "form_version", "token_hash", "has_unsaved_changes", "bot_bale_user_id"
        } <= {column["name"] for column in inspector.get_columns("form_response_drafts")}
        assert {
            "answers", "companions", "form_snapshot", "status", "draft_id", "ticket_serial",
            "registrant_name", "registrant_mobile", "added_by_response_id", "companion_index", "added_by_name",
            "ticket_claim_nonce_hash", "ticket_claim_expires_at", "ticket_claimed_by_bale_user_id",
            "ticket_claimed_at", "ticket_checked_in_at", "ticket_checked_in_by_bale_user_id",
        } <= {column["name"] for column in inspector.get_columns("form_responses")}
        assert "uq_form_responses_draft" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("form_responses")
        }
        response_indexes = {
            index["name"]: index for index in inspector.get_indexes("form_responses")
        }
        assert bool(response_indexes["uq_form_responses_ticket_serial"]["unique"])
        assert bool(response_indexes["uq_form_responses_ticket_claim_nonce"]["unique"])
        assert "ix_form_responses_ticket_claim_expiry" in response_indexes
        assert "ix_form_responses_added_by_response" in response_indexes
        assert "fk_form_responses_added_by_response" in {
            constraint["name"] for constraint in inspector.get_foreign_keys("form_responses")
        }
        assert "uq_form_responses_added_by_index" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("form_responses")
        }
        assert {"response_id", "content_hash", "note"} <= {
            column["name"] for column in inspector.get_columns("form_receipt_uploads")
        }
        assert "ix_public_write_throttles_window" in {
            index["name"] for index in inspector.get_indexes("public_write_throttles")
        }
        assert "ix_response_drafts_bot_bale_user" in {
            index["name"] for index in inspector.get_indexes("form_response_drafts")
        }
        assert "ix_response_drafts_account_updated" in {
            index["name"] for index in inspector.get_indexes("form_response_drafts")
        }
        assert "fk_response_drafts_account" in {
            constraint["name"] for constraint in inspector.get_foreign_keys("form_response_drafts")
        }
        assert {"provider", "provider_user_id", "account_id"} <= {
            column["name"] for column in inspector.get_columns("platform_identities")
        }
        assert "uq_platform_identity_provider_user" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("platform_identities")
        }
        assert "uq_platform_identity_account_provider" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("platform_identities")
        }
        assert {"account_id", "token_hash", "csrf_hash", "expires_at", "revoked_at"} <= {
            column["name"] for column in inspector.get_columns("account_sessions")
        }
        assert "uq_account_sessions_token_hash" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("account_sessions")
        }
        assert "auth_provider" in {
            column["name"] for column in inspector.get_columns("account_sessions")
        }
        assert {"phone_hash", "code_hash", "expires_at", "attempts", "max_attempts", "consumed_at"} <= {
            column["name"] for column in inspector.get_columns("phone_otp_challenges")
        }
        assert {"ck_phone_otp_attempts_nonnegative", "ck_phone_otp_max_attempts"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("phone_otp_challenges")
        }
        assert {"ix_phone_otp_phone_created", "ix_phone_otp_expiry"} <= {
            index["name"] for index in inspector.get_indexes("phone_otp_challenges")
        }
        assert "ix_miniapp_auth_replays_expiry" in {
            index["name"] for index in inspector.get_indexes("miniapp_auth_replays")
        }
        assert {"account_id", "role", "assigned_by", "created_at", "updated_at"} <= {
            column["name"] for column in inspector.get_columns("account_roles")
        }
        assert "ck_account_roles_assignable_role" in {
            constraint["name"] for constraint in inspector.get_check_constraints("account_roles")
        }
        assert {"account_id", "username_key", "password_hash", "created_at", "updated_at"} <= {
            column["name"] for column in inspector.get_columns("manager_credentials")
        }
        assert "uq_manager_credentials_username" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("manager_credentials")
        }
        assert {"account_id", "bale_user_id", "kind", "payload", "status", "idempotency_key", "create_hash", "version", "projection_status", "projection_attempts"} <= {
            column["name"] for column in inspector.get_columns("admin_tasks")
        }
        assert "uq_admin_tasks_idempotency" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("admin_tasks")
        }
        assert {"ck_admin_tasks_status", "ck_admin_tasks_projection_status"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("admin_tasks")
        }
        assert {"account_id", "source_task_id", "title", "body", "file_refs", "delivery_status", "read_at"} <= {
            column["name"] for column in inspector.get_columns("user_notifications")
        }
        assert "uq_user_notifications_task_kind" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("user_notifications")
        }
        assert {"id", "account_id", "task_id", "bale_user_id", "content_hash", "content_type", "content_size", "content"} <= {
            column["name"] for column in inspector.get_columns("private_files")
        }
        assert "uq_private_files_idempotency" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("private_files")
        }
        assert {"id", "form_id", "draft_id", "response_id", "method", "status", "amount", "currency", "selection", "invoice_payload", "transaction_id", "provider_charge_id"} <= {
            column["name"] for column in inspector.get_columns("form_payments")
        }
        assert {"uq_form_payments_invoice_payload", "uq_form_payments_idempotency", "uq_form_payments_transaction", "uq_form_payments_provider_charge", "uq_form_payments_response"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("form_payments")
        }
        assert {"id", "payment_id", "transaction_id", "provider_charge_id", "amount", "currency", "payer_bale_user_id", "status"} <= {
            column["name"] for column in inspector.get_columns("form_payment_transactions")
        }
        assert {"uq_form_payment_transactions_transaction", "uq_form_payment_transactions_provider_charge"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("form_payment_transactions")
        }
        assert {"service_checks", "admin_audit_events"} <= set(inspect(engine).get_table_names())
        assert {"id", "created_at", "actor_kind", "actor_id", "actor_role", "action", "target_type", "target_id", "outcome", "details"} <= {
            column["name"] for column in inspector.get_columns("admin_audit_events")
        }
        assert {"ix_admin_audit_events_created", "ix_admin_audit_events_action_created", "ix_admin_audit_events_target"} <= {
            index["name"] for index in inspector.get_indexes("admin_audit_events")
        }
        assert "ticket_checked_in_by_account_id" in {
            column["name"] for column in inspector.get_columns("form_responses")
        }
        assert {"id", "account_id", "bale_user_id", "external_key", "source", "legacy_id", "status", "serial", "full_code", "file_id", "preview_file_id"} <= {
            column["name"] for column in inspector.get_columns("certificates")
        }
        assert "uq_certificates_external_key" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("certificates")
        }
        assert {"ck_certificates_status", "ck_certificates_source"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("certificates")
        }
        assert {"id", "content_hash", "content_type", "content_size", "width", "height", "file_name", "uploaded_by_kind", "content"} <= {
            column["name"] for column in inspector.get_columns("public_media")
        }
        assert "uq_public_media_hash" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("public_media")
        }
        assert {"id", "account_id", "bale_user_id", "external_key", "source_id", "ledger_id", "delta", "balance_after",
                "entry_type", "source", "ref_key", "reason", "actor_kind", "reverses_external_key", "bot_created_at"} <= {
            column["name"] for column in inspector.get_columns("club_points_entries")
        }
        assert {"uq_club_points_entries_external_key", "uq_club_points_entries_source_ledger"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("club_points_entries")
        }
        assert {"ck_club_points_entries_entry_type", "ck_club_points_entries_actor_kind", "ck_club_points_entries_delta"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("club_points_entries")
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "forms" not in tables
        assert not {
            "form_response_drafts", "form_responses", "public_write_throttles",
            "cooperation_requests", "site_content", "accounts", "platform_identities",
            "account_sessions", "miniapp_auth_replays", "phone_otp_challenges", "account_roles", "manager_credentials", "admin_tasks",
            "user_notifications", "private_files", "form_receipt_uploads",
            "form_payments", "form_payment_transactions", "service_checks", "admin_audit_events", "certificates", "public_media",
            "club_points_entries",
        } & tables
    finally:
        engine.dispose()


def test_certificates_migration_with_existing_data_round_trip(tmp_path, monkeypatch):
    """0028 on a database that already holds accounts/identities/files: upgrade, downgrade one step, upgrade again."""
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0027_ticket_checkin_account")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-1')"))
            connection.execute(text(
                "INSERT INTO platform_identities (id, account_id, provider, provider_user_id) "
                "VALUES ('pid-1', 'acc-legacy-1', 'bale', '910001')"
            ))
        assert "certificates" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO certificates (id, account_id, bale_user_id, external_key, source, legacy_id, status, serial) "
                "VALUES ('cert-1', 'acc-legacy-1', '910001', 'src:1', 'bot_legacy', 1, 'issued', 'N-1')"
            ))
            assert connection.scalar(text("SELECT count(*) FROM certificates")) == 1
            assert connection.scalar(text("SELECT count(*) FROM accounts")) == 1
    finally:
        engine.dispose()

    command.downgrade(config, "0027_ticket_checkin_account")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "certificates" not in tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM accounts")) == 1
            assert connection.scalar(text("SELECT count(*) FROM platform_identities")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0027_ticket_checkin_account"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM certificates")) == 0
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_public_media_migration_with_existing_data_round_trip(tmp_path, monkeypatch):
    """0029 on a database that already holds content and certificates: upgrade, downgrade one step, upgrade again."""
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-media.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0028_certificates")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-2')"))
            connection.execute(text(
                "INSERT INTO site_content (id, content, version) VALUES ('public', '{\"events\": []}', 3)"
            ))
        assert "public_media" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO public_media (id, content_hash, content_type, content_size, content) "
                "VALUES ('media-1', 'a' * 64, 'image/png', 4, x'89504e47')"
            ))
            assert connection.scalar(text("SELECT count(*) FROM public_media")) == 1
            assert connection.scalar(text("SELECT version FROM site_content WHERE id='public'")) == 3
    finally:
        engine.dispose()

    command.downgrade(config, "0028_certificates")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "public_media" not in tables
        assert "certificates" in tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM accounts")) == 1
            assert connection.scalar(text("SELECT version FROM site_content WHERE id='public'")) == 3
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0028_certificates"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM public_media")) == 0
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_club_points_migration_with_existing_data_round_trip(tmp_path, monkeypatch):
    """0030 on a database that already holds accounts, certificates and media: upgrade, downgrade one step, upgrade again."""
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-points.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0029_public_media")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-3')"))
            connection.execute(text(
                "INSERT INTO certificates (id, account_id, bale_user_id, external_key, source, legacy_id, status, serial) "
                "VALUES ('cert-3', 'acc-legacy-3', '910001', 'src:3', 'bot_legacy', 3, 'issued', 'N-3')"
            ))
        assert "club_points_entries" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO club_points_entries (id, account_id, bale_user_id, external_key, source_id, ledger_id, delta, "
                "balance_after, entry_type, source, ref_key) VALUES ('pt-1', 'acc-legacy-3', '910001', "
                "'0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b:1', '0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b', 1, 120, 120, "
                "'opening_balance', 'legacy_counter', 'opening:910001')"
            ))
            assert connection.scalar(text("SELECT count(*) FROM club_points_entries")) == 1
            assert connection.scalar(text("SELECT count(*) FROM certificates")) == 1
    finally:
        engine.dispose()

    command.downgrade(config, "0029_public_media")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "club_points_entries" not in tables
        assert {"certificates", "public_media"} <= tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM accounts")) == 1
            assert connection.scalar(text("SELECT count(*) FROM certificates")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0029_public_media"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM club_points_entries")) == 0
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_event_interaction_migration_with_existing_data_round_trip(tmp_path, monkeypatch):
    """0031 on a database that already holds accounts, notifications and points: upgrade, downgrade one step, upgrade again.

    Existing rows survive both directions; the four new tables carry their constraints
    (status/access/kind checks, one review per account+event, dedupe per question).
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-interaction.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0030_club_points_entries")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-4')"))
            connection.execute(text(
                "INSERT INTO user_notifications (id, account_id, bale_user_id, kind, title, body, file_refs, delivery_status, delivery_attempts) "
                "VALUES ('ntf-4', 'acc-legacy-4', '910004', 'legacy', 'عنوان', 'متن', '[]', 'delivered', 1)"
            ))
        assert not {"event_resources", "event_questions", "event_reviews", "event_content_reports"} & set(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"event_resources", "event_questions", "event_reviews", "event_content_reports"} <= tables
        assert {"id", "event_id", "kind", "access", "status", "publish_at", "content", "content_hash", "removed_at"} <= {
            column["name"] for column in inspector.get_columns("event_resources")
        }
        assert {"ck_event_resources_kind", "ck_event_resources_access", "ck_event_resources_status", "ck_event_resources_size"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("event_resources")
        }
        assert {"uq_event_questions_dedupe"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("event_questions")
        }
        assert {"uq_event_reviews_account_event"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("event_reviews")
        }
        assert {"uq_event_content_reports_once"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("event_content_reports")
        }
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO event_questions (id, event_id, account_id, body, body_hash, status, notification_id) "
                "VALUES ('q-1', 'ev-legacy', 'acc-legacy-4', 'پرسش', 'h1', 'published', 'ntf-4')"
            ))
            connection.execute(text(
                "INSERT INTO event_reviews (id, event_id, account_id, body, status, verified_attendee) "
                "VALUES ('r-1', 'ev-legacy', 'acc-legacy-4', 'دیدگاه', 'pending', 1)"
            ))
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind) "
                "VALUES ('res-1', 'ev-legacy', 'جزوه', 'published', 'registered', 'file')"
            ))
            assert connection.scalar(text("SELECT count(*) FROM user_notifications")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()

    command.downgrade(config, "0030_club_points_entries")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert not {"event_resources", "event_questions", "event_reviews", "event_content_reports"} & tables
        assert {"user_notifications", "club_points_entries", "certificates"} <= tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM accounts")) == 1
            assert connection.scalar(text("SELECT count(*) FROM user_notifications")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0030_club_points_entries"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM event_questions")) == 0
            assert connection.scalar(text("SELECT count(*) FROM user_notifications")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_recorded_content_migration_with_existing_data_round_trip(tmp_path, monkeypatch):
    """0032 on a database that already holds phase-8 rows: upgrade, downgrade one step, upgrade again.

    Existing resources/questions/reviews survive, the four new tables carry their
    constraints (status/method/source checks, one access row per account+product,
    unique provider ids), ``event_resources`` accepts ``access='purchased'`` and
    ``delivery='view'`` only after the upgrade, and the downgrade folds purchased
    files to ``staff`` (never public) instead of deleting them.
    """
    from sqlalchemy.exc import IntegrityError

    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-recordings.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0031_event_interaction")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-5')"))
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind) "
                "VALUES ('res-old', 'ev-held', 'جزوه', 'published', 'registered', 'file')"
            ))
            connection.execute(text(
                "INSERT INTO event_questions (id, event_id, account_id, body, body_hash, status) "
                "VALUES ('q-old', 'ev-held', 'acc-legacy-5', 'پرسش قدیمی', 'h-old', 'published')"
            ))
            connection.execute(text(
                "INSERT INTO event_reviews (id, event_id, account_id, body, status, verified_attendee) "
                "VALUES ('r-old', 'ev-held', 'acc-legacy-5', 'دیدگاه قدیمی', 'published', 1)"
            ))
        tables = set(inspect(engine).get_table_names())
        assert not {"event_recordings", "recording_sessions", "recording_orders", "recording_access"} & tables
        assert "delivery" not in {column["name"] for column in inspect(engine).get_columns("event_resources")}
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"event_recordings", "recording_sessions", "recording_orders", "recording_access"} <= tables
        assert {"session_id", "delivery"} <= {column["name"] for column in inspector.get_columns("event_resources")}
        assert "session_id" in {column["name"] for column in inspector.get_columns("event_questions")}
        assert "badge" in {column["name"] for column in inspector.get_columns("event_reviews")}
        assert {"ck_event_resources_access", "ck_event_resources_delivery"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("event_resources")
        }
        assert {"ck_event_recordings_status", "ck_event_recordings_price", "ck_event_recordings_access_days"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("event_recordings")
        }
        assert {"uq_event_recordings_event"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("event_recordings")
        }
        assert {"ck_recording_orders_method", "ck_recording_orders_status", "ck_recording_orders_amount"} <= {
            constraint["name"] for constraint in inspector.get_check_constraints("recording_orders")
        }
        assert {
            "uq_recording_orders_idempotency", "uq_recording_orders_invoice_payload",
            "uq_recording_orders_transaction", "uq_recording_orders_provider_charge",
        } <= {constraint["name"] for constraint in inspector.get_unique_constraints("recording_orders")}
        assert {"uq_recording_access_account"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("recording_access")
        }
        with engine.begin() as connection:
            # Old rows kept, new columns defaulted.
            assert connection.scalar(text("SELECT delivery FROM event_resources WHERE id = 'res-old'")) == "download"
            assert connection.scalar(text("SELECT badge FROM event_reviews WHERE id = 'r-old'")) == ""
            connection.execute(text(
                "INSERT INTO event_recordings (id, event_id, status, title, faq, price) "
                "VALUES ('rec-1', 'ev-held', 'draft', 'نسخهٔ ضبط‌شده', '[]', 1500000)"
            ))
            connection.execute(text(
                "INSERT INTO recording_sessions (id, recording_id, title, status, sort_order) "
                "VALUES ('ses-1', 'rec-1', 'جلسهٔ اول', 'published', 1)"
            ))
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, session_id, delivery) "
                "VALUES ('res-new', 'ev-held', 'ویدیوی جلسه', 'published', 'purchased', 'file', 'ses-1', 'view')"
            ))
            connection.execute(text(
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key) "
                "VALUES ('ord-1', 'rec-1', 'acc-legacy-5', 'card_transfer', 'awaiting_receipt', 1500000, 'idem-1')"
            ))
            connection.execute(text(
                "INSERT INTO recording_access (id, recording_id, account_id, source, status, order_id) "
                "VALUES ('acc-r-1', 'rec-1', 'acc-legacy-5', 'purchase', 'active', 'ord-1')"
            ))
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
        with engine.connect() as connection:
            for statement in (
                # one product per event
                "INSERT INTO event_recordings (id, event_id, status, title, faq) VALUES ('rec-dup', 'ev-held', 'draft', 'x', '[]')",
                # unknown state / delivery / method / source
                "INSERT INTO event_recordings (id, event_id, status, title, faq) VALUES ('rec-bad', 'ev-2', 'live', 'x', '[]')",
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, delivery) "
                "VALUES ('res-bad', 'ev-held', 'x', 'published', 'purchased', 'file', 'stream')",
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key) "
                "VALUES ('ord-bad', 'rec-1', 'acc-legacy-5', 'cash', 'pending', 1, 'idem-2')",
                # replayed idempotency key / duplicate access row
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key) "
                "VALUES ('ord-dup', 'rec-1', 'acc-legacy-5', 'card_transfer', 'pending', 1, 'idem-1')",
                "INSERT INTO recording_access (id, recording_id, account_id, source, status) "
                "VALUES ('acc-r-dup', 'rec-1', 'acc-legacy-5', 'granted', 'active')",
            ):
                transaction = connection.begin()
                try:
                    with pytest.raises(IntegrityError):
                        connection.execute(text(statement))
                finally:
                    transaction.rollback()
    finally:
        engine.dispose()

    command.downgrade(config, "0031_event_interaction")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert not {"event_recordings", "recording_sessions", "recording_orders", "recording_access"} & tables
        assert {"event_resources", "event_questions", "event_reviews", "user_notifications"} <= tables
        assert "delivery" not in {column["name"] for column in inspector.get_columns("event_resources")}
        assert "badge" not in {column["name"] for column in inspector.get_columns("event_reviews")}
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM event_resources")) == 2
            assert connection.scalar(text("SELECT access FROM event_resources WHERE id = 'res-new'")) == "staff"
            assert connection.scalar(text("SELECT access FROM event_resources WHERE id = 'res-old'")) == "registered"
            assert connection.scalar(text("SELECT count(*) FROM event_questions")) == 1
            assert connection.scalar(text("SELECT count(*) FROM event_reviews")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM event_recordings")) == 0
            assert connection.scalar(text("SELECT count(*) FROM event_resources")) == 2
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_form_aligned_store_migration_round_trip(tmp_path, monkeypatch):
    """0033 on a database that already holds phase-9 rows: upgrade, downgrade one step, upgrade again.

    Existing forms keep working with ``purpose='registration'`` (the pre-9.1
    behaviour), a purchase form can be tied to a product, the ledger row can be
    tied to one response/payment at most once, ``certificate_policy`` only accepts
    ``none``/``manual`` and ``kind`` accepts the two embed providers only after
    the upgrade. The downgrade folds embeds to plain links instead of deleting them.
    """
    from sqlalchemy.exc import IntegrityError

    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-store.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0032_recorded_content")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-legacy-6')"))
            connection.execute(text(
                "INSERT INTO forms (id, owner_id, title, model, need, status, settings, version) "
                "VALUES ('form-old', 'owner-1', 'ثبت‌نام قدیمی', 'registration', 'reg', 'published', '{}', 1)"
            ))
            connection.execute(text(
                "INSERT INTO event_recordings (id, event_id, status, title, faq, price) "
                "VALUES ('rec-1', 'ev-held', 'draft', 'نسخهٔ ضبط‌شده', '[]', 1500000)"
            ))
            connection.execute(text(
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key) "
                "VALUES ('ord-old', 'rec-1', 'acc-legacy-6', 'card_transfer', 'paid_manual', 1500000, 'idem-old')"
            ))
        columns = {column["name"] for column in inspect(engine).get_columns("forms")}
        assert not {"purpose", "recording_id"} & columns
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(IntegrityError):
                    connection.execute(text(
                        "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                        "VALUES ('res-yt-early', 'ev-held', 'x', 'published', 'purchased', 'youtube', 'https://youtu.be/dQw4w9WgXcQ')"
                    ))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {"purpose", "recording_id"} <= {column["name"] for column in inspector.get_columns("forms")}
        assert "certificate_policy" in {column["name"] for column in inspector.get_columns("event_recordings")}
        assert {"form_response_id", "form_payment_id"} <= {
            column["name"] for column in inspector.get_columns("recording_orders")
        }
        assert {"uq_recording_orders_form_response", "uq_recording_orders_form_payment"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("recording_orders")
        }
        assert {"ck_forms_purpose"} <= {c["name"] for c in inspector.get_check_constraints("forms")}
        assert {"ck_event_recordings_certificate_policy"} <= {
            c["name"] for c in inspector.get_check_constraints("event_recordings")
        }
        with engine.begin() as connection:
            # Old rows keep the pre-9.1 behaviour by default.
            assert connection.scalar(text("SELECT purpose FROM forms WHERE id = 'form-old'")) == "registration"
            assert connection.scalar(text("SELECT recording_id FROM forms WHERE id = 'form-old'")) is None
            assert connection.scalar(text("SELECT certificate_policy FROM event_recordings WHERE id = 'rec-1'")) == "none"
            assert connection.scalar(text("SELECT form_response_id FROM recording_orders WHERE id = 'ord-old'")) is None
            connection.execute(text(
                "INSERT INTO forms (id, owner_id, title, model, need, status, settings, version, purpose, recording_id, event_id) "
                "VALUES ('form-buy', 'owner-1', 'خرید دسترسی', 'order', 'reg', 'published', '{}', 1, 'recording_access', 'rec-1', 'ev-held')"
            ))
            connection.execute(text(
                "INSERT INTO form_response_drafts (id, form_id, form_version, token_hash, answers, companions, expires_at) "
                "VALUES ('draft-1', 'form-buy', 1, 'hash-1', '{}', '[]', '2030-01-01 00:00:00')"
            ))
            connection.execute(text(
                "INSERT INTO form_responses (id, form_id, draft_id, form_version, status, answers, companions, form_snapshot) "
                "VALUES ('resp-1', 'form-buy', 'draft-1', 1, 'accepted', '{}', '[]', '{}')"
            ))
            connection.execute(text(
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key, form_response_id) "
                "VALUES ('ord-form', 'rec-1', 'acc-legacy-6', 'card_transfer', 'paid_manual', 1500000, 'idem-form', 'resp-1')"
            ))
            connection.execute(text(
                "UPDATE event_recordings SET certificate_policy = 'manual' WHERE id = 'rec-1'"
            ))
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                "VALUES ('res-yt', 'ev-held', 'ویدیوی یوتیوب', 'published', 'purchased', 'youtube', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')"
            ))
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                "VALUES ('res-ap', 'ev-held', 'ویدیوی آپارات', 'published', 'purchased', 'aparat', 'https://www.aparat.com/v/abc12')"
            ))
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
        with engine.connect() as connection:
            for statement in (
                "UPDATE forms SET purpose = 'shop' WHERE id = 'form-buy'",
                "UPDATE event_recordings SET certificate_policy = 'auto' WHERE id = 'rec-1'",
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                "VALUES ('res-bad', 'ev-held', 'x', 'published', 'purchased', 'vimeo', 'https://vimeo.com/1')",
                # one ledger row per form response
                "INSERT INTO recording_orders (id, recording_id, account_id, method, status, amount, idempotency_key, form_response_id) "
                "VALUES ('ord-dup', 'rec-1', 'acc-legacy-6', 'card_transfer', 'paid_manual', 1500000, 'idem-dup', 'resp-1')",
            ):
                transaction = connection.begin()
                try:
                    with pytest.raises(IntegrityError):
                        connection.execute(text(statement))
                finally:
                    transaction.rollback()
    finally:
        engine.dispose()

    command.downgrade(config, "0032_recorded_content")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert not {"purpose", "recording_id"} & {column["name"] for column in inspector.get_columns("forms")}
        assert "certificate_policy" not in {column["name"] for column in inspector.get_columns("event_recordings")}
        assert not {"form_response_id", "form_payment_id"} & {
            column["name"] for column in inspector.get_columns("recording_orders")
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM forms")) == 2
            assert connection.scalar(text("SELECT count(*) FROM recording_orders")) == 2
            assert connection.scalar(text("SELECT kind FROM event_resources WHERE id = 'res-yt'")) == "link"
            assert connection.scalar(text("SELECT link_url FROM event_resources WHERE id = 'res-ap'")) == "https://www.aparat.com/v/abc12"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0032_recorded_content"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT purpose FROM forms WHERE id = 'form-buy'")) == "registration"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()


def test_private_storage_migration_round_trip(tmp_path, monkeypatch):
    """0034 on a database that already holds phase-9.3 rows: upgrade, downgrade one step, upgrade again.

    Existing inline resources keep working untouched (``storage_key`` NULL, 8 MiB check still
    enforced for them); a row pointing at the private store may exceed 8 MiB; the downgrade
    refuses while such a row exists (nothing is deleted silently) and succeeds once it is gone,
    restoring the strict check.
    """
    from sqlalchemy.exc import IntegrityError

    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-storage.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0033_form_aligned_store")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, content, content_size, content_type) "
                "VALUES ('res-inline', 'ev-held', 'جزوه', 'published', 'purchased', 'file', X'255044462D', 5, 'application/pdf')"
            ))
        assert "storage_key" not in {c["name"] for c in inspect(engine).get_columns("event_resources")}
    finally:
        engine.dispose()

    command.upgrade(config, "0034_private_storage")
    engine = create_engine(database_url)
    try:
        assert "storage_key" in {c["name"] for c in inspect(engine).get_columns("event_resources")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0034_private_storage"
            assert connection.scalar(text("SELECT storage_key FROM event_resources WHERE id = 'res-inline'")) is None
            assert connection.scalar(text("SELECT content_size FROM event_resources WHERE id = 'res-inline'")) == 5
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, content_size, content_type, storage_key) "
                "VALUES ('res-disk', 'ev-held', 'ویدیو', 'published', 'purchased', 'file', 734003200, 'video/mp4', "
                "'2026/10/0123456789abcdef0123456789abcdef')"
            ))
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(IntegrityError):  # inline rows are still capped at 8 MiB
                    connection.execute(text("UPDATE event_resources SET content_size = 9000000 WHERE id = 'res-inline'"))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="exceed 8 MiB"):
        command.downgrade(config, "0033_form_aligned_store")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0034_private_storage"
            assert connection.scalar(text("SELECT COUNT(*) FROM event_resources")) == 2  # refused, nothing removed
            connection.execute(text("DELETE FROM event_resources WHERE id = 'res-disk'"))  # the operator's explicit decision
    finally:
        engine.dispose()

    command.downgrade(config, "0033_form_aligned_store")
    engine = create_engine(database_url)
    try:
        assert "storage_key" not in {c["name"] for c in inspect(engine).get_columns("event_resources")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT content_size FROM event_resources WHERE id = 'res-inline'")) == 5
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(IntegrityError):
                    connection.execute(text(
                        "INSERT INTO event_resources (id, event_id, title, status, access, kind, content_size) "
                        "VALUES ('res-big', 'ev-held', 'x', 'draft', 'purchased', 'file', 9000000)"
                    ))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
            assert connection.scalar(text("SELECT storage_key FROM event_resources WHERE id = 'res-inline'")) is None
    finally:
        engine.dispose()


def test_upload_sessions_migration_round_trip(tmp_path, monkeypatch):
    """0036 on a database that already holds phase-9.4 rows: upgrade, downgrade one step, upgrade again.

    Existing resources keep working untouched (``announced_at`` NULL = never announced); upload
    sessions enforce their status/bytes checks; ``system_markers`` holds JSON; the downgrade drops
    only the new objects and never touches ``event_resources`` rows.
    """
    from sqlalchemy.exc import IntegrityError

    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-upload.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0035_notification_dedupe")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO event_resources (id, event_id, title, status, access, kind, content_size, content_type, storage_key) "
                "VALUES ('res-disk', 'ev-held', 'ویدیو', 'published', 'purchased', 'file', 734003200, 'video/mp4', "
                "'2026/10/0123456789abcdef0123456789abcdef')"
            ))
        tables = set(inspect(engine).get_table_names())
        assert not {"upload_sessions", "system_markers"} & tables
        assert "announced_at" not in {c["name"] for c in inspect(engine).get_columns("event_resources")}
    finally:
        engine.dispose()

    command.upgrade(config, "0036_upload_sessions")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {"upload_sessions", "system_markers"} <= set(inspector.get_table_names())
        assert "announced_at" in {c["name"] for c in inspector.get_columns("event_resources")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0036_upload_sessions"
            assert connection.scalar(text("SELECT announced_at FROM event_resources WHERE id = 'res-disk'")) is None
            connection.execute(text(
                "INSERT INTO upload_sessions (id, resource_id, event_id, owner_kind, owner_id, part_id, expected_size, expires_at) "
                "VALUES ('up-1', 'res-disk', 'ev-held', 'owner', 'owner-1', '0123456789abcdef0123456789abcdef', 1000, '2026-10-23 00:00:00')"
            ))
            connection.execute(text("INSERT INTO system_markers (key, value) VALUES ('storage_verify', '{\"ok\": true}')"))
        with engine.connect() as connection:
            for statement in (
                "UPDATE upload_sessions SET status = 'done' WHERE id = 'up-1'",
                "UPDATE upload_sessions SET received_bytes = 2000 WHERE id = 'up-1'",
                "INSERT INTO upload_sessions (id, resource_id, event_id, owner_kind, owner_id, part_id, expected_size, expires_at) "
                "VALUES ('up-2', 'res-disk', 'ev-held', 'owner', 'owner-1', '0123456789abcdef0123456789abcdef', 10, '2026-10-23 00:00:00')",
            ):
                transaction = connection.begin()
                try:
                    with pytest.raises(IntegrityError):
                        connection.execute(text(statement))
                finally:
                    transaction.rollback()
    finally:
        engine.dispose()

    command.downgrade(config, "0035_notification_dedupe")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert not {"upload_sessions", "system_markers"} & set(inspector.get_table_names())
        assert "announced_at" not in {c["name"] for c in inspector.get_columns("event_resources")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT content_size FROM event_resources WHERE id = 'res-disk'")) == 734003200
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
            assert connection.scalar(text("SELECT COUNT(*) FROM upload_sessions")) == 0
    finally:
        engine.dispose()


def test_account_status_migration_round_trip(tmp_path, monkeypatch):
    """0037 on a database that already holds accounts: upgrade, downgrade one step, upgrade again.

    Every existing account becomes ``active`` with empty reason/note (server defaults, no row
    rewritten); a blocked row survives a downgrade only as the audit trail (columns are dropped,
    the account row itself is never deleted); re-upgrade restores the defaults.
    """
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-status.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0036_upload_sessions")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-old-1')"))
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-old-2')"))
        assert "status" not in {c["name"] for c in inspect(engine).get_columns("accounts")}
    finally:
        engine.dispose()

    command.upgrade(config, "0037_account_status")
    engine = create_engine(database_url)
    try:
        columns = {c["name"] for c in inspect(engine).get_columns("accounts")}
        assert {"status", "blocked_reason", "blocked_at", "blocked_by", "internal_note", "note_updated_at", "note_updated_by"} <= columns
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0037_account_status"
            rows = connection.execute(text("SELECT id, status, blocked_reason, internal_note FROM accounts ORDER BY id")).all()
            assert [tuple(row) for row in rows] == [("acc-old-1", "active", "", ""), ("acc-old-2", "active", "", "")]
            connection.execute(text(
                "UPDATE accounts SET status = 'blocked', blocked_reason = 'دلیل آزمایشی', blocked_by = 'owner-1', "
                "internal_note = 'یادداشت' WHERE id = 'acc-old-2'"
            ))
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-new-3')"))
            assert connection.scalar(text("SELECT status FROM accounts WHERE id = 'acc-new-3'")) == "active"
    finally:
        engine.dispose()

    command.downgrade(config, "0036_upload_sessions")
    engine = create_engine(database_url)
    try:
        assert "status" not in {c["name"] for c in inspect(engine).get_columns("accounts")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM accounts")) == 3
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0036_upload_sessions"
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
            assert connection.scalar(text("SELECT COUNT(*) FROM accounts WHERE status = 'active'")) == 3
    finally:
        engine.dispose()


def test_system_settings_migration_round_trip(tmp_path, monkeypatch):
    """0038 (panel settings store): create, write a row, downgrade drops it, upgrade recreates."""
    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-settings.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "0037_account_status")
    engine = create_engine(database_url)
    try:
        assert "system_settings" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(config, "0038_system_settings")
    engine = create_engine(database_url)
    try:
        assert {c["name"] for c in inspect(engine).get_columns("system_settings")} == {"key", "value", "updated_by", "updated_at"}
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO system_settings (key, value, updated_by) VALUES ('texts.reminder_head', '{\"v\": \"x\"}', 'owner-1')"
            ))
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()

    command.downgrade(config, "0037_account_status")
    engine = create_engine(database_url)
    try:
        assert "system_settings" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM system_settings")) == 0
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0038_system_settings"
    finally:
        engine.dispose()
