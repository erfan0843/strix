"""Local-only setup regressions; never touch the checkout's developer state."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text

UI_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def local_dev(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("nora_local_dev_qa", UI_ROOT / "tools/local-dev.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE_ROOT", tmp_path / ".local")
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / ".env.local")
    # Environment writes are reverted by pytest; real provider values are not used.
    original = dict(os.environ)
    yield module
    os.environ.clear()
    os.environ.update(original)


def test_local_init_runs_actual_migrations_without_seeded_accounts_or_providers(local_dev, capsys):
    local_dev.initialize(False)
    values = dotenv_values(local_dev.ENV_FILE)
    assert values["NORA_OWNER_PASSWORD_HASH"] == ""
    assert values["NORA_COOKIE_SECURE"] == "false"
    assert values["NORA_PUBLIC_BASE_URL"] == ""
    assert all(values[key] == "" for key in local_dev.EXTERNAL_KEYS)
    engine = create_engine(values["NORA_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0022_web_account_registration_history"
            assert connection.scalar(text("SELECT COUNT(*) FROM accounts")) == 0
            assert connection.scalar(text("SELECT COUNT(*) FROM form_responses")) == 0
        assert "site_content" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
    if os.name == "posix":
        assert local_dev.ENV_FILE.stat().st_mode & 0o777 == 0o600
    assert "مهاجرت محلی کامل شد" in capsys.readouterr().out


def test_repeat_init_preserves_existing_env_and_database(local_dev):
    local_dev.initialize(False)
    before = local_dev.ENV_FILE.read_bytes()
    database = local_dev.STATE_ROOT / "nora-dev.sqlite3"
    before_db = database.read_bytes()
    with pytest.raises(local_dev.LocalSetupError, match="overwrite"):
        local_dev.initialize(False)
    assert local_dev.ENV_FILE.read_bytes() == before
    assert database.read_bytes() == before_db


def test_local_launcher_rejects_external_database_before_any_migration(local_dev, monkeypatch):
    local_dev.ENV_FILE.write_text('NORA_DATABASE_URL="postgresql+psycopg://qa@db.example.invalid/qa"\n')
    with pytest.raises(local_dev.LocalSetupError, match="SQLite"):
        local_dev.prepare_environment()
    assert not local_dev.STATE_ROOT.exists()


def test_local_launcher_rejects_sqlite_outside_owned_state_directory(local_dev, tmp_path):
    outside = tmp_path / "unrelated.sqlite3"
    local_dev.ENV_FILE.write_text(f'NORA_DATABASE_URL="sqlite+pysqlite:///{outside}"\n')
    with pytest.raises(local_dev.LocalSetupError, match=".local"):
        local_dev.prepare_environment()
    assert not outside.exists()


def test_inherited_provider_and_seo_values_are_disabled(local_dev, monkeypatch):
    local_dev.initialize(False)
    monkeypatch.setenv("SAFIR_API_KEY", "FAKE_TEST_ONLY_DO_NOT_SEND")
    monkeypatch.setenv("NORA_BALE_BOT_TOKEN", "FAKE_TEST_ONLY_DO_NOT_SEND")
    monkeypatch.setenv("NORA_PUBLIC_BASE_URL", "https://qa.example.invalid")
    monkeypatch.setenv("NORA_SEO_BUSINESS_TELEPHONE", "FAKE_TEST_ONLY")
    local_dev.prepare_environment()
    assert all(os.environ[key] == "" for key in local_dev.EXTERNAL_KEYS)
    assert os.environ["NORA_PUBLIC_BASE_URL"] == ""
    assert os.environ["NORA_SEO_BUSINESS_TELEPHONE"] == ""


def test_provider_key_in_local_file_is_refused_without_echoing_it(local_dev, capsys):
    local_dev.ENV_FILE.write_text('SAFIR_API_KEY="FAKE_TEST_SECRET_ONLY"\n')
    with pytest.raises(local_dev.LocalSetupError) as error:
        local_dev.prepare_environment()
    assert "FAKE_TEST_SECRET_ONLY" not in str(error.value)
    assert "FAKE_TEST_SECRET_ONLY" not in capsys.readouterr().out


def test_owner_password_is_local_private_hash_not_plaintext_or_output(local_dev, monkeypatch, capsys):
    from backend.security import verify_password
    password = "FAKE_TEST_LOCAL_PASSWORD_ONLY_42"
    monkeypatch.setattr(local_dev.getpass, "getpass", lambda _prompt: password)
    local_dev.initialize(True)
    values = dotenv_values(local_dev.ENV_FILE)
    assert values["NORA_OWNER_USERNAME"] == "local-owner"
    assert verify_password(password, values["NORA_OWNER_PASSWORD_HASH"])
    assert password not in local_dev.ENV_FILE.read_text()
    assert password not in capsys.readouterr().out
    assert values["NORA_OWNER_PASSWORD_HASH"] not in capsys.readouterr().out


def test_missing_local_config_does_not_create_files(local_dev):
    with pytest.raises(local_dev.LocalSetupError, match="init"):
        local_dev.prepare_environment()
    assert not local_dev.ENV_FILE.exists()
    assert not local_dev.STATE_ROOT.exists()
