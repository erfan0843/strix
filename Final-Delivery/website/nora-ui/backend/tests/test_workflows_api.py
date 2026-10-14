from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AdminTaskRecord, Base, UserNotificationRecord  # noqa: E402
from backend.roles import ROLE_MANAGER, permissions_for_role  # noqa: E402
from backend.security import hash_password  # noqa: E402

BOT_TOKEN = "test-only-bale-token"
SERVICE_TOKEN = "test-only-bot-service-token"


def signed_init_data(user_id: int, *, query_id: str) -> str:
    now = int(time.time())
    fields = {
        "auth_date": str(now),
        "query_id": query_id,
        "user": json.dumps({"id": user_id, "first_name": "آزمایش"}, ensure_ascii=False, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode([*fields.items(), ("hash", signature)])


def workflow_app():
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


def bale_login(client: TestClient, user_id: int) -> str:
    response = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": signed_init_data(user_id, query_id=f"workflow-{user_id}")},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    return response.json()["account_id"]


def owner_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text


def service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def owner_write_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://testserver",
        "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
    }


def account_write_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://testserver",
        "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
    }


def assign_manager(client: TestClient, account_id: str) -> None:
    owner_login(client)
    response = client.put(
        f"/api/owner/accounts/{account_id}/role",
        json={"role": ROLE_MANAGER},
        headers=owner_write_headers(client),
    )
    assert response.status_code == 200, response.text
    username = "workflow." + account_id[-4:]
    password = "workflow-manager-password-2026"
    credentials = client.put(
        f"/api/owner/accounts/{account_id}/manager-credentials",
        json={"username": username, "password": password},
        headers=owner_write_headers(client),
    )
    assert credentials.status_code == 200, credentials.text
    client.cookies.delete("nora_session")
    client.cookies.delete("nora_csrf")
    manager_login = client.post(
        "/api/auth/manager-login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )
    assert manager_login.status_code == 200, manager_login.text


def submit_workflow(client: TestClient, *, kind: str, key: str, data: dict, user_id: int = 73421):
    return client.post(
        "/api/bot/workflows",
        headers=service_headers(),
        json={
            "bale_user_id": user_id,
            "kind": kind,
            "payload": data,
            "idempotency_key": key,
        },
    )


def test_bot_workflows_share_manager_web_inbox_and_user_notifications():
    app, engine = workflow_app()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, 73421)
            assign_manager(client, account_id)

            profile = {
                "full_name": "سارا رضایی",
                "mobile": "09120000000",
                "city": "تهران",
                "_legacy_profile_submission_id": 11,
                "_legacy_source_id": "12345678-1234-4234-9234-123456789012",
            }
            created = submit_workflow(client, kind="profile_review", key="profile-0001", data=profile)
            assert created.status_code == 200, created.text
            profile_task = created.json()["task"]
            assert created.json()["created"] is True
            assert profile_task["status"] == "pending"
            assert profile_task["payload"]["_legacy_profile_submission_id"] == 11
            assert profile_task["payload"]["_legacy_source_id"] == "12345678-1234-4234-9234-123456789012"

            replay = submit_workflow(client, kind="profile_review", key="profile-0001", data=profile)
            assert replay.status_code == 200
            assert replay.json()["created"] is False
            assert replay.json()["task"]["id"] == profile_task["id"]
            conflict = submit_workflow(
                client,
                kind="profile_review",
                key="profile-0001",
                data={"full_name": "نام متفاوت"},
            )
            assert conflict.status_code == 409

            receipt = submit_workflow(
                client,
                kind="receipt_review",
                key="receipt-0001",
                data={
                    "amount": 250000,
                    "currency": "IRR",
                    "event_title": "کارگاه داستان‌نویسی",
                    "ref_code": "PAY-2871",
                    "photo_file_id": "bale-file-reference",
                    "_legacy_receipt_id": 21,
                    "_legacy_source_id": "12345678-1234-4234-9234-123456789012",
                },
            )
            assert receipt.status_code == 200, receipt.text
            receipt_task = receipt.json()["task"]
            assert receipt_task["payload"]["_legacy_receipt_id"] == 21
            assert receipt_task["payload"]["_legacy_source_id"] == "12345678-1234-4234-9234-123456789012"

            inbox = client.get("/api/admin/inbox")
            assert inbox.status_code == 200, inbox.text
            tasks = {task["id"]: task for task in inbox.json()["items"]}
            assert {profile_task["id"], receipt_task["id"]} <= set(tasks)
            assert tasks[receipt_task["id"]]["payload"]["amount"] == 250000
            assert "receipt_approve" in permissions_for_role(ROLE_MANAGER)
            assert "finance" not in permissions_for_role(ROLE_MANAGER)

            reports = client.get("/api/admin/reports/summary?period=all")
            assert reports.status_code == 200, reports.text
            report_data = reports.json()
            assert report_data["source"] == "shared_server_database"
            assert report_data["reviews"]["total"] == 2
            assert report_data["reviews"]["by_kind"]["profile_review"]["pending"] == 1
            assert report_data["reviews"]["by_kind"]["receipt_review"]["pending"] == 1
            assert report_data["accounts"]["total"] == 1
            assert "250000" not in reports.text  # reports expose aggregates, never payment amounts
            assert "name" not in report_data and "payload" not in report_data
            invalid_period = client.get("/api/admin/reports/summary?period=custom")
            assert invalid_period.status_code == 422

            no_csrf = client.post(
                f"/api/admin/inbox/{profile_task['id']}/decision",
                json={"decision": "approved", "reason": "", "expected_version": 1},
                headers={"Origin": "http://testserver"},
            )
            assert no_csrf.status_code == 403
            cross_origin = client.post(
                f"/api/admin/inbox/{profile_task['id']}/decision",
                json={"decision": "approved", "reason": "", "expected_version": 1},
                headers={
                    "Origin": "https://attacker.example",
                    "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
                },
            )
            assert cross_origin.status_code == 403

            approved = client.post(
                f"/api/admin/inbox/{profile_task['id']}/decision",
                json={"decision": "approved", "reason": "", "expected_version": 1},
                headers=account_write_headers(client),
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["task"]["status"] == "approved"
            stale = client.post(
                f"/api/admin/inbox/{profile_task['id']}/decision",
                json={"decision": "rejected", "reason": "", "expected_version": 1},
                headers=account_write_headers(client),
            )
            assert stale.status_code == 409

            rejected = client.post(
                f"/api/admin/inbox/{receipt_task['id']}/decision",
                json={"decision": "rejected", "reason": "تصویر خوانا نیست", "expected_version": 1},
                headers=account_write_headers(client),
            )
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["task"]["status"] == "rejected"

            projection_queue = client.get("/api/bot/workflows/projection-pending", headers=service_headers())
            assert projection_queue.status_code == 200
            projection_ids = {item["id"] for item in projection_queue.json()["items"]}
            assert {profile_task["id"], receipt_task["id"]} <= projection_ids
            for projection_id in projection_ids:
                ack = client.post(
                    f"/api/bot/workflows/{projection_id}/projection-applied",
                    headers=service_headers(),
                )
                assert ack.status_code == 200 and ack.json()["applied"] is True
            assert client.get(
                "/api/bot/workflows/projection-pending", headers=service_headers()
            ).json()["items"] == []

            user_notifications = client.get("/api/account/notifications")
            assert user_notifications.status_code == 200, user_notifications.text
            notices = user_notifications.json()["items"]
            assert {notice["kind"] for notice in notices} == {"profile_approved", "receipt_rejected"}
            assert any("تصویر خوانا نیست" in notice["body"] for notice in notices)
            for notice in notices:
                marked = client.post(
                    f"/api/account/notifications/{notice['id']}/read",
                    headers=account_write_headers(client),
                )
                assert marked.status_code == 200
            assert all(item["read"] for item in client.get("/api/account/notifications").json()["items"])

            queued = client.get("/api/bot/notifications?bale_user_id=73421", headers=service_headers())
            assert queued.status_code == 200
            assert len(queued.json()["items"]) == 2
            for notice in queued.json()["items"]:
                delivered = client.post(
                    f"/api/bot/notifications/{notice['id']}/delivered",
                    headers=service_headers(),
                    json={"bale_user_id": 73421},
                )
                assert delivered.status_code == 200
            assert client.get("/api/bot/notifications?bale_user_id=73421", headers=service_headers()).json()["items"] == []

            with Session(engine) as db:
                assert db.scalar(select(AdminTaskRecord).where(AdminTaskRecord.id == profile_task["id"])).status == "approved"
                assert db.scalar(select(UserNotificationRecord).where(UserNotificationRecord.account_id == account_id)).delivery_status == "delivered"

            health = client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["workflowEnabled"] is True
            assert health.json()["notificationQueueEnabled"] is True
    finally:
        engine.dispose()


def test_admin_reports_require_a_server_assigned_report_permission():
    app, engine = workflow_app()
    try:
        with TestClient(app) as client:
            bale_login(client, 73422)
            denied = client.get("/api/admin/reports/summary")
            assert denied.status_code == 403
    finally:
        engine.dispose()


def test_bot_report_summary_uses_shared_data_and_server_role_only():
    app, engine = workflow_app()
    try:
        with TestClient(app) as client:
            request_body = {"bale_user_id": "73421", "period": "30d"}
            no_service = client.post("/api/bot/reports/summary", json=request_body)
            assert no_service.status_code == 401

            account_id = bale_login(client, 73421)
            unassigned = client.post(
                "/api/bot/reports/summary", headers=service_headers(), json=request_body
            )
            assert unassigned.status_code == 403

            assign_manager(client, account_id)
            receipt = submit_workflow(
                client,
                kind="receipt_review",
                key="bot-report-receipt-1",
                data={"amount": 987654, "currency": "IRR", "event_title": "رویداد"},
            )
            assert receipt.status_code == 200, receipt.text

            report = client.post(
                "/api/bot/reports/summary",
                headers=service_headers(),
                json=request_body,
            )
            assert report.status_code == 200, report.text
            data = report.json()
            assert data["source"] == "shared_server_database"
            assert data["period"] == "30d"
            assert data["reviews"]["by_kind"]["receipt_review"]["pending"] == 1
            assert "987654" not in report.text
            assert "payload" not in data and "account_id" not in data
            assert "no-store" in report.headers["cache-control"]

            invalid_period = client.post(
                "/api/bot/reports/summary",
                headers=service_headers(),
                json={"bale_user_id": "73421", "period": "custom"},
            )
            assert invalid_period.status_code == 422
            today_report = client.post(
                "/api/bot/reports/summary",
                headers=service_headers(),
                json={"bale_user_id": "73421", "period": "today"},
            )
            assert today_report.status_code == 200, today_report.text
            assert today_report.json()["reviews"]["total"] == 1
            invalid_body = client.post(
                "/api/bot/reports/summary",
                headers=service_headers(),
                json={**request_body, "include_users": True},
            )
            assert invalid_body.status_code == 400
    finally:
        engine.dispose()


def test_bot_workflow_endpoints_require_service_identity_permission_and_supersede_profile():
    app, engine = workflow_app()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, 73422)
            unauthenticated = client.post(
                "/api/bot/workflows",
                json={
                    "bale_user_id": 73422,
                    "kind": "profile_review",
                    "payload": {"full_name": "کاربر"},
                    "idempotency_key": "profile-no-auth",
                },
            )
            assert unauthenticated.status_code == 401

            first = submit_workflow(
                client,
                kind="profile_review",
                key="profile-revise-1",
                data={"full_name": "نام قبلی"},
                user_id=73422,
            )
            assert first.status_code == 200
            second = submit_workflow(
                client,
                kind="profile_review",
                key="profile-revise-2",
                data={"full_name": "نام تازه"},
                user_id=73422,
            )
            assert second.status_code == 200
            with Session(engine) as db:
                earlier = db.get(AdminTaskRecord, first.json()["task"]["id"])
                latest = db.get(AdminTaskRecord, second.json()["task"]["id"])
                assert earlier.status == "superseded"
                assert latest.status == "pending"

            assert client.get(
                "/api/bot/inbox?bale_user_id=73422", headers=service_headers()
            ).status_code == 403
            denied = client.post(
                f"/api/bot/workflows/{second.json()['task']['id']}/decision",
                headers=service_headers(),
                json={
                    "bale_user_id": 73422,
                    "decision": "approved",
                    "reason": "",
                    "expected_version": 1,
                },
            )
            assert denied.status_code == 403
            assert client.get("/api/bot/inbox?bale_user_id=73422").status_code == 401

            stranger = bale_login(client, 73423)
            assert stranger != account_id
            assert client.get("/api/account/notifications").status_code == 200
            assert client.get("/api/account/notifications").json()["items"] == []
    finally:
        engine.dispose()


def test_private_file_upload_is_idempotent_and_visible_only_through_authorized_routes():
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII="
    )
    app, engine = workflow_app()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, 73424)
            assign_manager(client, account_id)
            upload_headers = {
                **service_headers(),
                "X-Bale-User-Id": "73424",
                "X-File-Name": "profile.png",
                "Idempotency-Key": "profile-file:profile:73424:one",
                "Content-Type": "image/png",
            }
            uploaded = client.post("/api/bot/files", content=png, headers=upload_headers)
            assert uploaded.status_code == 200, uploaded.text
            file_id = uploaded.json()["id"]
            assert uploaded.json()["created"] is True
            replay = client.post("/api/bot/files", content=png, headers=upload_headers)
            assert replay.status_code == 200 and replay.json()["created"] is False
            pdf = b"%PDF-1.7\\nprivate receipt test\\n%%EOF\\n"
            pdf_upload = client.post(
                "/api/bot/files",
                content=pdf,
                headers={
                    **service_headers(),
                    "X-Bale-User-Id": "73424",
                    "X-File-Name": "receipt.pdf",
                    "Idempotency-Key": "receipt-file:profile:73424:one",
                    "Content-Type": "application/pdf",
                },
            )
            assert pdf_upload.status_code == 200, pdf_upload.text
            pdf_file_id = pdf_upload.json()["id"]
            assert pdf_upload.json()["content_type"] == "application/pdf"
            conflict = client.post(
                "/api/bot/files",
                content=b"not a PNG",
                headers={**upload_headers, "Content-Type": "application/octet-stream"},
            )
            assert conflict.status_code == 415

            task = submit_workflow(
                client,
                kind="profile_review",
                key="profile-with-photo-1",
                data={"full_name": "کاربر همراه تصویر", "file_refs": [file_id, pdf_file_id]},
                user_id=73424,
            )
            assert task.status_code == 200, task.text
            task_id = task.json()["task"]["id"]
            inbox = client.get("/api/admin/inbox")
            assert inbox.status_code == 200, inbox.text
            inbox_task = next(item for item in inbox.json()["items"] if item["id"] == task_id)
            listed_task_files = {item["id"]: item for item in inbox_task["files"]}
            assert listed_task_files == {
                file_id: {"id": file_id, "file_name": "profile.png", "content_type": "image/png", "content_size": len(png)},
                pdf_file_id: {"id": pdf_file_id, "file_name": "receipt.pdf", "content_type": "application/pdf", "content_size": len(pdf)},
            }
            task_file = client.get(f"/api/admin/inbox/{task_id}/files/{file_id}")
            assert task_file.status_code == 200
            assert task_file.headers["content-type"].startswith("image/png")
            assert task_file.content == png
            task_pdf = client.get(f"/api/admin/inbox/{task_id}/files/{pdf_file_id}")
            assert task_pdf.status_code == 200 and task_pdf.content == pdf
            assert task_pdf.headers["content-type"].startswith("application/pdf")
            assert "attachment" in task_pdf.headers["content-disposition"]
            # Account web exposes metadata only; user delivery has moved to Bale.
            own_file = client.get(f"/api/account/files/{file_id}")
            assert own_file.status_code == 410
            assert own_file.json()["detail"] == "file_delivery_via_bale_bot"
            own_pdf = client.get(f"/api/account/files/{pdf_file_id}")
            assert own_pdf.status_code == 410
            assert own_pdf.json()["detail"] == "file_delivery_via_bale_bot"
            # The manager's review attachment route remains intact and serves the exact bytes.
            assert client.get(f"/api/admin/inbox/{task_id}/files/{file_id}").content == png
            assert client.get(f"/api/admin/inbox/{task_id}/files/{pdf_file_id}").content == pdf
            # Only the authenticated bot service can list or fetch files for delivery.
            bot_files = client.get("/api/bot/files?bale_user_id=73424", headers=service_headers())
            assert bot_files.status_code == 200
            assert {item["id"] for item in bot_files.json()["items"]} == {file_id, pdf_file_id}
            bot_pdf = client.get(f"/api/bot/files/{pdf_file_id}", headers=service_headers())
            assert bot_pdf.status_code == 200 and bot_pdf.content == pdf
            assert "attachment" in bot_pdf.headers["content-disposition"]
            assert client.get("/api/bot/files?bale_user_id=73424").status_code == 401
            account_files = client.get("/api/account/files")
            assert account_files.status_code == 200
            assert "no-store" in account_files.headers["cache-control"]
            listed = {item["id"]: item for item in account_files.json()["items"]}
            assert set(listed) == {file_id, pdf_file_id}
            assert listed[file_id]["task_id"] == task_id and listed[pdf_file_id]["task_id"] == task_id
            assert listed[file_id]["file_name"] == "profile.png" and listed[file_id]["content_type"] == "image/png"
            assert listed[pdf_file_id]["file_name"] == "receipt.pdf" and listed[pdf_file_id]["content_type"] == "application/pdf"
            assert all("content" not in item and "content_hash" not in item for item in listed.values())

            with TestClient(app) as stranger:
                bale_login(stranger, 73425)
                assert stranger.get("/api/account/files").json()["items"] == []
                assert stranger.get(f"/api/account/files/{file_id}").status_code == 404
                assert stranger.get(f"/api/admin/inbox/{task_id}/files/{file_id}").status_code == 403

            unauthenticated = client.post(
                "/api/bot/files",
                content=png,
                headers={"X-Bale-User-Id": "73424", "Idempotency-Key": "no-service", "Content-Type": "image/png"},
            )
            assert unauthenticated.status_code == 401
    finally:
        engine.dispose()
