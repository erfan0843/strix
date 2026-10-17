"""بارگذاری نسخهٔ پشتیبان برای ممیزی: فقط staging، فقط خواندن، بدون افشای داده.

هر آزمون یک قاعدهٔ امنیتی را می‌سنجد که در رابط کاربری «داده‌ها و مهاجرت»
به کاربر نشان داده می‌شود؛ نه شکل ظاهری صفحه.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import UI_ROOT, Settings  # noqa: E402
from backend.data_staging import SQLITE_HEADER, StagingError, StagingStore, UploadLimits  # noqa: E402
from sqlalchemy import inspect as sa_inspect, text  # noqa: E402

from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    Base,
)
from backend.security import hash_password, token_digest  # noqa: E402

OWNER_USER = "nora-owner"
OWNER_PASS = "correct-horse-staple-42"
ORIGIN = {"Origin": "http://testserver"}
PHONE = "09121234567"
FULL_NAME = "لیلا رضایی"


def make_backup(path: Path, *, users: int = 3, duplicate_phone: bool = True) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                bale_user_id INTEGER,
                mobile TEXT,
                full_name TEXT
            );
            CREATE TABLE form_responses (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                bale_user_id INTEGER,
                status TEXT
            );
            """
        )
        for index in range(users):
            mobile = PHONE if (duplicate_phone and index < 2) else f"0912000000{index}"
            connection.execute(
                "INSERT INTO users (bale_user_id, mobile, full_name) VALUES (?, ?, ?)",
                (900000 + index, mobile, FULL_NAME),
            )
        connection.execute(
            "INSERT INTO form_responses (user_id, bale_user_id, status) VALUES (?, ?, 'accepted')",
            (1, 900000),
        )
        connection.execute(
            "INSERT INTO form_responses (user_id, bale_user_id, status) VALUES (?, ?, 'accepted')",
            (999, 424242),
        )
        connection.commit()
    finally:
        connection.close()
    return path


@pytest.fixture
def data_env(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        data_staging_dir=str(staging),
        data_upload_max_bytes=1024 * 1024,
        data_staging_retention_hours=72,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, tmp_path, staging
    engine.dispose()


MANAGER_SESSION = "sess-data-manager"
MANAGER_CSRF = "csrf-data-manager"


def install_manager_session(client: TestClient, account_id: str = "acct-data-manager") -> None:
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        # «مدیر» مجوز sys_settings/sys_backup ندارد؛ این دقیقاً همان مرزی است
        # که باید در بک‌اند اعمال شود، نه با پنهان‌کردن دکمه در رابط کاربری.
        db.add(AccountRoleRecord(account_id=account_id, role="manager", assigned_by="owner-01"))
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                auth_provider="manager-password",
                token_hash=token_digest(MANAGER_SESSION + account_id),
                csrf_hash=token_digest(MANAGER_CSRF + account_id),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    settings = client.app.state.settings
    client.cookies.set(settings.account_cookie_name, MANAGER_SESSION + account_id, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, MANAGER_CSRF + account_id, path="/")


def manager_headers(account_id: str = "acct-data-manager") -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": MANAGER_CSRF + account_id}


AUTH_BOOKKEEPING = {"owner_sessions", "public_write_throttles"}


def database_snapshot(engine) -> dict[str, list[tuple]]:
    """Every row of every business table, so a test can prove nothing was written.

    Login sessions and the upload rate limiter are excluded explicitly: they are
    authentication bookkeeping, not data, and are created before the snapshot.
    """
    snapshot: dict[str, list[tuple]] = {}
    with engine.connect() as connection:
        for table in sa_inspect(engine).get_table_names():
            if table in AUTH_BOOKKEEPING:
                continue
            rows = connection.execute(text(f'SELECT * FROM "{table}"')).fetchall()
            snapshot[table] = [tuple(row) for row in rows]
    return snapshot


def owner_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/auth/login", json={"username": OWNER_USER, "password": OWNER_PASS}, headers=ORIGIN
    )
    assert login.status_code == 200, login.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def upload(client: TestClient, headers: dict[str, str], path: Path, name: str | None = None):
    return client.post(
        "/api/owner/data/uploads",
        content=path.read_bytes(),
        headers={
            **headers,
            "Content-Type": "application/octet-stream",
            "X-File-Name": name if name is not None else path.name,
        },
    )


# ---------------------------------------------------------------------------
# دسترسی و مسیر
# ---------------------------------------------------------------------------

def test_only_the_owner_can_upload_or_list(data_env):
    client, tmp_path, _staging = data_env
    backup = make_backup(tmp_path / "nora.db")
    assert client.get("/api/owner/data/uploads").status_code == 401
    assert upload(client, ORIGIN, backup).status_code == 401

    headers = owner_headers(client)
    listed = client.get("/api/owner/data/uploads", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["uploads"] == []
    assert listed.json()["limits"]["max_bytes"] == 1024 * 1024


def test_a_manager_without_backup_permission_is_refused(data_env):
    client, tmp_path, _staging = data_env
    install_manager_session(client)
    backup = make_backup(tmp_path / "nora.db")
    headers = manager_headers()
    assert client.get("/api/owner/data/uploads", headers=headers).status_code == 403
    uploaded = upload(client, headers, backup)
    assert uploaded.status_code == 403
    assert uploaded.json()["detail"] == "permission_denied"
    assert client.delete("/api/owner/data/uploads/" + "a" * 32, headers=headers).status_code == 403


def test_staging_is_outside_the_public_ui_root(monkeypatch):
    settings = Settings(
        database_url=None, owner_id="o", owner_username="", owner_password_hash=""
    )
    staging = Path(settings.data_staging_dir).resolve()
    assert UI_ROOT.resolve() not in staging.parents, "staging نباید زیر ریشهٔ وب باشد"


# ---------------------------------------------------------------------------
# پذیرش فایل معتبر و رد فایل نامعتبر
# ---------------------------------------------------------------------------

def test_status_reports_the_database_without_leaking_paths(data_env):
    client, _tmp_path, staging = data_env
    headers = owner_headers(client)
    response = client.get("/api/owner/data/status", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["engine"] == "sqlite"
    assert body["operational_writes"] == 0
    assert body["staging"]["outside_webroot"] is True
    assert str(staging) not in response.text
    assert "tmp" not in body["staging"]


def test_valid_sqlite_backup_is_accepted_and_inspected(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")

    response = upload(client, headers, backup, "../../etc/passwd.db")
    assert response.status_code == 201, response.text
    item = response.json()["upload"]
    assert item["state"] == "inspected"
    assert item["structure"]["integrity"] == "ok"
    assert item["structure"]["table_count"] == 2
    assert item["display_name"] == "passwd.db", "نام باید پاک‌سازی شود، نه مسیر"
    assert item["size_bytes"] == backup.stat().st_size
    assert item["sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()

    stored = staging / "uploads" / item["id"] / "source.db"
    assert stored.is_file()
    assert stored.read_bytes() == backup.read_bytes()
    assert not (tmp_path / "etc").exists()


def test_corrupt_and_non_sqlite_files_are_rejected(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    fake = tmp_path / "fake.db"
    fake.write_bytes(b"this is definitely not a database" * 100)
    rejected = upload(client, headers, fake)
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "backup_not_sqlite"

    truncated = tmp_path / "truncated.db"
    truncated.write_bytes(SQLITE_HEADER + b"\x00" * 200)
    broken = upload(client, headers, truncated)
    assert broken.status_code == 422
    assert broken.json()["detail"] in {"backup_integrity_check_failed", "backup_not_sqlite"}
    assert list((staging / "uploads").iterdir()) == []


def test_sqlite_that_is_not_a_nora_backup_is_rejected(data_env):
    client, tmp_path, _staging = data_env
    headers = owner_headers(client)
    foreign = tmp_path / "other.db"
    connection = sqlite3.connect(foreign)
    try:
        connection.execute("CREATE TABLE invoices (id INTEGER PRIMARY KEY, total INTEGER)")
        connection.execute("INSERT INTO invoices (total) VALUES (42)")
        connection.commit()
    finally:
        connection.close()
    response = upload(client, headers, foreign, "nora-backup.db")
    assert response.status_code == 422
    assert response.json()["detail"] == "backup_not_legacy_database"


def test_upload_and_audit_never_write_to_the_operational_database(data_env):
    client, tmp_path, _staging = data_env
    engine = client.app.state.engine
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    before = database_snapshot(engine)
    created = upload(client, headers, backup)
    assert created.status_code == 201
    upload_id = created.json()["upload"]["id"]
    assert client.get("/api/owner/data/uploads", headers=headers).status_code == 200
    assert client.get(f"/api/owner/data/uploads/{upload_id}", headers=headers).status_code == 200
    assert client.post(f"/api/owner/data/uploads/{upload_id}/audit", headers=headers).status_code == 200
    assert database_snapshot(engine) == before


def test_oversized_upload_is_rejected_and_nothing_is_left(data_env, monkeypatch):
    client, tmp_path, staging = data_env
    client.app.state.settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        data_staging_dir=str(staging),
        data_upload_max_bytes=4096,
    )
    headers = owner_headers(client)
    big = tmp_path / "big.db"
    big.write_bytes(SQLITE_HEADER + b"\x00" * 8192)
    response = upload(client, headers, big)
    assert response.status_code == 413
    assert response.json()["detail"] == "backup_too_large"
    assert not any((staging / "uploads").glob("*"))
    assert not any((staging / "tmp").glob("*"))


def test_wrong_content_type_is_refused(data_env):
    client, tmp_path, _staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    response = client.post(
        "/api/owner/data/uploads",
        content=backup.read_bytes(),
        headers={**headers, "Content-Type": "text/html", "X-File-Name": "x.db"},
    )
    assert response.status_code == 415


def test_unknown_upload_ids_cannot_escape_the_staging_directory(data_env):
    client, _tmp_path, _staging = data_env
    headers = owner_headers(client)
    for bad in ("..", "..%2f..%2fetc", "a" * 64, "not-hex!"):
        assert client.get(f"/api/owner/data/uploads/{bad}", headers=headers).status_code in (404, 422)
        assert client.delete(f"/api/owner/data/uploads/{bad}", headers=headers).status_code in (404, 422)


# ---------------------------------------------------------------------------
# ممیزی فقط-خواندنی
# ---------------------------------------------------------------------------

def test_audit_runs_read_only_and_checksum_stays_identical(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    created = upload(client, headers, backup)
    upload_id = created.json()["upload"]["id"]
    stored = staging / "uploads" / upload_id / "source.db"
    before_bytes = stored.read_bytes()
    before_stat = stored.stat()

    audited = client.post(f"/api/owner/data/uploads/{upload_id}/audit", headers=headers)
    assert audited.status_code == 200, audited.text
    payload = audited.json()
    assert payload["unchanged"] is True
    item = payload["upload"]
    assert item["state"] == "audited"
    assert item["audit"]["unchanged"] is True
    assert item["audit"]["checksum_before"] == item["audit"]["checksum_after"]
    report = item["audit"]["report"]
    assert report["tool"] == "legacy_data_audit"
    assert report["mode"] == "dry-run"
    assert report["legacy"]["users"]["total"] == 3
    assert report["legacy"]["users"]["duplicate_mobiles"] == 1
    assert report["legacy"]["orphans_by_bale_user_id"]["form_responses"] == 1

    assert stored.read_bytes() == before_bytes
    assert stored.stat().st_mtime == before_stat.st_mtime
    # و خودِ فایل با اتصال فقط-خواندنی قابل نوشتن نیست.
    uri = f"file:{stored}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM users")
    finally:
        connection.close()


def test_audit_report_contains_no_personal_data(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    upload_id = upload(client, headers, backup).json()["upload"]["id"]
    response = client.post(f"/api/owner/data/uploads/{upload_id}/audit", headers=headers)
    assert response.status_code == 200
    text = response.text + (staging / "uploads" / upload_id / "meta.json").read_text("utf-8")
    assert PHONE not in text
    assert FULL_NAME not in text
    assert "full_name" not in text


def test_audit_is_unavailable_when_the_tool_is_missing(data_env):
    client, tmp_path, _staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    upload_id = upload(client, headers, backup).json()["upload"]["id"]
    client.app.state.settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        data_staging_dir=client.app.state.settings.data_staging_dir,
        legacy_audit_script=str(tmp_path / "missing.py"),
    )
    response = client.post(f"/api/owner/data/uploads/{upload_id}/audit", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "audit_tool_not_available"


# ---------------------------------------------------------------------------
# نگهداری، سهمیه و حذف
# ---------------------------------------------------------------------------

def test_expired_uploads_are_purged_on_listing(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    upload_id = upload(client, headers, make_backup(tmp_path / "nora.db")).json()["upload"]["id"]
    meta_path = staging / "uploads" / upload_id / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8"))
    meta["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    assert client.get("/api/owner/data/uploads", headers=headers).json()["uploads"] == []
    assert not (staging / "uploads" / upload_id).exists()


def test_explicit_delete_removes_only_that_upload(data_env):
    client, tmp_path, staging = data_env
    headers = owner_headers(client)
    first = upload(client, headers, make_backup(tmp_path / "a.db")).json()["upload"]["id"]
    second = upload(client, headers, make_backup(tmp_path / "b.db")).json()["upload"]["id"]
    deleted = client.delete(f"/api/owner/data/uploads/{first}", headers=headers)
    assert deleted.status_code == 200
    assert not (staging / "uploads" / first).exists()
    assert (staging / "uploads" / second).exists()
    assert client.delete(f"/api/owner/data/uploads/{first}", headers=headers).status_code == 404


def test_staging_store_enforces_quota(tmp_path):
    source = make_backup(tmp_path / "q.db")
    payload = source.read_bytes()
    store = StagingStore(
        tmp_path / "quota",
        UploadLimits(max_bytes=len(payload), retention_hours=1, quota_bytes=len(payload) + 64),
    )
    store.create_upload([payload], "q.db")
    with pytest.raises(StagingError) as excinfo:
        store.create_upload([payload], "q2.db")
    assert excinfo.value.code == "staging_quota_exceeded"
    assert len(list((store.uploads_dir).iterdir())) == 1


def test_upload_rate_limit_is_applied(data_env):
    client, tmp_path, _staging = data_env
    headers = owner_headers(client)
    backup = make_backup(tmp_path / "nora.db")
    responses = [upload(client, headers, backup) for _ in range(11)]
    assert any(response.status_code == 429 for response in responses), [
        response.status_code for response in responses
    ]
    assert responses[0].status_code == 201
