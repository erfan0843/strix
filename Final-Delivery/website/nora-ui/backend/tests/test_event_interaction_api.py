"""Phase 8: event resources, Q&A, attendee reviews, reports and answer notifications.

In-memory SQLite only. Every access decision is asserted against the HTTP API (never
the UI): resource downloads by access level / publication / id swapping, question
ownership from the server session, review eligibility from real check-in rows,
moderation + audit, and the idempotent answer notification in the shared outbox.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import event_interaction  # noqa: E402
from backend.models import (  # noqa: E402
    AccountProfileRecord,
    AdminAuditEventRecord,
    EventQuestionRecord,
    PlatformIdentityRecord,
    UserNotificationRecord,
)

from test_event_registration_gate import (  # noqa: E402
    ORIGIN,
    create_published_event,
    create_published_form,
    gate_app,
    iso,
    update_event,
)
from test_workflows_api import (  # noqa: E402
    SERVICE_TOKEN,
    account_write_headers,
    bale_login,
    owner_login,
    owner_write_headers,
)

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def set_profile(engine, account_id: str, full_name: str) -> None:
    with Session(engine) as db:
        record = db.get(AccountProfileRecord, account_id)
        if record is None:
            record = AccountProfileRecord(account_id=account_id, fields={})
            db.add(record)
        record.fields = {**(record.fields or {}), "fullName": full_name}
        db.commit()


def register(client: TestClient, form_id: str, name: str) -> str:
    """Submit the event's free registration form as the signed-in account; return the response id."""
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    submitted = client.post(
        f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": name}}, headers=ORIGIN,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "accepted"
    mine = client.get("/api/account/registrations").json()["items"]
    assert mine, "registration must appear in the account's own list"
    return mine[0]["id"]


def interaction(client: TestClient, event_id: str) -> dict:
    response = client.get(f"/api/public/events/{event_id}/interaction")
    assert response.status_code == 200, response.text
    return response.json()


def audit_actions(engine) -> list[str]:
    with Session(engine) as db:
        return list(db.scalars(select(AdminAuditEventRecord.action).order_by(AdminAuditEventRecord.created_at)))


# ── pure rules ──


def test_upload_validation_rejects_dangerous_and_unknown_files():
    content_type, name, digest = event_interaction.validate_upload(PDF, "../../etc/passwd.pdf")
    assert content_type == "application/pdf" and name == "passwd.pdf" and len(digest) == 64
    assert event_interaction.safe_file_name("جزوهٔ جلسه ۱.PDF", "application/pdf") == "جزوهٔ جلسه ۱.pdf"
    assert event_interaction.safe_file_name("", "image/png") == "resource.png"
    for payload, label in ((b"MZ\x90\x00binary", "x.pdf"), (b"#!/bin/sh\necho", "x.txt"), (b"\x7fELF", "x.pdf")):
        try:
            event_interaction.validate_upload(payload, label)
        except event_interaction.InteractionError as error:
            assert error.code == "file_type_not_allowed" and error.status == 415
        else:
            raise AssertionError(f"{label} must be rejected")
    try:
        event_interaction.validate_upload(b"<html><script>alert(1)</script>", "page.html")
    except event_interaction.InteractionError as error:
        assert error.status == 415
    try:
        event_interaction.validate_upload(b"x" * (event_interaction.MAX_BYTES + 1), "big.pdf")
    except event_interaction.InteractionError as error:
        assert error.code == "file_too_large" and error.status == 413
    assert event_interaction.author_label("مینا رستمی") == "مینا ر."
    assert event_interaction.author_label("09120000000") == event_interaction.AUTHOR_LABEL_DEFAULT
    assert event_interaction.delivery_state("pending", 0) == "queued"
    assert event_interaction.delivery_state("pending", 2) == "retrying"
    assert event_interaction.delivery_state("delivered", 1) == "delivered"
    assert event_interaction.delivery_state("failed", 5) == "failed"
    assert event_interaction.body_hash("سلام  دنیا ") == event_interaction.body_hash("سلام دنیا")


# ── resources ──


def test_resource_downloads_are_decided_by_registration_and_attendance_on_the_server():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, version = create_published_event(owner, 0, startsAt=iso(timedelta(days=3)))
            other_event, version = create_published_event(owner, version, t="رویداد دیگر", startsAt=iso(timedelta(days=4)))
            form_id = create_published_form(owner, event_id=event_id, key="phase8-resource-form-0001")
            base = f"/api/admin/events/{event_id}/resources"

            # Metadata rows: a link (public) and a file (registered) that is still a draft.
            link = owner.post(base, json={"kind": "link", "title": "پیوند جلسه", "link_url": "https://example.org/live",
                                          "access": "public", "status": "published"}, headers=owner_write_headers(owner))
            assert link.status_code == 201, link.text
            bad_link = owner.post(base, json={"kind": "link", "title": "بد", "link_url": "javascript:alert(1)"},
                                  headers=owner_write_headers(owner))
            assert bad_link.status_code == 422 and bad_link.json()["detail"]["code"] == "invalid_link"
            created = owner.post(base, json={"title": "جزوهٔ جلسه", "description": "اسلایدها", "access": "registered"},
                                 headers=owner_write_headers(owner))
            assert created.status_code == 201, created.text
            resource_id = created.json()["id"]
            assert created.json()["status"] == "draft"
            unknown = owner.post(base, json={"title": "x", "file_url": "/tmp/x"}, headers=owner_write_headers(owner))
            assert unknown.status_code == 422 and unknown.json()["detail"]["code"] == "unexpected_fields"
            # Publishing a file row without bytes is refused.
            early = owner.put(f"{base}/{resource_id}", json={"status": "published"}, headers=owner_write_headers(owner))
            assert early.status_code == 409 and early.json()["detail"]["code"] == "resource_file_missing"

            # Upload rules: type sniffed from bytes, executables and oversize rejected, name sanitised.
            exe = owner.put(f"{base}/{resource_id}/file", content=b"MZ\x90\x00\x03", headers={**owner_write_headers(owner), "X-File-Name": "setup.pdf"})
            assert exe.status_code == 415
            html = owner.put(f"{base}/{resource_id}/file", content=b"<script>1</script>", headers={**owner_write_headers(owner), "X-File-Name": "x.html"})
            assert html.status_code == 415
            big = owner.put(f"{base}/{resource_id}/file", content=b"%PDF-" + b"0" * event_interaction.MAX_BYTES,
                            headers={**owner_write_headers(owner), "X-File-Name": "big.pdf"})
            assert big.status_code == 413
            uploaded = owner.put(f"{base}/{resource_id}/file", content=PDF,
                                 headers={**owner_write_headers(owner), "X-File-Name": quote("../..\\جزوه نهایی.exe.PDF")})
            assert uploaded.status_code == 200, uploaded.text
            assert uploaded.json()["file_name"] == "جزوه نهایی.exe.pdf"
            assert uploaded.json()["content_type"] == "application/pdf" and uploaded.json()["size"] == len(PDF)
            published = owner.put(f"{base}/{resource_id}", json={"status": "published"}, headers=owner_write_headers(owner))
            assert published.status_code == 200 and published.json()["live"] is True

            download = f"/api/public/events/{event_id}/resources/{resource_id}/download"

            # Guest: sees the row with an honest state, cannot download.
            guest = TestClient(app)
            view = interaction(guest, event_id)
            rows = {row["id"]: row for row in view["resources"]}
            assert rows[resource_id]["allowed"] is False and rows[resource_id]["reason"] == "login_required"
            assert rows[link.json()["id"]]["allowed"] is True and rows[link.json()["id"]]["link_url"] == "https://example.org/live"
            assert "link_url" not in rows[resource_id] and "content" not in rows[resource_id]
            denied = guest.get(download)
            assert denied.status_code == 401 and denied.json()["detail"]["reason"] == "login_required"

            # Signed in but not registered → 403 with the reason; a pending/waitlisted row is not enough.
            member = TestClient(app)
            member_id = bale_login(member, 93001)
            view = interaction(member, event_id)
            assert view["viewer"]["signed_in"] is True and view["viewer"]["participation"]["registered"] is False
            denied = member.get(download)
            assert denied.status_code == 403 and denied.json()["detail"]["reason"] == "registration_required"

            # Confirmed (free) registration → allowed; headers force a download and block sniffing.
            response_id = register(member, form_id, "مینا رستمی")
            view = interaction(member, event_id)
            assert view["viewer"]["participation"] == {"registered": True, "attended": False, "pending": False}
            ok = member.get(download)
            assert ok.status_code == 200 and ok.content == PDF
            assert ok.headers["content-disposition"].startswith('attachment; filename="')
            assert "filename*=UTF-8''" in ok.headers["content-disposition"]
            assert ok.headers["x-content-type-options"] == "nosniff" and "no-store" in ok.headers["cache-control"]
            assert ok.headers["x-nora-resource-access"] == "registered"

            # Access tightened to attendance → recomputed on the next request, no cache.
            changed = owner.put(f"{base}/{resource_id}", json={"access": "attended"}, headers=owner_write_headers(owner))
            assert changed.status_code == 200
            denied = member.get(download)
            assert denied.status_code == 403 and denied.json()["detail"]["reason"] == "attendance_required"
            checked = owner.post(f"/api/admin/attendance/responses/{response_id}/check-in", json={}, headers=owner_write_headers(owner))
            assert checked.status_code == 200, checked.text
            assert member.get(download).status_code == 200
            assert interaction(member, event_id)["viewer"]["participation"]["attended"] is True
            undone = owner.post(f"/api/admin/attendance/responses/{response_id}/undo-check-in", json={"reason": "آزمون فاز ۸"}, headers=owner_write_headers(owner))
            assert undone.status_code == 200
            assert member.get(download).status_code == 403

            # Staff-only level, id swapping across events, direct ids and unpublished rows.
            owner.put(f"{base}/{resource_id}", json={"access": "staff"}, headers=owner_write_headers(owner))
            assert member.get(download).status_code == 403
            assert owner.get(download).status_code == 200  # staff preview
            owner.put(f"{base}/{resource_id}", json={"access": "public"}, headers=owner_write_headers(owner))
            assert guest.get(download).status_code == 200
            assert guest.get(f"/api/public/events/{other_event}/resources/{resource_id}/download").status_code == 404
            assert guest.get(f"/api/public/events/{event_id}/resources/not-a-uuid/download").status_code == 404
            assert guest.get(f"/api/public/events/{event_id}/resources/00000000-0000-4000-8000-000000000000/download").status_code == 404
            scheduled = owner.put(f"{base}/{resource_id}", json={"publish_at": iso(timedelta(days=1))}, headers=owner_write_headers(owner))
            assert scheduled.status_code == 200 and scheduled.json()["live"] is False
            assert guest.get(download).status_code == 404
            assert resource_id not in {row["id"] for row in interaction(guest, event_id)["resources"]}
            staff_rows = {row["id"]: row for row in interaction(owner, event_id)["resources"]}
            assert staff_rows[resource_id]["status"] == "published" and staff_rows[resource_id]["published"] is False
            back = owner.put(f"{base}/{resource_id}", json={"publish_at": ""}, headers=owner_write_headers(owner))
            assert back.status_code == 200 and back.json()["live"] is True
            assert guest.get(download).status_code == 200

            # Logical removal: no download, not listed, row kept with reason; registration untouched.
            removed = owner.post(f"{base}/{resource_id}/remove", json={"reason": "نسخهٔ قدیمی"}, headers=owner_write_headers(owner))
            assert removed.status_code == 200 and removed.json()["status"] == "removed"
            assert guest.get(download).status_code == 404
            assert resource_id not in {row["id"] for row in interaction(guest, event_id)["resources"]}
            listed = owner.get(base + "?include_removed=true").json()["items"]
            assert any(row["id"] == resource_id and row["removed_reason"] == "نسخهٔ قدیمی" for row in listed)
            assert owner.put(f"{base}/{resource_id}", json={"title": "x"}, headers=owner_write_headers(owner)).status_code == 409
            assert member.get("/api/account/registrations").json()["items"][0]["id"] == response_id

            # Event itself unpublished → nothing public, even for a public link resource.
            paused = owner.post(f"/api/admin/content/events/{event_id}/status",
                                json={"status": "paused", "expected_version": owner.get(f"/api/admin/content/events/{event_id}").json()["version"]},
                                headers=owner_write_headers(owner))
            assert paused.status_code == 200, paused.text
            assert guest.get(f"/api/public/events/{event_id}/interaction").status_code == 404
            assert owner.get(f"/api/public/events/{event_id}/interaction").status_code == 200

            # Permissions: a plain account may not manage or list resources; audit trail recorded.
            assert member.get(base).status_code == 403
            assert member.post(base, json={"title": "x"}, headers=account_write_headers(member)).status_code == 403
            assert member.put(f"{base}/{resource_id}/file", content=PDF, headers=account_write_headers(member)).status_code == 403
            actions = audit_actions(engine)
            assert actions.count("event_resource.update") >= 5 and "event_resource.remove" in actions
            assert "event_resource.file" in actions and "event_resource.create" in actions
            with Session(engine) as db:
                access_change = db.scalar(
                    select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "event_resource.update")
                    .order_by(AdminAuditEventRecord.created_at).offset(1)
                )
                assert access_change is not None
                assert access_change.details["access_before"] == "registered" and access_change.details["access_after"] == "attended"
                assert access_change.actor_kind == "owner"
    finally:
        engine.dispose()


# ── questions ──


def test_questions_belong_to_the_event_and_the_session_and_are_moderated_with_audit():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, version = create_published_event(owner, 0, startsAt=iso(timedelta(days=3)))
            other_event, version = create_published_event(owner, version, t="رویداد دوم", startsAt=iso(timedelta(days=5)))
            ask = f"/api/account/events/{event_id}/questions"

            guest = TestClient(app)
            assert guest.post(ask, json={"body": "ساعت شروع دقیقاً چند است؟"}, headers=ORIGIN).status_code == 401
            view = interaction(guest, event_id)
            assert view["event"]["qa_open"] is True and view["questions"]["items"] == []

            asker = TestClient(app)
            asker_id = bale_login(asker, 93101)
            set_profile(engine, asker_id, "مینا رستمی")
            # Client-supplied identity fields are rejected outright.
            forged = asker.post(ask, json={"body": "ساعت شروع دقیقاً چند است؟", "account_id": "someone-else"}, headers=account_write_headers(asker))
            assert forged.status_code == 400
            short = asker.post(ask, json={"body": "؟"}, headers=account_write_headers(asker))
            assert short.status_code == 422 and short.json()["detail"]["code"] == "text_too_short"
            no_csrf = asker.post(ask, json={"body": "ساعت شروع دقیقاً چند است؟"}, headers=ORIGIN)
            assert no_csrf.status_code == 403
            asked = asker.post(ask, json={"body": "  ساعت شروع دقیقاً چند است؟\u0000 "}, headers=account_write_headers(asker))
            assert asked.status_code == 201, asked.text
            question = asked.json()
            assert question["status"] == "pending" and question["mine"] is True and question["author"] == "مینا ر."
            assert question["body"] == "ساعت شروع دقیقاً چند است؟" and "account_id" not in question
            dup = asker.post(ask, json={"body": "ساعت شروع دقیقاً  چند است؟"}, headers=account_write_headers(asker))
            assert dup.status_code == 409 and dup.json()["detail"]["code"] == "duplicate_question"
            missing = asker.post(f"/api/account/events/ev-does-not-exist/questions", json={"body": "پرسش برای رویداد ناموجود"}, headers=account_write_headers(asker))
            assert missing.status_code == 404

            # Pending question: only its author sees it (status shown), nobody else.
            assert interaction(asker, event_id)["questions"]["items"][0]["status"] == "pending"
            assert interaction(guest, event_id)["questions"]["items"] == []
            reader = TestClient(app)
            reader_id = bale_login(reader, 93102)
            assert interaction(reader, event_id)["questions"]["items"] == []
            assert interaction(reader, other_event)["questions"]["items"] == []

            # Flood control: at most 3 open questions per event per account.
            for text_body in ("آیا پذیرایی دارد؟", "پارکینگ هست؟"):
                assert asker.post(ask, json={"body": text_body}, headers=account_write_headers(asker)).status_code == 201
            capped = asker.post(ask, json={"body": "گواهی هم می‌دهید؟"}, headers=account_write_headers(asker))
            assert capped.status_code == 429 and capped.json()["detail"]["code"] == "too_many_open_questions"

            # Answering: wrong event → 404; non-staff → 403; staff answer publishes and queues one notification.
            admin_q = f"/api/admin/events/{event_id}/questions/{question['id']}"
            wrong = owner.post(f"/api/admin/events/{other_event}/questions/{question['id']}/answer",
                               json={"answer": "ساعت ده."}, headers=owner_write_headers(owner))
            assert wrong.status_code == 404
            assert reader.post(f"{admin_q}/answer", json={"answer": "ساعت ده."}, headers=account_write_headers(reader)).status_code == 403
            assert reader.get(f"/api/admin/events/{event_id}/questions").status_code == 403
            unanswered = owner.get("/api/admin/event-questions").json()
            assert unanswered["total"] == 3 and unanswered["items"][0]["event_title"].startswith("کارگاه")
            answered = owner.post(f"{admin_q}/answer", json={"answer": "ساعت ده صبح، سالن اصلی.", "official": True},
                                  headers=owner_write_headers(owner))
            assert answered.status_code == 200, answered.text
            body = answered.json()
            assert body["status"] == "published" and body["answer"] == "ساعت ده صبح، سالن اصلی." and body["answer_official"] is True
            notification_id = body["notification"]["id"]
            assert body["notification"]["state"] == "queued" and body["notification"]["has_bale_target"] is True
            public_q = interaction(guest, event_id)["questions"]["items"]
            assert len(public_q) == 1 and public_q[0]["answer"] == "ساعت ده صبح، سالن اصلی." and public_q[0]["mine"] is False
            assert "account_id" not in public_q[0] and public_q[0]["author"] == "مینا ر."
            assert owner.get("/api/admin/event-questions").json()["total"] == 2
            assert owner.get(f"/api/admin/events/{event_id}/questions?answered=true").json()["total"] == 1

            # Notification: appears in the asker's account, in the bot queue, with queued ≠ delivered.
            own = asker.get("/api/account/notifications").json()["items"]
            assert own[0]["id"] == notification_id and own[0]["kind"] == "event_qa_answer"
            assert own[0]["delivery_state"] == "queued" and own[0]["delivery_status"] == "pending"
            queue = owner.get("/api/bot/notifications/pending", headers=service_headers()).json()["items"]
            assert [item["id"] for item in queue] == [notification_id] and queue[0]["bale_user_id"] == "93101"
            # Five provider failures → failed; the answer is still there; resend re-queues the same row.
            for _ in range(5):
                failed = owner.post(f"/api/bot/notifications/{notification_id}/delivery-failed",
                                    json={"bale_user_id": "93101"}, headers=service_headers())
                assert failed.status_code == 200
            assert asker.get("/api/account/notifications").json()["items"][0]["delivery_state"] == "failed"
            assert interaction(guest, event_id)["questions"]["items"][0]["answer"] == "ساعت ده صبح، سالن اصلی."
            resent = owner.post(f"{admin_q}/resend-notification", headers=owner_write_headers(owner))
            assert resent.status_code == 200 and resent.json()["notification"]["id"] == notification_id
            assert resent.json()["notification"]["state"] == "retrying" and resent.json()["notification"]["attempts"] == 5
            # Editing the answer keeps the same outbox row (idempotency key = question.notification_id).
            edited = owner.post(f"{admin_q}/answer", json={"answer": "ساعت ده صبح، سالن اصلی (ورودی غربی)."}, headers=owner_write_headers(owner))
            assert edited.status_code == 200 and edited.json()["notification"]["id"] == notification_id
            with Session(engine) as db:
                assert db.scalar(select(func.count(UserNotificationRecord.id)).where(UserNotificationRecord.account_id == asker_id)) == 1
            delivered = owner.post(f"/api/bot/notifications/{notification_id}/delivered", json={"bale_user_id": "93101"}, headers=service_headers())
            assert delivered.status_code == 200
            assert asker.get("/api/account/notifications").json()["items"][0]["delivery_state"] == "delivered"
            again = owner.post(f"{admin_q}/resend-notification", headers=owner_write_headers(owner)).json()
            assert again["notification"]["state"] == "delivered"  # delivered rows are never re-queued

            # Reports: another user may report, the author may not; hiding resolves open reports.
            report = reader.post(f"/api/account/events/{event_id}/questions/{question['id']}/report",
                                 json={"reason": "تبلیغاتی"}, headers=account_write_headers(reader))
            assert report.status_code == 201 and report.json()["duplicate"] is False
            twice = reader.post(f"/api/account/events/{event_id}/questions/{question['id']}/report",
                                json={"reason": "باز هم"}, headers=account_write_headers(reader))
            assert twice.status_code == 201 and twice.json()["duplicate"] is True
            own_report = asker.post(f"/api/account/events/{event_id}/questions/{question['id']}/report", json={}, headers=account_write_headers(asker))
            assert own_report.status_code == 404
            assert interaction(reader, event_id)["questions"]["items"][0]["reported"] is True
            reports = owner.get("/api/admin/event-reports").json()
            assert reports["total"] == 1 and reports["items"][0]["target_kind"] == "question"
            assert owner.get("/api/admin/event-interaction/summary").json()["open_reports"] == 1
            no_reason = owner.post(f"{admin_q}/status", json={"status": "hidden"}, headers=owner_write_headers(owner))
            assert no_reason.status_code == 422
            hidden = owner.post(f"{admin_q}/status", json={"status": "hidden", "reason": "خارج از موضوع"}, headers=owner_write_headers(owner))
            assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"
            assert interaction(guest, event_id)["questions"]["items"] == []
            own_rows = {row["id"]: row for row in interaction(asker, event_id)["questions"]["items"]}
            assert own_rows[question["id"]]["status"] == "hidden" and len(own_rows) == 3
            assert owner.get("/api/admin/event-reports").json()["total"] == 0
            assert owner.get("/api/admin/event-reports?status=resolved").json()["items"][0]["resolution_note"] == "hidden"
            republished = owner.post(f"{admin_q}/status", json={"status": "published", "reason": ""}, headers=owner_write_headers(owner))
            assert republished.status_code == 200 and len(interaction(guest, event_id)["questions"]["items"]) == 1

            # Closing Q&A per event (content field) and cancellation both block new questions; reading still works.
            version = owner.get(f"/api/admin/content/events/{event_id}").json()["version"]
            version = update_event(owner, event_id, version, qaClosed=True)
            assert interaction(guest, event_id)["event"]["qa_open"] is False
            closed = reader.post(ask, json={"body": "هنوز می‌شود پرسید؟"}, headers=account_write_headers(reader))
            assert closed.status_code == 409 and closed.json()["detail"]["code"] == "qa_closed"
            assert len(interaction(guest, event_id)["questions"]["items"]) == 1
            version = update_event(owner, event_id, version, qaClosed=False, lifecycle="cancelled")
            cancelled = reader.post(ask, json={"body": "هنوز می‌شود پرسید؟"}, headers=account_write_headers(reader))
            assert cancelled.status_code == 409 and cancelled.json()["detail"]["reason"] == "cancelled"

            actions = audit_actions(engine)
            assert actions.count("event_question.answer") == 2 and actions.count("event_question.status") == 2
            assert actions.count("event_question.notification_resend") == 2
            with Session(engine) as db:
                stored = db.get(EventQuestionRecord, question["id"])
                assert stored is not None and stored.account_id == asker_id and stored.notification_id == notification_id
    finally:
        engine.dispose()


def test_answer_notification_for_web_only_account_fails_honestly_and_never_reaches_the_bot_queue():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, _version = create_published_event(owner, 0, startsAt=iso(timedelta(days=3)))
            asker = TestClient(app)
            asker_id = bale_login(asker, 93201)
            asked = asker.post(f"/api/account/events/{event_id}/questions", json={"body": "آیا ضبط می‌شود؟"}, headers=account_write_headers(asker))
            assert asked.status_code == 201
            # Simulate an account without any server-verified Bale identity (web-only sign-in).
            with Session(engine) as db:
                db.execute(delete(PlatformIdentityRecord).where(PlatformIdentityRecord.account_id == asker_id))
                db.commit()
            answered = owner.post(f"/api/admin/events/{event_id}/questions/{asked.json()['id']}/answer",
                                  json={"answer": "بله، ضبط می‌شود."}, headers=owner_write_headers(owner))
            assert answered.status_code == 200, answered.text
            note = answered.json()["notification"]
            assert note["state"] == "failed" and note["last_error"] == "no_bale_identity" and note["has_bale_target"] is False
            assert interaction(TestClient(app), event_id)["questions"]["items"][0]["answer"] == "بله، ضبط می‌شود."
            assert owner.get("/api/bot/notifications/pending", headers=service_headers()).json()["items"] == []
            assert owner.get("/api/admin/event-interaction/summary").json()["failed_notifications"] == 1
            own = asker.get("/api/account/notifications").json()["items"]
            assert own[0]["delivery_state"] == "failed" and own[0]["last_delivery_error"] == "no_bale_identity"
            assert own[0]["title"] == "پاسخ برگزارکننده به پرسش شما"
    finally:
        engine.dispose()


# ── reviews ──


def test_reviews_need_verified_attendance_have_no_rating_and_separate_submitted_from_published():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, version = create_published_event(owner, 0, startsAt=iso(timedelta(days=3)))
            other_event, version = create_published_event(owner, version, t="رویداد دوم", startsAt=iso(timedelta(days=5)))
            form_id = create_published_form(owner, event_id=event_id, key="phase8-review-form-00001")
            post = f"/api/account/events/{event_id}/reviews"

            member = TestClient(app)
            member_id = bale_login(member, 93301)
            set_profile(engine, member_id, "امید نادری")
            not_registered = member.post(post, json={"body": "کارگاه بسیار مفیدی بود و خوب برگزار شد."}, headers=account_write_headers(member))
            assert not_registered.status_code == 403 and not_registered.json()["detail"]["registered"] is False
            response_id = register(member, form_id, "امید نادری")
            not_attended = member.post(post, json={"body": "کارگاه بسیار مفیدی بود و خوب برگزار شد."}, headers=account_write_headers(member))
            assert not_attended.status_code == 403 and not_attended.json()["detail"]["reason"] == "attendance_required"
            assert not_attended.json()["detail"]["registered"] is True
            assert interaction(member, event_id)["reviews"]["eligible"] is False

            assert owner.post(f"/api/admin/attendance/responses/{response_id}/check-in", json={}, headers=owner_write_headers(owner)).status_code == 200
            assert interaction(member, event_id)["reviews"]["eligible"] is True
            rated = member.post(post, json={"body": "کارگاه بسیار مفیدی بود.", "rating": 5}, headers=account_write_headers(member))
            assert rated.status_code == 400  # no numeric rating exists
            posted = member.post(post, json={"body": "کارگاه بسیار مفیدی بود و خوب برگزار شد."}, headers=account_write_headers(member))
            assert posted.status_code == 201, posted.text
            review = posted.json()
            assert review["status"] == "pending" and review["verified_attendee"] is True and review["author"] == "امید ن."
            assert "rating" not in review and "stars" not in review
            second = member.post(post, json={"body": "یک دیدگاه دیگر برای همین رویداد."}, headers=account_write_headers(member))
            assert second.status_code == 409 and second.json()["detail"]["code"] == "review_exists"
            cross = member.post(f"/api/account/events/{other_event}/reviews", json={"body": "دیدگاه برای رویداد دیگر."}, headers=account_write_headers(member))
            assert cross.status_code == 403  # attendance is per event

            # Submitted ≠ published: pending is visible only to the author.
            guest = TestClient(app)
            assert interaction(guest, event_id)["reviews"]["items"] == []
            mine = interaction(member, event_id)["reviews"]
            assert mine["mine"]["status"] == "pending" and mine["items"][0]["mine"] is True
            assert owner.get("/api/admin/event-interaction/summary").json()["pending_reviews"] == 1
            admin_r = f"/api/admin/events/{event_id}/reviews/{review['id']}"
            assert member.post(f"{admin_r}/status", json={"status": "published"}, headers=account_write_headers(member)).status_code == 403
            approved = owner.post(f"{admin_r}/status", json={"status": "published"}, headers=owner_write_headers(owner))
            assert approved.status_code == 200 and approved.json()["status"] == "published"
            shown = interaction(guest, event_id)["reviews"]["items"]
            assert len(shown) == 1 and shown[0]["verified_attendee"] is True and shown[0]["author"] == "امید ن."
            assert "account_id" not in shown[0] and "response_id" not in shown[0]
            assert interaction(guest, other_event)["reviews"]["items"] == []

            # Author edits → back to pending (re-approval); audit of edits kept in counters.
            edited = member.put(f"{post}/{review['id']}", json={"body": "کارگاه بسیار مفیدی بود؛ فقط زمان استراحت کم بود."}, headers=account_write_headers(member))
            assert edited.status_code == 200 and edited.json()["status"] == "pending" and edited.json()["edited"] is True
            assert interaction(guest, event_id)["reviews"]["items"] == []
            owner.post(f"{admin_r}/status", json={"status": "published"}, headers=owner_write_headers(owner))
            assert len(interaction(guest, event_id)["reviews"]["items"]) == 1

            # Hide with reason+actor → gone everywhere public, author still sees the state, cannot edit.
            assert owner.post(f"{admin_r}/status", json={"status": "hidden"}, headers=owner_write_headers(owner)).status_code == 422
            hidden = owner.post(f"{admin_r}/status", json={"status": "hidden", "reason": "حاوی شمارهٔ تماس"}, headers=owner_write_headers(owner))
            assert hidden.status_code == 200 and hidden.json()["moderation_reason"] == "حاوی شمارهٔ تماس"
            assert interaction(guest, event_id)["reviews"]["items"] == []
            assert interaction(member, event_id)["reviews"]["mine"]["status"] == "hidden"
            locked = member.put(f"{post}/{review['id']}", json={"body": "ویرایش پس از پنهان شدن نباید ممکن باشد."}, headers=account_write_headers(member))
            assert locked.status_code == 409
            # Other users cannot touch it; withdraw keeps the row.
            stranger = TestClient(app)
            bale_login(stranger, 93302)
            assert stranger.put(f"{post}/{review['id']}", json={"body": "تلاش برای ویرایش دیدگاه دیگری."}, headers=account_write_headers(stranger)).status_code == 404
            assert stranger.post(f"{post}/{review['id']}/withdraw", headers=account_write_headers(stranger)).status_code == 404
            owner.post(f"{admin_r}/status", json={"status": "published"}, headers=owner_write_headers(owner))
            withdrawn = member.post(f"{post}/{review['id']}/withdraw", headers=account_write_headers(member))
            assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "withdrawn"
            assert interaction(guest, event_id)["reviews"]["items"] == []
            assert owner.get(f"/api/admin/events/{event_id}/reviews").json()["items"][0]["status"] == "withdrawn"
            assert owner.post(f"{admin_r}/status", json={"status": "published"}, headers=owner_write_headers(owner)).status_code == 409

            actions = audit_actions(engine)
            assert actions.count("event_review.status") == 4
    finally:
        engine.dispose()
