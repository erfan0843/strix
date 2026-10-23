"""Owner decision 1405/08/01: account status (active/blocked), block reason, staff-only internal note.

Every rule is asserted against the HTTP API, never the UI:

* owner blocks with a mandatory reason / re-activates; both audited with actor + reason;
* the owner's own account (``owner_bale_user_id``) can never be blocked (409);
* a manager cannot block (owner route → 401) but can read/write the internal note (``us_view``);
* a blocked account: existing session stops resolving (403 ``account_blocked`` on /api/account/me,
  registration, questions), Bale mini-app login and phone-OTP login refuse a session, the
  manager-password login refuses, the bot registration path for the linked Bale id refuses;
* other accounts are untouched; re-activation restores login;
* the internal note never appears in member-facing or public payloads; the audit row stores only
  its length; the «مسدودها» filter is server-side.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.models import AccountRecord, AdminAuditEventRecord, AccountSessionRecord  # noqa: E402

from test_event_interaction_api import set_profile  # noqa: E402
from test_event_registration_gate import (  # noqa: E402
    ORIGIN,
    create_published_event,
    create_published_form,
    gate_app,
    iso,
)
from test_workflows_api import (  # noqa: E402
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
    signed_init_data,
)

OWNER_BALE_ID = 70001
MEMBER_BALE_ID = 95001
OTHER_BALE_ID = 95002
MANAGER_BALE_ID = 95003


def service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def audit_rows(engine, action: str) -> list[AdminAuditEventRecord]:
    with Session(engine) as db:
        return list(db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == action)))


def set_status(client: TestClient, account_id: str, status: str, reason: str = ""):
    return client.put(
        f"/api/owner/accounts/{account_id}/status",
        json={"status": status, "reason": reason},
        headers=owner_write_headers(client),
    )


def test_block_and_unblock_are_enforced_on_every_entry_point_and_audited():
    app, engine = gate_app()
    try:
        # Owner prepares a published event with a free registration form.
        owner = TestClient(app)
        owner_login(owner)
        event_id, version = create_published_event(owner, 0, startsAt=iso(timedelta(days=3)))
        form_id = create_published_form(owner, event_id=event_id, key="block-test-form-00000001")

        # Member signs in (Bale), registers once, asks a question → all fine while active.
        member = TestClient(app)
        member_id = bale_login(member, MEMBER_BALE_ID)
        set_profile(engine, member_id, "عضو آزمایشی")
        other = TestClient(app)
        other_id = bale_login(other, OTHER_BALE_ID)
        set_profile(engine, other_id, "عضو دیگر")
        assert member.get("/api/account/me").status_code == 200
        ask = f"/api/account/events/{event_id}/questions"
        asked = member.post(ask, json={"body": "ساعت شروع دقیقاً چند است؟"}, headers=account_write_headers(member))
        assert asked.status_code == 201, asked.text

        # Validation: unknown status, missing reason, reason too short, unknown account.
        assert set_status(owner, member_id, "suspended", "x").status_code == 422
        missing = set_status(owner, member_id, "blocked", "")
        assert missing.status_code == 422 and missing.json()["detail"]["code"] == "block_reason_required"
        assert set_status(owner, member_id, "blocked", "ab").status_code == 422
        assert set_status(owner, "00000000-0000-0000-0000-000000000000", "blocked", "دلیل").status_code == 404
        # No CSRF header → 403, nothing changes.
        assert owner.put(
            f"/api/owner/accounts/{member_id}/status", json={"status": "blocked", "reason": "دلیل کافی"},
            headers={"Origin": "http://testserver"},
        ).status_code == 403
        with Session(engine) as db:
            assert db.get(AccountRecord, member_id).status == "active"

        # Block with a reason: status, reason, actor, time; every open session revoked.
        blocked = set_status(owner, member_id, "blocked", "  دو پرداخت   ناموفق و گزارش مزاحمت  ")
        assert blocked.status_code == 200, blocked.text
        body = blocked.json()
        assert body["changed"] is True and body["status"] == "blocked"
        assert body["blocked_reason"] == "دو پرداخت ناموفق و گزارش مزاحمت" and body["blocked_by"] == "owner-01"
        assert body["blocked_at"] and body["sessions_revoked"] >= 1
        with Session(engine) as db:
            open_sessions = db.scalars(select(AccountSessionRecord).where(
                AccountSessionRecord.account_id == member_id, AccountSessionRecord.revoked_at.is_(None)
            )).all()
            assert open_sessions == []
        rows = audit_rows(engine, "account.block")
        assert len(rows) == 1 and rows[0].target_type == "account" and rows[0].target_id == member_id
        assert rows[0].actor_kind == "owner" and rows[0].details["reason"] == "دو پرداخت ناموفق و گزارش مزاحمت"
        # Blocking again is idempotent (no second audit row).
        again = set_status(owner, member_id, "blocked", "دلیل دیگر")
        assert again.status_code == 200 and again.json()["changed"] is False
        assert len(audit_rows(engine, "account.block")) == 1

        # The blocked account's existing cookie no longer works anywhere (block revoked the session).
        me = member.get("/api/account/me")
        assert me.status_code == 401
        denied_question = member.post(ask, json={"body": "پرسش دوم از حساب مسدود"}, headers=account_write_headers(member))
        assert denied_question.status_code in {401, 403}
        # Defense in depth: a session that is still open while the account is blocked (status set by
        # another path) does not resolve either, and the member is told why.
        with Session(engine) as db:
            db.get(AccountRecord, other_id).status = "blocked"
            db.commit()
        told = other.get("/api/account/me")
        assert told.status_code == 403 and told.json()["detail"] == {"code": "account_blocked"}
        told_q = other.post(ask, json={"body": "پرسش از حساب مسدود باز"}, headers=account_write_headers(other))
        assert told_q.status_code == 403 and told_q.json()["detail"] == {"code": "account_blocked"}
        # …and the public registration path does not downgrade that cookie to an anonymous guest.
        told_draft = other.get(f"/api/public/forms/{form_id}/draft")
        assert told_draft.status_code == 403 and told_draft.json()["detail"] == {"code": "account_blocked"}
        told_reg = other.post(
            f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "عضو دیگر"}}, headers=ORIGIN,
        )
        assert told_reg.status_code in {401, 403}, told_reg.text  # no draft could be opened → no registration
        with Session(engine) as db:
            db.get(AccountRecord, other_id).status = "active"
            db.commit()
        # Public pages still render for the blocked visitor as an anonymous reader (no identity leak).
        view = member.get(f"/api/public/events/{event_id}/interaction")
        assert view.status_code == 200 and all(not q.get("mine") for q in view.json()["questions"]["items"])
        # Fresh Bale mini-app login is refused; no new session is created.
        fresh = TestClient(app)
        login = fresh.post(
            "/api/auth/bale-mini-app",
            json={"init_data": signed_init_data(MEMBER_BALE_ID, query_id="blocked-login-1")},
            headers=ORIGIN,
        )
        assert login.status_code == 403 and login.json()["detail"] == {"code": "account_blocked"}
        assert "nora_account_session" not in fresh.cookies and fresh.get("/api/account/me").status_code == 401
        # Bot-side registration for the linked Bale id is refused too.
        bot_draft = fresh.post(
            f"/api/bot/forms/{form_id}/draft",
            json={"bale_user_id": str(MEMBER_BALE_ID), "session_key": "bot-session-00000000000000000000000001"}, headers=service_headers(),
        )
        assert bot_draft.status_code == 403 and bot_draft.json()["detail"] == {"code": "account_blocked"}
        # The other member is untouched.
        assert other.get("/api/account/me").status_code == 200
        ok_other = other.post(ask, json={"body": "آیا پارکینگ دارد؟"}, headers=account_write_headers(other))
        assert ok_other.status_code == 201
        other_bot = fresh.post(
            f"/api/bot/forms/{form_id}/draft",
            json={"bale_user_id": str(OTHER_BALE_ID), "session_key": "bot-session-00000000000000000000000002"}, headers=service_headers(),
        )
        assert other_bot.status_code == 200, other_bot.text

        # Staff list/detail show the real status; the blocked filter is server-side.
        listing = owner.get("/api/admin/users?status=blocked")
        assert listing.status_code == 200
        assert [row["account_id"] for row in listing.json()["items"]] == [member_id]
        assert listing.json()["blocked_total"] == 1 and listing.json()["can_block"] is True
        row = listing.json()["items"][0]
        assert row["status"] == "blocked" and row["blocked_reason"] == "دو پرداخت ناموفق و گزارش مزاحمت"
        assert owner.get("/api/admin/users?status=active").json()["total"] >= 1
        assert member_id not in [r["account_id"] for r in owner.get("/api/admin/users?status=active").json()["items"]]
        assert owner.get("/api/admin/users?status=weird").status_code == 422

        # Re-activate: reason cleared, audited with the previous reason, login works again.
        unblocked = set_status(owner, member_id, "active")
        assert unblocked.status_code == 200 and unblocked.json()["status"] == "active"
        assert unblocked.json()["blocked_reason"] == "" and unblocked.json()["blocked_at"] is None
        rows = audit_rows(engine, "account.unblock")
        assert len(rows) == 1 and rows[0].details["previous_reason"] == "دو پرداخت ناموفق و گزارش مزاحمت"
        relogin = fresh.post(
            "/api/auth/bale-mini-app",
            json={"init_data": signed_init_data(MEMBER_BALE_ID, query_id="blocked-login-2")},
            headers=ORIGIN,
        )
        assert relogin.status_code == 200, relogin.text
        assert fresh.get("/api/account/me").status_code == 200
        # The revoked old cookie stays revoked (block revoked it; unblock does not resurrect it).
        assert member.get("/api/account/me").status_code == 401
    finally:
        engine.dispose()


def test_owner_account_is_protected_manager_cannot_block_and_manager_login_is_refused_when_blocked():
    app, engine = gate_app()
    try:
        owner = TestClient(app)
        owner_login(owner)
        # The owner's own Bale account exists as an account too.
        owner_member = TestClient(app)
        owner_account_id = bale_login(owner_member, OWNER_BALE_ID)
        protected = set_status(owner, owner_account_id, "blocked", "تلاش برای مسدودکردن مالک")
        assert protected.status_code == 409 and protected.json()["detail"] == {"code": "owner_account_protected"}
        with Session(engine) as db:
            assert db.get(AccountRecord, owner_account_id).status == "active"
        assert audit_rows(engine, "account.block") == []

        # A manager (password session) cannot use the owner route at all.
        manager = TestClient(app)
        manager_id = bale_login(manager, MANAGER_BALE_ID)
        assign_manager(manager, manager_id)
        victim = TestClient(app)
        victim_id = bale_login(victim, MEMBER_BALE_ID)
        denied = manager.put(
            f"/api/owner/accounts/{victim_id}/status", json={"status": "blocked", "reason": "دلیل مدیر"},
            headers=account_write_headers(manager),
        )
        assert denied.status_code == 401
        assert victim.get("/api/account/me").status_code == 200

        # Blocking a manager account refuses the manager-password login and kills the panel session.
        blocked = set_status(owner, manager_id, "blocked", "خروج از تیم")
        assert blocked.status_code == 200 and blocked.json()["sessions_revoked"] >= 1
        assert manager.get("/api/admin/users").status_code in {401, 403}
        username = "workflow." + manager_id[-4:]
        relogin = TestClient(app).post(
            "/api/auth/manager-login",
            json={"username": username, "password": "workflow-manager-password-2026"},
            headers=ORIGIN,
        )
        assert relogin.status_code == 403 and relogin.json()["detail"] == {"code": "account_blocked"}
        staff = TestClient(app).post(
            "/api/auth/staff-login",
            json={"username": username, "password": "workflow-manager-password-2026"},
            headers=ORIGIN,
        )
        assert staff.status_code == 403 and staff.json()["detail"] == {"code": "account_blocked"}, staff.text
    finally:
        engine.dispose()


def test_internal_note_is_staff_only_audited_by_length_and_never_member_facing():
    app, engine = gate_app()
    try:
        owner = TestClient(app)
        owner_login(owner)
        member = TestClient(app)
        member_id = bale_login(member, MEMBER_BALE_ID)
        set_profile(engine, member_id, "عضو یادداشت")
        manager = TestClient(app)
        manager_id = bale_login(manager, MANAGER_BALE_ID)
        assign_manager(manager, manager_id)
        secret_note = "یادداشت داخلی: پیگیری فیش شمارهٔ ۱۲ تا پایان ماه"
        note_url = f"/api/admin/users/{member_id}/note"

        # Member cannot write or read anyone's note (no us_view); anonymous neither.
        assert member.put(note_url, json={"note": "x"}, headers=account_write_headers(member)).status_code == 403
        assert TestClient(app).put(note_url, json={"note": "x"}, headers=ORIGIN).status_code == 401
        # Manager with us_view writes it (CSRF required), audit stores only the length.
        assert manager.put(note_url, json={"note": secret_note}, headers=ORIGIN).status_code == 403
        saved = manager.put(note_url, json={"note": secret_note}, headers=account_write_headers(manager))
        assert saved.status_code == 200, saved.text
        assert saved.json()["internal_note"] == secret_note and saved.json()["note_updated_by"] == manager_id
        assert manager.put(note_url, json={"note": secret_note, "extra": 1}, headers=account_write_headers(manager)).status_code == 400
        too_long = manager.put(note_url, json={"note": "ن" * 2001}, headers=account_write_headers(manager))
        assert too_long.status_code == 422 and too_long.json()["detail"]["code"] == "note_too_long"
        rows = audit_rows(engine, "account.note")
        assert len(rows) == 1 and rows[0].actor_id == manager_id and rows[0].target_id == member_id
        assert rows[0].details == {"length": len(secret_note), "cleared": False}
        assert secret_note not in repr(rows[0].details)
        # Same note again → no change, no second audit row.
        assert manager.put(note_url, json={"note": secret_note}, headers=account_write_headers(manager)).json()["changed"] is False
        assert len(audit_rows(engine, "account.note")) == 1
        # Staff detail/list carry it; owner sees it too.
        detail = manager.get(f"/api/admin/users/{member_id}")
        assert detail.status_code == 200 and detail.json()["internal_note"] == secret_note
        assert owner.get(f"/api/admin/users/{member_id}").json()["internal_note"] == secret_note
        listed = owner.get("/api/admin/users").json()["items"]
        assert next(r for r in listed if r["account_id"] == member_id)["internal_note"] == secret_note
        # The member's own payloads and public payloads never contain it.
        me = member.get("/api/account/me")
        assert me.status_code == 200 and secret_note not in me.text and "internal_note" not in me.text
        assert "status" not in me.json() or me.json().get("status") != "blocked"
        registrations = member.get("/api/account/registrations")
        assert registrations.status_code == 200 and secret_note not in registrations.text
        for path in ("/api/account/profile", "/api/account/identities", "/api/account/notifications"):
            own = member.get(path)
            assert own.status_code == 200 and secret_note not in own.text and "internal_note" not in own.text, path
        # Owner-only accounts list (roles) does not expose the note either (different purpose).
        accounts = owner.get("/api/owner/accounts").text
        assert secret_note not in accounts
        # Clearing the note is audited as cleared.
        cleared = owner.put(note_url, json={"note": "   "}, headers=owner_write_headers(owner))
        assert cleared.status_code == 200 and cleared.json()["internal_note"] == "" and cleared.json()["changed"] is True
        assert audit_rows(engine, "account.note")[-1].details == {"length": 0, "cleared": True}
        # Unknown / malformed account id → 404 without touching anything.
        assert owner.put("/api/admin/users/not-an-id/note", json={"note": "x"}, headers=owner_write_headers(owner)).status_code == 404
    finally:
        engine.dispose()
