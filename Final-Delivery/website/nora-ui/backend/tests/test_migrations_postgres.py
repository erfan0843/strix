"""PostgreSQL-specific migration regressions, never against application tables.

Set NORA_TEST_POSTGRES_URL to a disposable PostgreSQL instance. Every online
case creates its own random schema inside a transaction and rolls it back;
no existing tables, accounts, identities, or revisions are modified.
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.models import FormResponseDraftRecord

BACKEND_ROOT = Path(__file__).resolve().parents[1]


# Resolved from the migration scripts so the test never pins a stale head.
HEAD = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini"))).get_current_head()
PRE_COMPANIONS = "0017_form_companions"


def test_offline_postgres_script_preserves_revision_ids_and_only_widens_metadata(monkeypatch):
    monkeypatch.setenv("NORA_DATABASE_URL", "postgresql+psycopg://qa@localhost/nora_qa")
    output = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "0018_separate_companion_responses" in sql
    assert HEAD in sql
    assert sql.count("DO $nora_version_width$") == 2
    assert "atttypmod > 0" in sql and "atttypmod < 68" in sql
    assert "attrelid = 'alembic_version'::regclass" in sql
    assert "ALTER COLUMN version_num TYPE VARCHAR(64)" in sql


@pytest.mark.parametrize("initial_type", ["VARCHAR(32)", "VARCHAR(33)", "VARCHAR(128)", "TEXT"])
def test_postgres_upgrade_and_downgrade_preserve_data_and_version_capacity(monkeypatch, initial_type):
    url = os.environ.get("NORA_TEST_POSTGRES_URL", "")
    if not url:
        pytest.skip("requires an explicitly configured disposable NORA_TEST_POSTGRES_URL")
    assert url.startswith(("postgresql://", "postgresql+psycopg://"))
    monkeypatch.setenv("NORA_DATABASE_URL", url)
    engine = create_engine(url)
    schema = "nora_migration_qa_" + uuid4().hex
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
                connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", pg_catalog')
                config = Config(str(BACKEND_ROOT / "alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "0021_form_payment_transactions" if initial_type == "VARCHAR(33)" else PRE_COMPANIONS)
                # Only hard-coded, parameterized types enter this SQL.
                # VARCHAR(33) at 0021 simulates an earlier manual capacity fix.
                connection.exec_driver_sql(
                    f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE {initial_type}"
                )
                account_id, form_id, draft_id = (str(uuid4()) for _ in range(3))
                # Raw SQL at this revision: the ORM models already know columns that later
                # migrations add (0037 ``accounts.status``…, 0033 ``forms.purpose``).
                connection.execute(text("INSERT INTO accounts (id) VALUES (:id)"), {"id": account_id})
                connection.execute(text(
                    "INSERT INTO forms (id, owner_id, title, model, need, status, settings, version) "
                    "VALUES (:id, 'migration-qa', 'فرم آزمون مهاجرت', 'registration', 'registration', 'draft', '{}', 1)"
                ), {"id": form_id})
                connection.execute(FormResponseDraftRecord.__table__.insert().values(
                    id=draft_id, form_id=form_id, form_version=1,
                    token_hash="a" * 64, bot_bale_user_id="70001", answers={}, companions=[],
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                ))
                command.upgrade(config, "head")
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
                # Phase 8 (0031): the four interaction tables and their constraints exist on PostgreSQL too.
                head_tables = set(inspect(connection).get_table_names(schema=schema))
                assert {"event_resources", "event_questions", "event_reviews", "event_content_reports"} <= head_tables
                assert {"uq_event_reviews_account_event"} <= {
                    constraint["name"] for constraint in inspect(connection).get_unique_constraints("event_reviews", schema=schema)
                }
                # Phase 9 (0032): recorded products, orders and access rights + widened resource access.
                assert {"event_recordings", "recording_sessions", "recording_orders", "recording_access"} <= head_tables
                assert {"uq_recording_access_account"} <= {
                    constraint["name"] for constraint in inspect(connection).get_unique_constraints("recording_access", schema=schema)
                }
                assert {"session_id", "delivery"} <= {
                    column["name"] for column in inspect(connection).get_columns("event_resources", schema=schema)
                }
                connection.execute(text(
                    "INSERT INTO event_resources (id, event_id, title, status, access, kind, delivery) "
                    "VALUES ('res-pg-1', 'ev-pg', 'ویدیوی جلسه', 'published', 'purchased', 'file', 'view')"
                ))
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(text(
                            "INSERT INTO event_resources (id, event_id, title, status, access, kind, delivery) "
                            "VALUES ('res-pg-2', 'ev-pg', 'نامعتبر', 'published', 'purchased', 'file', 'stream')"
                        ))
                # Phase 9.1 (0033): purpose/recording link on forms, ledger ↔ form links, certificate policy, embed kinds.
                assert {"purpose", "recording_id"} <= {
                    column["name"] for column in inspect(connection).get_columns("forms", schema=schema)
                }
                assert {"form_response_id", "form_payment_id"} <= {
                    column["name"] for column in inspect(connection).get_columns("recording_orders", schema=schema)
                }
                assert "certificate_policy" in {
                    column["name"] for column in inspect(connection).get_columns("event_recordings", schema=schema)
                }
                # Phase 9.5 (0036): upload sessions, system markers and the one-shot announcement column.
                assert {"upload_sessions", "system_markers"} <= head_tables
                assert "announced_at" in {
                    column["name"] for column in inspect(connection).get_columns("event_resources", schema=schema)
                }
                assert {"ck_upload_sessions_status", "ck_upload_sessions_bytes"} <= {
                    check["name"] for check in inspect(connection).get_check_constraints("upload_sessions", schema=schema)
                }
                connection.execute(text(
                    "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                    "VALUES ('res-pg-yt', 'ev-pg', 'ویدیوی یوتیوب', 'published', 'purchased', 'youtube', 'https://youtu.be/dQw4w9WgXcQ')"
                ))
                for statement in (
                    "INSERT INTO event_resources (id, event_id, title, status, access, kind, link_url) "
                    "VALUES ('res-pg-bad', 'ev-pg', 'x', 'published', 'purchased', 'vimeo', 'https://vimeo.com/1')",
                    "UPDATE forms SET purpose = 'shop'",
                ):
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(text(statement))
                version_type = inspect(connection).get_columns("alembic_version", schema=schema)[0]["type"]
                expected_length = {"VARCHAR(32)": 64, "VARCHAR(33)": 64, "VARCHAR(128)": 128, "TEXT": None}[initial_type]
                assert getattr(version_type, "length", None) == expected_length
                assert connection.scalar(text("SELECT id FROM accounts")) == account_id
                # Historical Bale associations must NOT become guessed web-account links.
                old_draft = connection.execute(text(
                    "SELECT id, account_id, bot_bale_user_id FROM form_response_drafts"
                )).one()
                assert tuple(old_draft) == (draft_id, None, "70001")
                command.downgrade(config, "0031_event_interaction")
                # Downgrade folds purchased-only files to 'staff' (never public) and keeps the row.
                assert connection.scalar(text("SELECT access FROM event_resources WHERE id = 'res-pg-1'")) == "staff"
                # 0033 downgrade folded the embed to a plain link and kept the URL.
                assert connection.scalar(text("SELECT kind FROM event_resources WHERE id = 'res-pg-yt'")) == "link"
                assert "event_recordings" not in set(inspect(connection).get_table_names(schema=schema))
                command.downgrade(config, PRE_COMPANIONS)
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PRE_COMPANIONS
                assert connection.scalar(text("SELECT id FROM accounts")) == account_id
                assert connection.scalar(text("SELECT id FROM form_response_drafts")) == draft_id
            finally:
                transaction.rollback()
        with engine.connect() as connection:
            assert not connection.scalar(text(
                "SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = :schema"
            ), {"schema": schema})
    finally:
        engine.dispose()
