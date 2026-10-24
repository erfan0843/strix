"""Shared certificate registry: bot sync (``/api/bot/certificates``) and managers' read API.

In-memory SQLite only. Ownership is resolved on the server from the Bale id;
a certificate whose owner has no server identity is rejected (never stored,
never auto-matched). Files come from the existing private-file store and must
belong to the certificate owner. Nothing here mutates certificate status from
the panel: the bot stays the single writer.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import certificates as certificates_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountRecord, Base, CertificateRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_admin_users_attendance_api import set_profile  # noqa: E402
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    assign_manager,
    bale_login,
    owner_login,
    service_headers,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII="
)
PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def make_app():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bot_service_token=SERVICE_TOKEN,
        owner_bale_user_id="70001",
    )
    return create_app(settings, engine=engine), engine


def upload(client: TestClient, bale_user_id: str, key: str, content: bytes, content_type: str, name: str) -> str:
    response = client.post(
        "/api/bot/files",
        content=content,
        headers={
            **service_headers(),
            "X-Bale-User-Id": bale_user_id,
            "X-File-Name": name,
            "Idempotency-Key": key,
            "Content-Type": content_type,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def submit(client: TestClient, *, bale_user_id: str, key: str, certificate: dict, file_refs: dict | None = None):
    payload: dict = {"bale_user_id": bale_user_id, "external_key": key, "certificate": certificate}
    if file_refs is not None:
        payload["file_refs"] = file_refs
    return client.post("/api/bot/certificates", json=payload, headers=service_headers())


SOURCE_ID = "0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b"


def base_certificate(**extra) -> dict:
    data = {
        "status": "issued", "source": "bot_legacy", "source_id": SOURCE_ID, "legacy_id": 1, "kind": "event",
        "serial": "N-0001", "full_code": "140501-A1", "event_ref": "17", "event_title": "کارگاه نجوم",
        "title": "گواهی حضور", "holder_name": "زهرا موسوی", "issued_on": "1405/01/12", "expires_on": "",
        "issued_at": "2026-04-01T10:00:00+00:00", "issued_by_bale_user_id": "70001", "verify_count": 2,
    }
    data.update(extra)
    return data


def test_bot_sync_requires_service_token_server_owner_and_owned_files():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            # Service identity is mandatory.
            anonymous = client.post("/api/bot/certificates", json={})
            assert anonymous.status_code == 401
            # Owner without a server identity: not stored and no account is created.
            missing = submit(client, bale_user_id="919999", key=f"{SOURCE_ID}:9", certificate=base_certificate(legacy_id=9))
            assert missing.status_code == 404 and missing.json()["detail"] == "owner_identity_not_found"
            with Session(engine) as db:
                assert db.scalar(select(func.count(AccountRecord.id))) == 0
                assert db.scalar(select(func.count(CertificateRecord.id))) == 0

            holder = bale_login(client, 910001)
            client.cookies.clear()
            other = bale_login(client, 910002)
            client.cookies.clear()

            created = submit(client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate())
            assert created.status_code == 200, created.text
            body = created.json()
            assert body["created"] is True and body["account_id"] == holder and body["has_file"] is False
            certificate_id = body["id"]

            # Idempotent replay refreshes instead of duplicating.
            replay = submit(client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(verify_count=5))
            assert replay.status_code == 200 and replay.json()["created"] is False and replay.json()["id"] == certificate_id
            with Session(engine) as db:
                assert db.scalar(select(func.count(CertificateRecord.id))) == 1
                assert db.get(CertificateRecord, certificate_id).verify_count == 5

            # The same external key can never be re-owned by another Bale id.
            hijack = submit(client, bale_user_id="910002", key=f"{SOURCE_ID}:1", certificate=base_certificate())
            assert hijack.status_code == 409 and hijack.json()["detail"] == "certificate_owner_mismatch"

            # Files must be private files of the same owner and of the right type.
            own_pdf = upload(client, "910001", f"cert:{SOURCE_ID}:1:pdf", PDF, "application/pdf", "cert.pdf")
            own_png = upload(client, "910001", f"cert:{SOURCE_ID}:1:png", PNG, "image/png", "cert.png")
            foreign_pdf = upload(client, "910002", f"cert:{SOURCE_ID}:2:pdf", PDF, "application/pdf", "other.pdf")
            stolen = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(),
                file_refs={"pdf": foreign_pdf},
            )
            assert stolen.status_code == 422 and stolen.json()["detail"] == "file_not_owned_by_certificate_owner"
            swapped = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(),
                file_refs={"pdf": own_png},
            )
            assert swapped.status_code == 422
            with_files = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(),
                file_refs={"pdf": own_pdf, "png": own_png},
            )
            assert with_files.status_code == 200 and with_files.json()["has_file"] and with_files.json()["has_preview"]
            # A later status-only sync keeps the files attached.
            revoked = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(status="revoked"),
            )
            assert revoked.status_code == 200 and revoked.json()["status"] == "revoked" and revoked.json()["has_file"]

            # Validation: unknown fields, bad status, bad key, missing identity.
            assert submit(client, bale_user_id="910001", key="k:1", certificate={**base_certificate(), "password": "x"}).status_code == 422
            assert submit(client, bale_user_id="910001", key="k:2", certificate=base_certificate(status="pending")).status_code == 422
            assert submit(client, bale_user_id="910001", key="bad key!", certificate=base_certificate()).status_code == 422
            assert submit(client, bale_user_id="910001", key="k:3", certificate=base_certificate(serial="", full_code="", legacy_id=None)).status_code == 422
            assert submit(client, bale_user_id="not-an-id", key="k:4", certificate=base_certificate()).status_code == 422
            assert client.post("/api/bot/certificates", json={"bale_user_id": "910001"}, headers=service_headers()).status_code == 400
            assert other != holder
    finally:
        engine.dispose()


def test_admin_certificate_listing_detail_file_and_permissions():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            holder = bale_login(client, 910001)
            client.cookies.clear()
            manager = bale_login(client, 910004)
            client.cookies.clear()
            set_profile(engine, holder, fullName="زهرا موسوی", nationalId="0012345678")

            pdf_id = upload(client, "910001", f"cert:{SOURCE_ID}:1:pdf", PDF, "application/pdf", "cert.pdf")
            first = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:1", certificate=base_certificate(),
                file_refs={"pdf": pdf_id},
            ).json()["id"]
            second = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:2",
                certificate=base_certificate(legacy_id=2, serial="N-0002", full_code="", status="revoked",
                                             revoked_at="2026-05-01T08:00:00+00:00", event_ref="18", event_title="دورهٔ تلسکوپ"),
            ).json()["id"]
            third = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:3",
                certificate=base_certificate(legacy_id=3, serial="N-0003", full_code="", expires_on="1399/01/01", kind="batch"),
            ).json()["id"]

            # Anonymous and plain members are blocked at the API.
            assert client.get("/api/admin/certificates").status_code == 401
            member = bale_login(client, 910003)
            assert client.get("/api/admin/certificates").status_code == 403
            assert client.get(f"/api/admin/certificates/{first}").status_code == 403
            assert client.get(f"/api/admin/certificates/{first}/file").status_code == 403
            client.cookies.clear()

            assign_manager(client, manager)
            listing = client.get("/api/admin/certificates")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["source"] == "shared_server_database"
            assert body["total"] == 3 and body["can_revoke"] is False
            assert body["counts"] == {"issued": 2, "revoked": 1}
            by_id = {item["id"]: item for item in body["items"]}
            assert by_id[first]["effective_status"] == "issued" and by_id[first]["has_file"] is True
            assert by_id[second]["effective_status"] == "revoked" and by_id[second]["revoked_at"].startswith("2026-05-01")
            assert by_id[third]["effective_status"] == "expired" and by_id[third]["kind"] == "batch"
            assert by_id[first]["holder"] == {
                "account_id": holder, "bale_user_id": "910001", "display_name": "زهرا موسوی", "name_source": "profile",
            }
            for item in body["items"]:
                flattened = repr(item).lower()
                assert "0012345678" not in flattened
                assert "hash" not in flattened and "token" not in flattened and "phone" not in flattened
            assert {(event["event_ref"], event["count"]) for event in body["events"]} == {("17", 2), ("18", 1)}

            # Search and filters.
            assert [item["id"] for item in client.get("/api/admin/certificates?q=N-0002").json()["items"]] == [second]
            assert client.get("/api/admin/certificates?q=140501").json()["total"] == 1
            assert client.get("/api/admin/certificates?q=زهرا").json()["total"] == 3
            assert client.get("/api/admin/certificates?q=910001").json()["total"] == 3
            assert client.get("/api/admin/certificates?status=revoked").json()["total"] == 1
            assert client.get("/api/admin/certificates?status=expired").json()["total"] == 1
            assert client.get("/api/admin/certificates?status=issued").json()["total"] == 1
            assert client.get("/api/admin/certificates?event_ref=18").json()["total"] == 1
            assert client.get("/api/admin/certificates?kind=batch").json()["total"] == 1
            assert client.get("/api/admin/certificates?status=bogus").status_code == 422
            page = client.get("/api/admin/certificates?limit=2&offset=2").json()
            assert len(page["items"]) == 1 and page["has_more"] is False

            # Detail and file access.
            detail = client.get(f"/api/admin/certificates/{first}")
            assert detail.status_code == 200, detail.text
            data = detail.json()["certificate"]
            assert data["files"] == [{"slot": "pdf", "file_id": pdf_id}]
            assert data["issued_by_bale_user_id"] == "70001" and data["source_id"] == SOURCE_ID
            assert "content" not in data and "0012345678" not in repr(data)
            file_response = client.get(f"/api/admin/certificates/{first}/file")
            assert file_response.status_code == 200
            assert file_response.headers["content-type"] == "application/pdf"
            assert file_response.headers["content-disposition"].startswith('attachment; filename="N-0001.pdf"')
            assert file_response.headers["x-content-type-options"] == "nosniff"
            assert file_response.content == PDF
            assert client.get(f"/api/admin/certificates/{first}/file?slot=png").status_code == 404
            assert client.get(f"/api/admin/certificates/{second}/file").status_code == 404

            # Tampered identifiers leak nothing.
            assert client.get("/api/admin/certificates/not-a-uuid").status_code == 404
            assert client.get("/api/admin/certificates/00000000-0000-4000-8000-000000000000").status_code == 404
            assert client.get("/api/admin/certificates/00000000-0000-4000-8000-000000000000/file").status_code == 404
            assert client.get(f"/api/admin/certificates/{first}/file?slot=exe").status_code == 422
            # No panel-side mutation exists in this phase.
            assert client.post(f"/api/admin/certificates/{first}/revoke", json={}).status_code in {404, 405}
            assert client.delete(f"/api/admin/certificates/{first}").status_code in {404, 405}

            # Owner sees the same registry.
            client.cookies.clear()
            owner_login(client)
            assert client.get("/api/admin/certificates").json()["total"] == 3
            assert member != holder
    finally:
        engine.dispose()


def test_effective_status_and_jalali_expiry_helpers():
    record = CertificateRecord(status="issued", expires_on="۱۴۰۴/۱۲/۲۹")
    assert certificates_mod.effective_status(record, "1405/01/01") == "expired"
    assert certificates_mod.effective_status(record, "1404/12/29") == "issued"
    record.expires_on = "نامعتبر"
    assert certificates_mod.effective_status(record, "1405/01/01") == "issued"
    record.status = "revoked"
    assert certificates_mod.effective_status(record, "1405/01/01") == "revoked"
    today = certificates_mod.today_jalali()
    assert len(today) == 10 and today[4] == "/" and today[:2] == "14"


def test_recording_completion_kind_and_account_view_are_owner_scoped():
    """Phase 9.2: ``kind=recording`` (manual completion certificate from the bot centre)
    is mirrored like any other kind, and «گواهینامه‌های من» shows only the caller's rows."""
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            # Guest: no account → 401, nothing leaks.
            assert client.get("/api/account/certificates").status_code == 401

            holder = bale_login(client, 910001)
            holder_cookies = dict(client.cookies)
            client.cookies.clear()
            other = bale_login(client, 910002)
            other_cookies = dict(client.cookies)
            client.cookies.clear()
            assert holder != other

            # Unknown kind is rejected; nothing stored.
            bogus = submit(client, bale_user_id="910001", key=f"{SOURCE_ID}:21", certificate=base_certificate(legacy_id=21, kind="attendance_auto"))
            assert bogus.status_code == 422 and bogus.json()["detail"] == "invalid_certificate_kind"

            recording = submit(
                client, bale_user_id="910001", key=f"{SOURCE_ID}:22",
                certificate=base_certificate(
                    legacy_id=22, kind="recording", serial="NC-0022", full_code="1421/R22", event_ref="", event_title="",
                    title="پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی",
                ),
            )
            assert recording.status_code == 200, recording.text
            attendance = submit(client, bale_user_id="910001", key=f"{SOURCE_ID}:23", certificate=base_certificate(legacy_id=23, serial="NC-0023", full_code="1421/A23"))
            assert attendance.status_code == 200
            foreign = submit(
                client, bale_user_id="910002", key=f"{SOURCE_ID}:24",
                certificate=base_certificate(legacy_id=24, kind="recording", serial="NC-0024", full_code="1421/R24", holder_name="علی رضایی", status="revoked"),
            )
            assert foreign.status_code == 200
            with Session(engine) as db:
                assert db.scalar(select(func.count(CertificateRecord.id))) == 3

            # Holder sees exactly their two rows, with the recording kind distinct from the event kind.
            client.cookies.update(holder_cookies)
            mine = client.get("/api/account/certificates")
            assert mine.status_code == 200, mine.text
            body = mine.json()
            assert "no-store" in mine.headers["cache-control"]
            assert body["total"] == 2 and body["delivery"] == "bale_bot" and body["counts"] == {"issued": 2, "revoked": 0, "expired": 0}
            by_kind = {item["kind"]: item for item in body["items"]}
            assert set(by_kind) == {"recording", "event"}
            assert by_kind["recording"]["title"] == "پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی"
            assert by_kind["recording"]["event_ref"] == "" and by_kind["recording"]["effective_status"] == "issued"
            assert by_kind["recording"]["serial"] == "NC-0022" and by_kind["recording"]["has_file"] is False
            # No issuer / account identifiers and nothing from the other account.
            assert "issued_by_bale_user_id" not in by_kind["recording"] and "account_id" not in by_kind["recording"]
            assert "NC-0024" not in mine.text and "علی رضایی" not in mine.text and other not in mine.text
            client.cookies.clear()

            # The other account sees only its own (revoked) certificate with the real status.
            client.cookies.update(other_cookies)
            theirs = client.get("/api/account/certificates").json()
            assert theirs["total"] == 1 and theirs["items"][0]["serial"] == "NC-0024"
            assert theirs["items"][0]["effective_status"] == "revoked" and theirs["counts"]["revoked"] == 1
            assert "NC-0022" not in repr(theirs)
            client.cookies.clear()

            # Managers' panel filters the new kind like the others.
            owner_login(client)
            assert client.get("/api/admin/certificates?kind=recording").json()["total"] == 2
            assert client.get("/api/admin/certificates?kind=event").json()["total"] == 1
            assert client.get("/api/admin/certificates?kind=attendance_auto").status_code == 422
    finally:
        engine.dispose()
