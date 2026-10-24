"""فاز ۹.۲ — گواهی «پایان محتوای آموزشی ضبط‌شده» از مسیر واقعی مرکز صدور (آفلاین).

* همان مسیر موجود: ``certcenter`` (طرح → نوع گواهی → قالب → گیرندهٔ دستی →
  انتشار → ساخت) و همان جدول ``certificates``؛ هیچ جدول یا مسیر موازی نیست.
* موتور ورد (``certgen.generate``) به LibreOffice نیاز دارد که در این محیط نیست؛
  فقط همان تابع با یک فایل PNG کوچک جایگزین می‌شود. بقیهٔ مسیر (ردیف گواهی،
  شمارهٔ یکتا، ستون source، ابطال، گزارش فعالیت و payload آینهٔ سرور) واقعی است.
* هیچ اتصال شبکه‌ای برقرار نمی‌شود؛ آینهٔ سرور با یک API جعلی در حافظه است.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

import bale_api  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import attendance  # noqa: E402
import certcenter as cc  # noqa: E402
import certgen  # noqa: E402
import shared_certificates as sc  # noqa: E402

# ادمین مجاز = یک کاربر با is_admin=1 (مستقل از SUPER_ADMIN_ID محیط تست مشترک)
ADMIN = 7200001
HOLDER, OTHER, STRANGER = 7201001, 7201002, 7201003
SENT: list[tuple] = []


def _fake_raw_call(method, params=None, **_kw):
    SENT.append((method, dict(params or {})))
    return {"ok": True, "result": {"message_id": len(SENT), "status": "member"}}


def _capture_send(cid, text, kb=None, *a, **k):
    SENT.append(("sendMessage", {"chat_id": cid, "text": text, "kb": kb}))
    return {"ok": True, "result": {"message_id": len(SENT)}}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    SENT.clear()
    monkeypatch.setattr(bale_api, "_raw_call", _fake_raw_call)
    monkeypatch.setattr(bale_api, "api_async", lambda m, p=None: {"ok": True})
    monkeypatch.setattr(bale_api, "send", _capture_send)
    monkeypatch.setattr(bale_api, "send_or_edit", _capture_send)
    database.close_db()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "cert.db"))
    database._conn = None
    database.init_db()
    attendance.init_attendance_tables()
    certgen.init_cert_tables()
    cc.init_tables()
    database.seed_default_settings()
    database.db_execute(
        "INSERT INTO users (bale_user_id, first_name, last_name, is_authenticated, is_admin) VALUES (?,?,?,1,1)",
        (ADMIN, "مدیر", "آزمایشی"))
    assert auth.is_admin(ADMIN) and not auth.is_admin(STRANGER)
    for uid, first in ((HOLDER, "مریم"), (OTHER, "رضا"), (STRANGER, "سارا")):
        database.db_execute(
            "INSERT INTO users (bale_user_id, first_name, last_name, is_authenticated, national_id) "
            "VALUES (?,?,?,1,?)", (uid, first, "آزمایشی", f"00{uid}"))
    # قالب آزمایشی: فقط یک ردیف؛ فایل واقعی ورد لازم نیست چون generate جایگزین می‌شود
    tid = database.db_execute(
        "INSERT INTO cert_templates (name, file_path, kind, is_active) VALUES (?,?,?,1)",
        ("قالب آزمایشی ۹.۲", str(tmp_path / "tpl.docx"), "docx"))
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def fake_generate(mapping, tpl, want=None):
        png = out_dir / f"{mapping.get('serial') or 'cert'}.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        return {"docx": None, "pdf": None, "png": str(png), "engine": "test", "error": ""}

    monkeypatch.setattr(certgen, "generate", fake_generate)
    monkeypatch.setattr(cc, "scan_template", lambda _tid: [])
    monkeypatch.setattr(cc, "template_fields", lambda _tid: ([], [], []))
    yield {"db": database, "template_id": tid}
    database.close_db()


def _actions(action):
    return [json.loads(r["action_data"] or "{}") for r in database.db_execute(
        "SELECT action_data FROM user_actions WHERE action_type=? ORDER BY id", (action,), fetch="all") or []]


def _texts():
    return [p.get("text", "") for m, p in SENT if m == "sendMessage"]


def test_recording_completion_is_a_distinct_kind_on_the_real_center_path(db):
    iid = cc.create_issue(ADMIN, "پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی", db["template_id"])
    assert cc.kind_of(cc.get_issue(iid)) == "general"           # پیش‌فرض = رفتار قبلی مرکز

    # نوع نامعتبر رد می‌شود و چیزی تغییر نمی‌کند
    cc.set_kind(ADMIN, ADMIN, iid, "attendance_auto")
    assert cc.kind_of(cc.get_issue(iid)) == "general"
    assert any("نامعتبر" in t for t in _texts())

    cc.set_kind(ADMIN, ADMIN, iid, "recording_completion")
    assert cc.kind_of(cc.get_issue(iid)) == "recording_completion"
    assert _actions("cert_issue_kind") == [{"issue": iid, "kind": "recording_completion"}]

    # گیرنده فقط دستی؛ خرید/تماشا هیچ ردیفی نمی‌سازد (هیچ منبع خودکاری خوانده نمی‌شود)
    cc.add_share(iid, uid=HOLDER)
    assert database.db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?", (iid,)) == 1

    ok, todo = cc.issue_ready(cc.get_issue(iid))
    assert ok, todo
    n, err = cc.publish(iid, notify=False)
    assert err == "" and n == 0
    cc._audit_publish(ADMIN, iid, "silent")
    audit = _actions("cert_issue_published")
    assert audit and audit[-1]["kind"] == "recording_completion" and audit[-1]["way"] == "silent"

    # پس از انتشار نوع قفل است
    cc.set_kind(ADMIN, ADMIN, iid, "general")
    assert cc.kind_of(cc.get_issue(iid)) == "recording_completion"

    share = cc.shares(iid)[0]
    cert, err = cc.build_one(iid, share["id"])
    assert err == "" and cert
    assert cert["source"] == "recording"                      # ≠ center / event
    assert cert["event_id"] is None                           # هیچ رویداد/حضوری به آن نمی‌چسبد
    assert cert["issued_by"] == ADMIN
    assert cert["full_code"] and cert["person_code"] and cert["serial"]
    assert int(cert["revoked"] or 0) == 0

    # صدور تکراری: همان ردیف، نه ردیف دوم
    again, err = cc.build_one(iid, share["id"])
    assert err == "" and again["id"] == cert["id"]
    assert database.db_scalar("SELECT COUNT(*) FROM certificates WHERE bale_user_id=?", (HOLDER,)) == 1
    assert database.db_scalar("SELECT COUNT(*) FROM attendance_records") == 0

    # آینهٔ سرور: kind=recording و عنوان = عنوان طرح (نه نام قالب)
    run = database.db_execute
    payload = sc.build_payload(run, sc.load_certificate(run, cert["id"]), source="bot", source_key="k")
    assert payload["kind"] == "recording"
    assert payload["title"] == "پایان دورهٔ ضبط‌شدهٔ نجوم مقدماتی"
    assert payload["event_ref"] == "" and payload["status"] == "issued"
    assert payload["issued_by_bale_user_id"] == str(ADMIN)

    # طرح عمومی همچنان source=center و kind=center می‌دهد (رفتار قبلی دست‌نخورده)
    gid = cc.create_issue(ADMIN, "گواهی عمومی", db["template_id"])
    cc.add_share(gid, uid=OTHER)
    cc.publish(gid, notify=False)
    general, err = cc.build_one(gid, cc.shares(gid)[0]["id"])
    assert err == "" and general["source"] == "center"
    assert sc.build_payload(run, sc.load_certificate(run, general["id"]), source="bot", source_key="k")["kind"] == "center"


def test_revoke_restore_and_unauthorized_paths(db):
    iid = cc.create_issue(ADMIN, "پایان محتوای ضبط‌شدهٔ تلسکوپ", db["template_id"])
    cc.set_kind(ADMIN, ADMIN, iid, "recording_completion")
    cc.add_share(iid, uid=HOLDER)
    cc.publish(iid, notify=False)
    share = cc.shares(iid)[0]

    # کاربر غیرمجاز: نه نوع را عوض می‌کند، نه ابطال می‌کند، نه گواهی دیگری را می‌گیرد
    cc.set_kind(STRANGER, STRANGER, iid, "general")
    assert cc.kind_of(cc.get_issue(iid)) == "recording_completion"
    cc.user_get(STRANGER, STRANGER, share["id"])
    assert any("برای شما نیست" in t for t in _texts())
    assert database.db_scalar("SELECT COUNT(*) FROM certificates") == 0

    # شناسهٔ نامعتبر
    cc.user_get(HOLDER, HOLDER, 999999)
    assert any("یافت نشد" in t for t in _texts())
    cc.revoke_share(ADMIN, ADMIN, 999999)
    assert any("گواهی ساخته‌شده‌ای" in t for t in _texts())

    # دارنده خودش دریافت می‌کند → یک ردیف
    cc.user_get(HOLDER, HOLDER, share["id"])
    cert = database.db_execute("SELECT * FROM certificates WHERE bale_user_id=?", (HOLDER,), fetch="one")
    assert cert and cert["source"] == "recording"

    # ابطال غیرمجاز اثری ندارد
    cc.revoke_share(STRANGER, STRANGER, share["id"])
    assert int(database.db_scalar("SELECT revoked FROM certificates WHERE id=?", (cert["id"],)) or 0) == 0

    # ابطال و بازگردانی توسط ادمین: ردیف حذف نمی‌شود؛ عامل/دلیل ثبت؛ آینه وضعیت تازه می‌گیرد
    synced: list[int] = []
    import shared_certificates as _sc
    original = _sc.sync_after_change
    _sc.sync_after_change = lambda cid: synced.append(int(cid))
    try:
        cc.revoke_share(ADMIN, ADMIN, share["id"])
        assert int(database.db_scalar("SELECT revoked FROM certificates WHERE id=?", (cert["id"],))) == 1
        run = database.db_execute
        assert sc.build_payload(run, sc.load_certificate(run, cert["id"]), source="bot", source_key="k")["status"] == "revoked"
        cc.revoke_share(ADMIN, ADMIN, share["id"], undo=True)
        assert int(database.db_scalar("SELECT revoked FROM certificates WHERE id=?", (cert["id"],))) == 0
    finally:
        _sc.sync_after_change = original
    assert synced == [cert["id"], cert["id"]]
    revoked = _actions("cert_revoked")
    restored = _actions("cert_restored")
    assert revoked[-1]["certificate"] == cert["id"] and revoked[-1]["reason"] == "cert_center_admin"
    assert restored[-1]["certificate"] == cert["id"]
    assert database.db_scalar("SELECT COUNT(*) FROM certificates") == 1
