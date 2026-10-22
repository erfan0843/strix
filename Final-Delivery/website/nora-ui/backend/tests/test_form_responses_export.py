"""بازیابی پنل (مرحلهٔ B): خروجی CSV واقعی پاسخ‌های فرم.

همان ردیف‌های ``GET /api/forms/{id}/responses`` با ``format=csv``؛ مجوز ``fm_export`` سمت سرور،
ستون‌های مالی فقط با مجوز ``finance`` (مالک)، فیلد «خارج از خروجی اکسل» حذف، ثبت در تاریخچهٔ عملیات.
"""
from __future__ import annotations

import csv
import io
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountRecord, AccountRoleRecord, AccountSessionRecord, AdminAuditEventRecord, Base  # noqa: E402
from backend.security import hash_password, token_digest  # noqa: E402

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), session_ttl_seconds=3600, cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def owner_login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "nora-owner", "password": "correct-horse-staple-42"}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def install_account_session(client: TestClient, account_id: str, role: str | None) -> None:
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        if role:
            db.add(AccountRoleRecord(account_id=account_id, role=role, assigned_by="owner-01"))
        db.add(AccountSessionRecord(
            id=str(uuid.uuid4()), account_id=account_id, auth_provider="manager-password",
            token_hash=token_digest("sess-" + account_id), csrf_hash=token_digest("csrf-" + account_id),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
    settings = client.app.state.settings
    client.cookies.set(settings.account_cookie_name, "sess-" + account_id, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, "csrf-" + account_id, path="/")


def seed_form_with_responses(client: TestClient) -> str:
    headers = owner_login(client)
    payload = {
        "name": "ثبت‌نام آزمایشی خروجی", "model": "registration", "need": "reg", "slug": "export/test", "ev": "",
        "settings": {"description": "فرم آزمایشی"},
        "fields": [
            {"id": "full-name", "t": "text", "l": "نام کامل", "required": True},
            {"id": "note", "t": "text", "l": "یادداشت داخلی", "col": False},
        ],
    }
    created = client.post("/api/forms", json=payload, headers={**headers, "Idempotency-Key": "export-create-0001"})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    assert client.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=headers).status_code == 200
    for index, name in enumerate(["=HYPERLINK(\"x\")", "لیلا آزمایشی"]):
        public = TestClient(client.app)
        assert public.get(f"/api/public/forms/{form_id}/draft").status_code == 200
        submitted = public.post(
            f"/api/public/forms/{form_id}/responses",
            json={"answers": {"full-name": name, "note": f"محرمانه-{index}"}}, headers=ORIGIN,
        )
        assert submitted.status_code in (200, 201), submitted.text
    return form_id


def parse_csv(response) -> list[list[str]]:
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "no-store" in response.headers["cache-control"]
    assert response.text.startswith("\ufeff"), "UTF-8 BOM برای اکسل"
    return list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))


def test_owner_export_is_real_flat_csv_with_finance_columns_and_audit(client):
    form_id = seed_form_with_responses(client)
    exported = client.get(f"/api/forms/{form_id}/responses?format=csv")
    assert exported.status_code == 200, exported.text
    rows = parse_csv(exported)
    header, body = rows[0], rows[1:]
    assert header[:3] == ["response_id", "status", "created_at"]
    assert "نام کامل" in header
    assert "یادداشت داخلی" not in header, "فیلد «خارج از خروجی اکسل» صادر نمی‌شود"
    assert "payment_status" in header and "amount" in header, "ستون مالی برای مالک"
    assert len(body) == 2
    name_col = header.index("نام کامل")
    names = {row[name_col] for row in body}
    assert "لیلا آزمایشی" in names
    assert "'=HYPERLINK(\"x\")" in names, "پاسخ فرمول‌مانند خنثی می‌شود"
    assert all(row[header.index("status")] == "accepted" for row in body)
    assert all(row[header.index("payment_status")] == "" for row in body), "فرم رایگان رکورد پرداخت ندارد؛ وضعیت جعل نمی‌شود"

    with client.app.state.session_factory() as db:
        audit = db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "form.responses.export")).all()
    assert len(audit) == 1
    assert audit[0].target_id == form_id
    assert audit[0].details["rows"] == 2 and audit[0].details["finance_columns"] is True

    assert client.get(f"/api/forms/{form_id}/responses?format=xlsx").status_code == 422, "فقط CSV واقعی؛ قالب دیگری ادعا نمی‌شود"
    listed = client.get(f"/api/forms/{form_id}/responses")
    assert listed.status_code == 200 and listed.json()["total"] == 2, "فهرست JSON دست‌نخورده می‌ماند"


def test_manager_export_omits_finance_columns_and_roleless_account_is_denied(client):
    form_id = seed_form_with_responses(client)
    client.cookies.clear()

    install_account_session(client, "acct-manager-export", "manager")
    exported = client.get(f"/api/forms/{form_id}/responses?format=csv")
    assert exported.status_code == 200, exported.text
    header = parse_csv(exported)[0]
    assert "نام کامل" in header
    assert "payment_status" not in header and "amount" not in header and "transaction_id" not in header, \
        "مدیر بدون مجوز مالی ستون مبلغ/تراکنش نمی‌گیرد"

    client.cookies.clear()
    install_account_session(client, "acct-member-export", None)
    denied = client.get(f"/api/forms/{form_id}/responses?format=csv")
    assert denied.status_code == 403, denied.text
    assert client.get(f"/api/forms/{form_id}/responses").status_code == 403

    client.cookies.clear()
    assert client.get(f"/api/forms/{form_id}/responses?format=csv").status_code == 401
