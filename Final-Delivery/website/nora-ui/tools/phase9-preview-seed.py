"""Phase-9 preview seed (TEST DB ONLY, synthetic data; never point it at an operational database).

Usage:  NORA_PREVIEW_DIR=<empty dir> python tools/phase9-preview-seed.py
Builds <dir>/nora.db + <dir>/preview.env with:
owner (password login), manager (password login), three member accounts (Bale test identities):
qa-buyer (card order approved → access), qa-pending (receipt submitted → waiting), qa-free (free claim);
a held workshop with a published paid product, a held workshop with a free product, a held workshop
without product, an upcoming workshop with open registration. Credentials are written ONLY to
nora-ui/PREVIEW-LOGIN.local.md (gitignored) — never printed, never committed.
The seeding step uses the fixed credentials of the backend test helpers (``owner_login``); the served
``preview.env`` carries freshly generated QA credentials for the same owner_id.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))
sys.path.insert(0, str(UI / "backend" / "tests"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402
from backend.roles import ROLE_MANAGER  # noqa: E402

from test_event_registration_gate import create_published_event, create_published_form, iso  # noqa: E402
from test_recordings_api import (  # noqa: E402
    MP4, PNG, build_sellable_product, inbox_decide, purchase_form, put_recording, set_status, submit_purchase,
    upload_purchase_receipt,
)
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN, SERVICE_TOKEN, account_write_headers, bale_login, owner_login, owner_write_headers,
)

PREVIEW_DIR = Path(os.environ.get("NORA_PREVIEW_DIR") or (Path.home() / "nora-preview"))
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
DB = PREVIEW_DIR / "nora.db"
ENV = PREVIEW_DIR / "preview.env"
CREDS = Path(os.environ.get("NORA_PREVIEW_LOGIN_FILE") or (UI / "PREVIEW-LOGIN.local.md"))
# Optional: seed a disposable PostgreSQL (or any SQLAlchemy URL) instead of the SQLite file. The schema must
# already exist there (``alembic upgrade head``); ``create_all`` then only fills in anything missing.
DB_URL = os.environ.get("NORA_PREVIEW_DATABASE_URL") or ""

TEST_HELPER_OWNER_PASSWORD = "correct-horse-staple-42"  # fixed value hard-coded in backend/tests/test_workflows_api.py::owner_login
OWNER_USER = "qa-owner"
OWNER_PASS = secrets.token_urlsafe(12)
MANAGER_USER = "qa-manager"
MANAGER_PASS = secrets.token_urlsafe(12)


def main() -> None:
    if DB_URL:
        engine = create_engine(DB_URL)
    else:
        if DB.exists():
            DB.unlink()
        engine = create_engine(f"sqlite+pysqlite:///{DB}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    settings = Settings(
        # Seeding runs with the test helpers' fixed credentials; the served env uses the QA ones (same owner_id).
        database_url=None, owner_id="owner-qa", owner_username="nora-owner",
        owner_password_hash=hash_password(TEST_HELPER_OWNER_PASSWORD), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as owner:
        owner_login(owner)
        version = 0
        paid_ev, version = create_published_event(
            owner, version, t="کارگاه نجوم رصدی (برگزارشده)", kind="کارگاه", on="۱۴۰۵/۰۷/۲۰",
            d="سه جلسهٔ عملی دربارهٔ آسمان شب، صور فلکی و کار با تلسکوپ.", place="رصدخانهٔ انجمن",
            startsAt=iso(timedelta(days=-9)), endsAt=iso(timedelta(days=-8)), regClosesAt=iso(timedelta(days=-10)), past=True,
        )
        create_published_form(owner, event_id=paid_ev, key="preview-reg-paid-0001")
        free_ev, version = create_published_event(
            owner, version, t="نشست ادبی پاییز (برگزارشده)", kind="نشست", on="۱۴۰۵/۰۷/۱۲",
            d="نشست خوانش و گفت‌وگو دربارهٔ شعر معاصر.", place="سالن اصلی",
            startsAt=iso(timedelta(days=-20)), endsAt=iso(timedelta(days=-20)), regClosesAt=iso(timedelta(days=-21)), past=True,
        )
        plain_ev, version = create_published_event(
            owner, version, t="کارگاه عکاسی شب (برگزارشده، بدون ضبط)", kind="کارگاه", on="۱۴۰۵/۰۷/۰۵",
            d="کارگاه عملی عکاسی از آسمان شب.", place="طبیعت اطراف شهر",
            startsAt=iso(timedelta(days=-30)), endsAt=iso(timedelta(days=-30)), regClosesAt=iso(timedelta(days=-31)), past=True,
        )
        up_ev, version = create_published_event(
            owner, version, t="کارگاه آینده: مقدمات اخترفیزیک", kind="کارگاه", on="۱۴۰۵/۰۸/۱۵",
            d="برای علاقه‌مندان مبتدی.", place="سالن اصلی", startsAt=iso(timedelta(days=12)), endsAt=iso(timedelta(days=12)),
            regClosesAt=iso(timedelta(days=10)),
        )
        create_published_form(owner, event_id=up_ev, key="preview-reg-upcoming-01")

        # Paid product: two sessions, one preview handout, one purchased-only video, FAQ.
        product = build_sellable_product(
            owner, paid_ev, title="نسخهٔ ضبط‌شدهٔ کارگاه نجوم رصدی", summary="سه جلسه ویدئو به‌همراه جزوهٔ هر جلسه.",
            price=1_500_000, outcomes="شناخت صور فلکی، کار با تلسکوپ، ثبت عکس ساده", audience="علاقه‌مندان بدون پیش‌نیاز",
            access_terms="مشاهدهٔ برخط ویدئوها؛ جزوه‌ها قابل دانلود", refund_policy="تا ۷ روز پس از خرید با درخواست کتبی",
            faq=[{"q": "آیا ویدئو قابل دانلود است؟", "a": "خیر؛ فقط مشاهدهٔ برخط. جزوه‌ها قابل دانلودند."},
                 {"q": "دسترسی چقدر اعتبار دارد؟", "a": "۹۰ روز پس از فعال‌شدن."}],
            access_days=90,
        )
        session_1 = product["_session_id"]
        handout = owner.post(f"/api/admin/events/{paid_ev}/resources",
                             json={"title": "جزوهٔ جلسهٔ اول (پیش‌نمایش)", "access": "public", "session_id": session_1, "delivery": "download"},
                             headers=owner_write_headers(owner))
        assert handout.status_code == 201, handout.text
        hid = handout.json()["id"]
        assert owner.put(f"/api/admin/events/{paid_ev}/resources/{hid}/file", content=PNG,
                         headers={**owner_write_headers(owner), "X-File-Name": quote("جزوه-۱.png")}).status_code == 200
        assert owner.put(f"/api/admin/events/{paid_ev}/resources/{hid}", json={"status": "published"},
                         headers=owner_write_headers(owner)).status_code == 200
        s2 = owner.post(f"/api/admin/events/{paid_ev}/recording/sessions",
                        json={"title": "جلسهٔ دوم: کار با تلسکوپ", "duration_minutes": 70}, headers=owner_write_headers(owner))
        assert s2.status_code == 201, s2.text
        v2 = owner.post(f"/api/admin/events/{paid_ev}/resources",
                        json={"title": "ویدئوی جلسهٔ دوم", "access": "purchased", "session_id": s2.json()["id"], "delivery": "view"},
                        headers=owner_write_headers(owner))
        assert v2.status_code == 201
        assert owner.put(f"/api/admin/events/{paid_ev}/resources/{v2.json()['id']}/file", content=MP4,
                         headers={**owner_write_headers(owner), "X-File-Name": quote("جلسه-۲.mp4")}).status_code == 200
        assert owner.put(f"/api/admin/events/{paid_ev}/resources/{v2.json()['id']}", json={"status": "published"},
                         headers=owner_write_headers(owner)).status_code == 200
        assert owner.put(f"/api/admin/events/{paid_ev}/recording/sessions/{s2.json()['id']}", json={"status": "published"},
                         headers=owner_write_headers(owner)).status_code == 200
        paid_rec = product["recording"]["id"]
        # Phase 9.1 §3: a third session delivered from external players (YouTube privacy-enhanced + Aparat).
        s3 = owner.post(f"/api/admin/events/{paid_ev}/recording/sessions",
                        json={"title": "جلسهٔ سوم: منابع بیرونی (یوتیوب و آپارات)", "duration_minutes": 45}, headers=owner_write_headers(owner))
        assert s3.status_code == 201, s3.text
        for kind, raw, title in (
            ("youtube", "https://youtu.be/jNQXAC9IVRw", "ویدیوی یوتیوب جلسهٔ سوم"),
            ("aparat", "https://www.aparat.com/v/IM5AJ", "ویدیوی آپارات جلسهٔ سوم"),
        ):
            ext = owner.post(f"/api/admin/events/{paid_ev}/resources",
                             json={"kind": kind, "title": title, "link_url": raw, "access": "purchased", "session_id": s3.json()["id"]},
                             headers=owner_write_headers(owner))
            assert ext.status_code == 201, ext.text
            # Phase 9.5 §6.4: a paid-level external video goes live only with the operator's audited acknowledgement.
            assert owner.put(f"/api/admin/events/{paid_ev}/resources/{ext.json()['id']}",
                             json={"status": "published", "acknowledge_external_exposure": True},
                             headers=owner_write_headers(owner)).status_code == 200
        assert owner.put(f"/api/admin/events/{paid_ev}/recording/sessions/{s3.json()['id']}", json={"status": "published"},
                         headers=owner_write_headers(owner)).status_code == 200
        # Phase 9.1 §2: explicit completion-certificate policy (manual issuance only; nothing automatic exists).
        assert put_recording(owner, paid_ev, certificate_policy="manual").status_code == 200
        # Phase 9.1 §1: the purchase entry is a builder form (purpose=recording_access) — price/method/card live there.
        paid_form = purchase_form(owner, paid_rec, price=1_500_000, methods=("card_transfer",))
        assert set_status(owner, paid_ev, "ready").status_code == 200
        published = set_status(owner, paid_ev, "published")
        assert published.status_code == 200, published.text

        # Free product on the literary session.
        free = build_sellable_product(owner, free_ev, title="ضبط نشست ادبی پاییز", summary="یک جلسه ویدئو، رایگان.",
                                      price=0, payment_card=None, attendee_access=True)
        assert set_status(owner, free_ev, "ready").status_code == 200
        assert set_status(owner, free_ev, "published").status_code == 200
        free_rec = free["recording"]["id"]

        # Members (Bale test identities; no real Bale call happens).
        buyer = TestClient(app); buyer_id = bale_login(buyer, 91001)
        pending = TestClient(app); pending_id = bale_login(pending, 91002)
        freer = TestClient(app); freer_id = bale_login(freer, 91003)
        # buyer: purchase form response → receipt in the same form → approved by the owner in the shared inbox.
        r1 = submit_purchase(buyer, paid_form, name="خریدار آزمایشی یک")
        assert r1.status_code == 200 and r1.json()["accepted"] is True, r1.text
        rc1 = upload_purchase_receipt(buyer, paid_form, note="واریز ۱۴۰۵/۰۷/۲۸")
        assert rc1.status_code == 200 and rc1.json()["uploaded"] is True, rc1.text
        task_1 = rc1.json()["review_task_id"]
        ok = inbox_decide(owner, task_1, "approved", "رسید با مبلغ تطبیق داده شد", owner_write_headers(owner))
        assert ok.status_code == 200, ok.text
        # pending: response + receipt, waiting for review in the inbox.
        r2 = submit_purchase(pending, paid_form, name="خریدار آزمایشی دو")
        assert r2.status_code == 200 and r2.json()["accepted"] is True, r2.text
        assert upload_purchase_receipt(pending, paid_form, name="receipt2.png").status_code == 200
        # free holder.
        assert freer.post(f"/api/account/recordings/{free_rec}/claim", headers=account_write_headers(freer)).status_code == 201
        # buyer asks a session question; owner answers; buyer reviews.
        q = buyer.post(f"/api/account/events/{paid_ev}/questions",
                       json={"body": "در جلسهٔ اول، تنظیم زاویهٔ تلسکوپ برای مبتدی‌ها توضیح داده می‌شود؟", "session_id": session_1},
                       headers=account_write_headers(buyer))
        assert q.status_code == 201, q.text
        ans = owner.post(f"/api/admin/events/{paid_ev}/questions/{q.json()['id']}/answer",
                         json={"answer": "بله؛ دقیقهٔ ۲۰ تا ۳۵ جلسهٔ اول.", "official": True, "publish": True}, headers=owner_write_headers(owner))
        assert ans.status_code in (200, 201), ans.text
        rv = buyer.post(f"/api/account/events/{paid_ev}/reviews", json={"body": "ضبط باکیفیت و توضیحات روان؛ جزوه‌ها هم مفید بودند."},
                        headers=account_write_headers(buyer))
        assert rv.status_code == 201, rv.text
        mod = owner.post(f"/api/admin/events/{paid_ev}/reviews/{rv.json()['id']}/status",
                         json={"status": "published", "reason": "تأیید"}, headers=owner_write_headers(owner))
        assert mod.status_code == 200, mod.text

        # Manager account (separate from owner) with password login.
        manager = TestClient(app); manager_id = bale_login(manager, 91004)
        assert owner.put(f"/api/owner/accounts/{manager_id}/role", json={"role": ROLE_MANAGER}, headers=owner_write_headers(owner)).status_code == 200
        assert owner.put(f"/api/owner/accounts/{manager_id}/manager-credentials",
                         json={"username": MANAGER_USER, "password": MANAGER_PASS}, headers=owner_write_headers(owner)).status_code == 200

    engine.dispose()
    ENV.write_text(
        "\n".join([
            f"NORA_DATABASE_URL={DB_URL or f'sqlite+pysqlite:///{DB}'}",
            "NORA_OWNER_ID=owner-qa",
            f"NORA_OWNER_USERNAME={OWNER_USER}",
            f"NORA_OWNER_PASSWORD_HASH='{hash_password(OWNER_PASS)}'",  # single-quoted: hash contains `$`
            "NORA_COOKIE_SECURE=true",
            "NORA_COOKIE_SAMESITE=none",
            f"NORA_BALE_BOT_TOKEN={BOT_TOKEN}",
            # Served env: the bot bridge is not part of the preview; Settings.from_env rejects tokens < 32 chars, so leave it blank.
            "NORA_BOT_SERVICE_TOKEN=",
            "NORA_OWNER_BALE_USER_ID=70001",
        ]) + "\n", encoding="utf-8",
    )
    CREDS.write_text(
        "# پیش‌نمایش فاز ۹ (فقط دادهٔ آزمایشی، فایل محلی خارج از Git)\n\n"
        f"- مالک: `{OWNER_USER}` / `{OWNER_PASS}` → `/login.html?mode=staff&next=admin.html%23dash`\n"
        f"- مدیر: `{MANAGER_USER}` / `{MANAGER_PASS}` → همان مسیر\n"
        f"- اعضا (هویت بلهٔ آزمایشی، بدون رمز؛ نشست با امضای initData آزمایشی): buyer=91001 ({buyer_id}), pending=91002 ({pending_id}), free=91003 ({freer_id})\n"
        f"- رویدادها: paid={paid_ev} free={free_ev} plain={plain_ev} upcoming={up_ev}\n"
        f"- فرم خرید محصول پولی (فاز ۹.۱): `form.html?fid={paid_form}&kind=reg` · محصول: {paid_rec}\n",
        encoding="utf-8",
    )
    print("seeded", {"paid": paid_ev, "free": free_ev, "plain": plain_ev, "upcoming": up_ev, "purchase_form": paid_form,
                     "buyer": buyer_id, "pending": pending_id, "free_holder": freer_id})


if __name__ == "__main__":
    os.environ.setdefault("NORA_PUBLIC_BASE_URL", "")
    main()
