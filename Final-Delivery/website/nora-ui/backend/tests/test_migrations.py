from __future__ import annotations

import sys
from pathlib import Path

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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_event_interaction"
    finally:
        engine.dispose()
