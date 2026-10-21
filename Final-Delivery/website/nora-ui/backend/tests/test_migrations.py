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
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0028_certificates"
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
            "form_payments", "form_payment_transactions", "service_checks", "admin_audit_events", "certificates",
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
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0028_certificates"
    finally:
        engine.dispose()
