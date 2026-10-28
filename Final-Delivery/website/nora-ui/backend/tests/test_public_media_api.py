"""Public images uploaded from the managers' panel (``/api/admin/media``).

In-memory SQLite only. Covers: real content sniffing (renamed executables,
SVG/HTML, truncated images rejected regardless of extension and Content-Type),
size limit, safe naming, dedupe, stable public URL + caching headers, usage
detection against ``site_content``, in-use delete refusal, audit rows,
owner/manager-password/member/anonymous permission matrix and CSRF.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import public_media  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AdminAuditEventRecord, Base, PublicMediaRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
)

ORIGIN = {"Origin": "http://testserver"}
MANAGER_PASSWORD = "Str0ng-manager-passphrase-2026"


def media_app():
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


def image_bytes(fmt: str, size=(64, 48), color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def upload(client, content: bytes, *, name="poster.png", content_type="image/png", headers=None):
    return client.post(
        "/api/admin/media",
        content=content,
        headers={**(headers or owner_write_headers(client)), "X-File-Name": name, "Content-Type": content_type},
    )


def manager_password_login(client: TestClient, account_id: str) -> None:
    """Owner assigns the manager role + password; the client ends up logged in through the password path."""
    assign_manager(client, account_id)


def test_inspect_image_rejects_disguised_and_broken_files():
    png = image_bytes("PNG")
    info = public_media.inspect_image(png)
    assert (info.content_type, info.width, info.height) == ("image/png", 64, 48)
    assert public_media.inspect_image(image_bytes("JPEG")).content_type == "image/jpeg"
    assert public_media.inspect_image(image_bytes("WEBP")).content_type == "image/webp"

    def code(content: bytes) -> str:
        try:
            public_media.inspect_image(content)
        except public_media.MediaError as error:
            return error.code
        return "accepted"

    assert code(b"") == "empty_image"
    assert code(b"MZ\x90\x00" + b"\x00" * 200) == "unsupported_image_type"  # Windows executable
    assert code(b"\x7fELF" + b"\x00" * 200) == "unsupported_image_type"
    assert code(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>") == "unsupported_image_type"
    assert code(b"<!doctype html><script>alert(1)</script>") == "unsupported_image_type"
    assert code(b"GIF89a" + b"\x00" * 64) == "unsupported_image_type"  # animated/active formats not accepted
    assert code(b"%PDF-1.4 ...") == "unsupported_image_type"
    assert code(png[:40]) == "invalid_image"  # PNG magic but truncated body
    assert code(b"\x89PNG\r\n\x1a\n" + b"<script>" * 20) == "invalid_image"  # forged magic bytes
    assert code(image_bytes("PNG", size=(8, 8))) == "image_too_small"
    assert code(b"\xff\xd8\xff" + b"\x00" * (public_media.MAX_BYTES + 1)) == "image_too_large"

    assert public_media.safe_name("../../etc/passwd.exe", "image/png") == "passwd.png"
    assert public_media.safe_name("پوستر رویداد.JPG", "image/jpeg") == "image.jpg"
    assert public_media.safe_name("Poster Final (v2).png", "image/webp") == "Poster_Final_v2.webp"
    assert public_media.parse_id("00000000-0000-4000-8000-000000000000'; drop") is None


def test_upload_list_public_serving_usage_and_delete_policy():
    app, engine = media_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            png = image_bytes("PNG")

            # Declared type and extension lie; the bytes decide.
            created = upload(client, png, name="poster.exe", content_type="application/octet-stream")
            assert created.status_code == 201, created.text
            body = created.json()
            media_id = body["id"]
            assert body["created"] is True and body["source"] == "shared_server_database"
            assert body["url"] == f"/api/public/media/{media_id}"
            assert body["content_type"] == "image/png" and body["width"] == 64 and body["height"] == 48
            assert body["file_name"] == "poster.png"
            assert "content" not in body and "hash" not in repr(body).lower()

            # Same bytes again: no second copy, same stable URL.
            again = upload(client, png, name="other-name.png")
            assert again.status_code == 201
            assert again.json()["id"] == media_id and again.json()["created"] is False
            with Session(engine) as db:
                assert db.scalar(select(PublicMediaRecord).where(PublicMediaRecord.id == media_id)) is not None
                assert len(db.scalars(select(PublicMediaRecord)).all()) == 1

            # Disguised executable / active content / oversized bodies never land.
            for payload, expected in (
                (b"MZ\x90\x00" + b"\x00" * 100, 415),
                (b"<svg xmlns='http://www.w3.org/2000/svg'/>", 415),
                (png[:40], 422),
                (b"", 422),
            ):
                rejected = upload(client, payload, name="x.png", content_type="image/png")
                assert rejected.status_code == expected, (payload[:12], rejected.text)
            oversized = upload(client, b"\xff\xd8\xff" + b"\x00" * public_media.MAX_BYTES, name="big.jpg", content_type="image/jpeg")
            assert oversized.status_code == 413
            with Session(engine) as db:
                assert len(db.scalars(select(PublicMediaRecord)).all()) == 1

            # Public serving: anonymous, immutable cache, no sniffing, 304 on ETag, nothing for bad ids.
            client.cookies.clear()
            served = client.get(f"/api/public/media/{media_id}")
            assert served.status_code == 200
            assert served.headers["content-type"] == "image/png"
            assert served.content == png
            assert "immutable" in served.headers["cache-control"]
            assert served.headers["x-content-type-options"] == "nosniff"
            assert "sandbox" in served.headers["content-security-policy"]
            assert served.headers["content-disposition"] == 'inline; filename="poster.png"'
            etag = served.headers["etag"]
            assert client.get(f"/api/public/media/{media_id}", headers={"If-None-Match": etag}).status_code == 304
            assert client.get("/api/public/media/not-a-uuid").status_code == 404
            assert client.get("/api/public/media/00000000-0000-4000-8000-000000000000").status_code == 404
            assert client.get(f"/api/public/media/{media_id.upper()}").status_code == 200

            # Usage detection: the URL saved into an event poster marks the media as in use.
            owner_login(client)
            listing = client.get("/api/admin/media")
            assert listing.status_code == 200
            assert listing.json()["total"] == 1 and listing.json()["items"][0]["in_use"] is False
            assert listing.json()["unused"] == 1 and listing.json()["max_bytes"] == public_media.MAX_BYTES

            event = client.post(
                "/api/admin/content/events",
                json={"record": {"t": "رویداد با پوستر", "poster": body["url"], "d": "توضیح", "on": "۱۴۰۵/۰۸/۱۲"}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert event.status_code == 200, event.text
            assert event.json()["record"]["poster"] == body["url"]
            event_id = event.json()["record"]["id"]
            item = client.get("/api/admin/media").json()["items"][0]
            assert item["in_use"] is True and item["used_in"] == 1

            blocked = client.delete(f"/api/admin/media/{media_id}", headers=owner_write_headers(client))
            assert blocked.status_code == 409
            assert blocked.json()["detail"] == {"code": "media_in_use", "used_in": 1}
            assert client.get(f"/api/public/media/{media_id}").status_code == 200

            # Published event projects the stable URL to the public document.
            published = client.post(
                f"/api/admin/content/events/{event_id}/status",
                json={"status": "published", "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            public_events = client.get("/api/public/site-content").json()["content"]["events"]
            assert public_events[0]["poster"] == body["url"]

            # Remove the reference, then an explicit delete is allowed and audited.
            cleared = client.put(
                f"/api/admin/content/events/{event_id}",
                json={"record": {"poster": ""}, "expected_version": 2},
                headers=owner_write_headers(client),
            )
            assert cleared.status_code == 200, cleared.text
            assert client.get("/api/admin/media").json()["items"][0]["in_use"] is False
            assert client.delete(f"/api/admin/media/{media_id}", headers=ORIGIN).status_code == 403  # CSRF
            deleted = client.delete(f"/api/admin/media/{media_id}", headers=owner_write_headers(client))
            assert deleted.status_code == 200 and deleted.json() == {"deleted": True, "id": media_id}
            assert client.get(f"/api/public/media/{media_id}").status_code == 404
            assert client.delete(f"/api/admin/media/{media_id}", headers=owner_write_headers(client)).status_code == 404

            with Session(engine) as db:
                rows = db.scalars(
                    select(AdminAuditEventRecord).where(AdminAuditEventRecord.action.like("media.%"))
                ).all()
                actions = [(row.action, row.outcome) for row in rows]
                assert ("media.upload", "ok") in actions
                assert ("media.upload", "rejected") in actions
                assert ("media.delete", "ok") in actions
                for row in rows:
                    assert "content" not in row.details and row.actor_id == "owner-01"
    finally:
        engine.dispose()


def test_media_permission_matrix_and_csrf():
    app, engine = media_app()
    try:
        with TestClient(app) as client:
            png = image_bytes("PNG", color=(10, 90, 200))
            # Anonymous: nothing.
            assert client.post("/api/admin/media", content=png, headers={**ORIGIN, "Content-Type": "image/png"}).status_code == 401
            assert client.get("/api/admin/media").status_code == 401

            # Plain member (no permissions): blocked at the API.
            member = bale_login(client, 910003)
            assert member
            assert upload(client, png, headers=account_write_headers(client)).status_code == 403
            assert client.get("/api/admin/media").status_code == 403
            client.cookies.clear()

            # Manager via Bale session only (no password): blocked; via manager password: allowed.
            manager = bale_login(client, 910004)
            manager_password_login(client, manager)
            missing_csrf = client.post("/api/admin/media", content=png, headers={**ORIGIN, "Content-Type": "image/png"})
            assert missing_csrf.status_code == 403
            created = upload(client, png, name="cover.png", headers=account_write_headers(client))
            assert created.status_code == 201, created.text
            media_id = created.json()["id"]
            listing = client.get("/api/admin/media")
            assert listing.status_code == 200 and listing.json()["total"] == 1
            assert client.delete(f"/api/admin/media/{media_id}", headers=account_write_headers(client)).status_code == 200
            with Session(engine) as db:
                audit = db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "media.upload")).all()
                assert audit and audit[0].actor_id == manager and audit[0].actor_role == "manager"
            client.cookies.clear()

            # Manager through a Bale session alone (no password) must not pass.
            bale_only = bale_login(client, 910005)
            owner_login(client)
            assert client.put(
                f"/api/owner/accounts/{bale_only}/role", json={"role": "manager"}, headers=owner_write_headers(client),
            ).status_code == 200
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            denied = client.get("/api/admin/media")
            assert denied.status_code == 403 and denied.json()["detail"] == "manager_password_required"
    finally:
        engine.dispose()
