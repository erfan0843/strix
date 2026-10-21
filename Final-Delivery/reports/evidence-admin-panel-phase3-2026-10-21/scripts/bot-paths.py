"""مسیرهای ربات بله روی سرور آزمایشی محلی با کد واقعی ربات؛ فقط حساب‌های آزمایشی.

* ارسال به سرویس بله (bale_api.api) با یک stub ضبط‌کننده جایگزین می‌شود: این محیط به
  سرویس بله دسترسی ندارد و هیچ پیامی به هیچ کاربری نمی‌رود. بنابراین «تحویل واقعی
  اعلان در بله» آزموده‌نشده می‌ماند و فقط مسیر کد + ثبت وضعیت در سرور آزموده می‌شود.
* پایگاه ربات: کپی پایگاه مصنوعی (/tmp/qa/p3/bale/bot.db)؛ پایگاه عملیاتی لمس نمی‌شود.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

BOT_ROOT = Path("/home/user/strix/Final-Delivery/bale-bot/nora_bot")
WEB_ROOT = Path("/home/user/strix/Final-Delivery/website")
B = "http://127.0.0.1:8000"
OUT = Path("/tmp/qa/p3/bale")
MANAGER_UID = 910777   # مدیر آزمایشی (نقش manager + رمز مدیر؛ هویت بله)
MEMBER_UID = 910778    # عضو آزمایشی (دارندهٔ بلیت و درخواست کارتابل)

os.environ["NORA_SHARED_API_URL"] = B
os.environ["DB_PATH"] = str(OUT / "bot.db")
os.environ.setdefault("BOT_TOKEN", "test-only-not-a-real-token")
assert os.environ.get("NORA_BOT_SERVICE_TOKEN"), "service token از env.sh لازم است"
assert "NORA_BOT_ALLOW_LEGACY_SQLITE" not in os.environ

sys.path.insert(0, str(BOT_ROOT))
os.chdir(BOT_ROOT)
import bale_api  # noqa: E402

SENT: list[dict] = []
BALE_MODE = {"ok": True}


def fake_api(method, payload=None, files=None, **_):
    SENT.append({"method": method, "chat_id": (payload or {}).get("chat_id"), "text": (payload or {}).get("text", "")[:160]})
    if not BALE_MODE["ok"]:
        return {"ok": False, "error_code": 400, "description": "simulated delivery failure"}
    return {"ok": True, "result": {"message_id": len(SENT)}}


bale_api.api = fake_api  # هیچ درخواستی به بله نمی‌رود
import shared_api  # noqa: E402
import shared_form_ticket  # noqa: E402
import shared_workflows  # noqa: E402

log_lines: list[str] = []


def say(msg: str) -> None:
    print(msg)
    log_lines.append(msg)


# ── سرور: نشست‌های آزمایشی ──
O = {"Origin": B}
owner = httpx.Client(base_url=B)
assert owner.post("/api/auth/login", json={"username": os.environ["NORA_OWNER_USERNAME"], "password": Path("/tmp/nora-preview/owner-pw.txt").read_text().strip()}, headers=O).status_code == 200
OW = lambda: {**O, "X-CSRF-Token": owner.cookies.get("nora_csrf", "")}  # noqa: E731
manager = httpx.Client(base_url=B)
assert manager.post("/api/auth/manager-login", json={"username": "qa-manager", "password": Path("/tmp/nora-preview/manager-pw.txt").read_text().strip()}, headers=O).status_code == 200
MW = lambda: {**O, "X-CSRF-Token": manager.cookies.get("nora_account_csrf", "")}  # noqa: E731

# ── ۱) حضور و غیاب: بلیت آزمایشی در پایگاه مشترک (seed مستقیم، فقط پایگاه آزمایشی) ──
sys.path.insert(0, str(WEB_ROOT / "nora-ui"))
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from backend.models import AccountRecord, FormRecord, FormResponseDraftRecord, FormResponseRecord, PlatformIdentityRecord  # noqa: E402

engine = create_engine(os.environ["NORA_DATABASE_URL"])
FORM_ID = "7a3a0000-0000-4000-8000-0000000000a7"  # شناسهٔ فرم باید UUID باشد (قرارداد ربات)
with Session(engine) as db:
    member_account = db.scalar(select(PlatformIdentityRecord.account_id).where(PlatformIdentityRecord.provider == "bale", PlatformIdentityRecord.provider_user_id == str(MEMBER_UID)))
    assert member_account, "حساب عضو آزمایشی باید از قبل با ورود مینی‌اپ ساخته شده باشد"
    if db.get(FormRecord, FORM_ID) is None:
        db.add(FormRecord(id=FORM_ID, owner_id=os.environ["NORA_OWNER_ID"], title="کارگاه آزمایشی مرحلهٔ سوم (حضور)", model="registration", need="reg", status="published", version=1, settings={}))
    now = datetime.now(timezone.utc)
    response_id, draft_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(FormResponseDraftRecord(id=draft_id, form_id=FORM_ID, account_id=member_account, form_version=1, token_hash=uuid.uuid4().hex + uuid.uuid4().hex, bot_bale_user_id=str(MEMBER_UID), answers={"full-name": "عضو آزمایشی"}, companions=[], expires_at=now + timedelta(days=1), created_at=now, updated_at=now))
    db.add(FormResponseRecord(id=response_id, form_id=FORM_ID, draft_id=draft_id, form_version=1, status="accepted", answers={"full-name": "عضو آزمایشی"}, companions=[], registrant_name="عضو آزمایشی", form_snapshot={"name": "کارگاه آزمایشی مرحلهٔ سوم (حضور)", "version": 1, "model": "registration", "need": "reg"}, created_at=now, updated_at=now))
    db.commit()
say(f"seeded ticket response {response_id} for member account (form {FORM_ID})")

say("\n== attendance: bot scan path (shared_form_ticket.check_in) ==")
SENT.clear()
shared_form_ticket.check_in(MEMBER_UID, MEMBER_UID, response_id)  # عضو بدون مجوز
say("member tries check-in -> bot reply: " + SENT[-1]["text"])
before = len(SENT)
shared_form_ticket.check_in(MANAGER_UID, MANAGER_UID, response_id)
say("manager check-in #1 -> bot reply: " + SENT[-1]["text"].replace("\n", " | "))
shared_form_ticket.check_in(MANAGER_UID, MANAGER_UID, response_id)
say("manager check-in #2 (duplicate) -> bot reply: " + SENT[-1]["text"].replace("\n", " | "))
people = manager.get(f"/api/admin/attendance/forms/{FORM_ID}/people").json()
row = next(p for p in people["items"] if p["response_id"] == response_id)
say(f"panel API (manager) sees: checked_in={row['checked_in']} checked_in_by={row['checked_in_by']} source={people.get('source')}")
assert row["checked_in"] is True and row["checked_in_by"] == {"kind": "bot", "id": str(MANAGER_UID)}
# اصلاح دستی: برگرداندن حضور فقط با دلیل و مجوز attendance؛ عضو ۴۰۳
member_http = httpx.Client(base_url=B)
anon_undo = member_http.post(f"/api/admin/attendance/responses/{response_id}/undo-check-in", json={"reason": "x"}, headers=O)
say(f"anonymous undo -> {anon_undo.status_code}")
no_reason = manager.post(f"/api/admin/attendance/responses/{response_id}/undo-check-in", json={}, headers=MW())
say(f"manager undo without reason -> {no_reason.status_code} {no_reason.json().get('detail')}")
undo = manager.post(f"/api/admin/attendance/responses/{response_id}/undo-check-in", json={"reason": "آزمون مرحلهٔ سوم: اسکن اشتباه"}, headers=MW())
say(f"manager undo with reason -> {undo.status_code}")
shared_form_ticket.check_in(MANAGER_UID, MANAGER_UID, response_id)
say("bot re-scan after undo -> " + SENT[-1]["text"].replace("\n", " | "))
row = next(p for p in manager.get(f"/api/admin/attendance/forms/{FORM_ID}/people").json()["items"] if p["response_id"] == response_id)
say(f"final state: checked_in={row['checked_in']} by={row['checked_in_by']}")
aud = owner.get("/api/owner/audit?limit=10&offset=0&action=attendance.").json()
say("audit attendance rows: " + json.dumps([(a["action"], a.get("actor_role"), (a.get("details") or {}).get("reason")) for a in aud["items"]][:4], ensure_ascii=False))

# ── ۲) کارتابل: درخواست از مسیر ربات، تصمیم مدیر، اعلان ──
say("\n== kartabl: bot submit_workflow -> manager decision -> notification delivery ==")
key = f"profile:{MEMBER_UID}:{uuid.uuid4().hex}"
PROFILE = {"full_name": "عضو آزمایشی", "city": "آزمون", "bio": "درخواست آزمایشی مرحلهٔ سوم"}
result = shared_api.submit_workflow(MEMBER_UID, "profile_review", PROFILE, key)
task = result["task"]
say(f"bot created task {task['id']} kind={task['kind']} status={task['status']} created={result['created']}")
again = shared_api.submit_workflow(MEMBER_UID, "profile_review", PROFILE, key)
say(f"same idempotency key + same payload again -> created={again['created']} same id={again['task']['id'] == task['id']}")
try:
    shared_api.submit_workflow(MEMBER_UID, "profile_review", {"full_name": "تغییر"}, key)
    say("same key, different payload -> accepted (unexpected)")
except shared_api.SharedAPIError as exc:
    say(f"same key, different payload -> rejected by server: {exc.code}")
inbox = manager.get("/api/admin/inbox?limit=20&offset=0&status=pending").json()
mine = next((t for t in inbox["items"] if t["id"] == task["id"]), None)
say(f"manager inbox shows task: {bool(mine)} version={mine and mine.get('version')}")
no_perm = member_http.post(f"/api/admin/inbox/{task['id']}/decision", json={"decision": "approved", "expected_version": 1}, headers=O)
say(f"anonymous decision -> {no_perm.status_code}")
decision = manager.post(f"/api/admin/inbox/{task['id']}/decision", json={"decision": "rejected", "reason": "آزمون مرحلهٔ سوم: اطلاعات ناقص", "expected_version": mine["version"]}, headers=MW())
decided = decision.json().get("task", {}) if decision.status_code == 200 else {}
say(f"manager rejects with reason -> {decision.status_code} status={decided.get('status')} reason={decided.get('review_reason')} notification={json.dumps(decided.get('notification'), ensure_ascii=False)}")
# وضعیت اعلان: «تصمیم ذخیره شد» جدا از «اعلان تحویل شد»
pending = httpx.get(f"{B}/api/bot/notifications/pending", headers={"Authorization": "Bearer " + os.environ["NORA_BOT_SERVICE_TOKEN"]}, params={"limit": 50}).json()
mine_n = [n for n in pending.get("items", pending if isinstance(pending, list) else []) if str(n.get("bale_user_id")) == str(MEMBER_UID)]
say(f"server notification queue for member: {len(mine_n)} pending (decision saved, not yet delivered)")
BALE_MODE["ok"] = False
SENT.clear()
failed = shared_workflows.deliver_pending_notifications()
say(f"bot delivery run with simulated Bale failure -> delivered={failed}; bot attempted sendMessage to chat {SENT[-1]['chat_id'] if SENT else None}")
pending2 = httpx.get(f"{B}/api/bot/notifications/pending", headers={"Authorization": "Bearer " + os.environ["NORA_BOT_SERVICE_TOKEN"]}, params={"limit": 50}).json()
say(f"queue after failure: {len([n for n in pending2.get('items', []) if str(n.get('bale_user_id')) == str(MEMBER_UID)])} still pending for member")
mid_view = next((t for t in manager.get("/api/admin/inbox?limit=20&offset=0&status=decided").json()["items"] if t["id"] == task["id"]), {})
say("task after failed attempt (manager view): " + json.dumps(mid_view.get("notification"), ensure_ascii=False))
BALE_MODE["ok"] = True
SENT.clear()
ok = shared_workflows.deliver_pending_notifications()
say(f"bot delivery run with simulated Bale success -> delivered={ok}; message text: {SENT[-1]['text'].replace(chr(10), ' | ') if SENT else None}")
after = manager.get(f"/api/admin/inbox?limit=20&offset=0&status=decided").json()
mine2 = next((t for t in after["items"] if t["id"] == task["id"]), None)
say("task after delivery (manager view): " + json.dumps({"status": mine2.get("status"), "review_reason": mine2.get("review_reason"), "notification": mine2.get("notification")} if mine2 else {}, ensure_ascii=False, default=str))
summary = owner.get("/api/admin/reports/summary?period=7d").json()
say("reports notifications by_delivery_status: " + json.dumps(summary["notifications"]["by_delivery_status"], ensure_ascii=False))
json.dump({"response_id": response_id, "form_id": FORM_ID, "task_id": task["id"]}, open(OUT / "state.json", "w"))
(OUT / "bot-paths-log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
