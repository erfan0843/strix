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
from test_recordings_api import MP4, PNG, build_sellable_product, set_status, put_recording  # noqa: E402
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN, SERVICE_TOKEN, account_write_headers, bale_login, owner_login, owner_write_headers,
)

PREVIEW_DIR = Path(os.environ.get("NORA_PREVIEW_DIR") or (Path.home() / "nora-preview"))
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
DB = PREVIEW_DIR / "nora.db"
ENV = PREVIEW_DIR / "preview.env"
CREDS = UI / "PREVIEW-LOGIN.local.md"

TEST_HELPER_OWNER_PASSWORD = "correct-horse-staple-42"  # fixed value hard-coded in backend/tests/test_workflows_api.py::owner_login
OWNER_USER = "qa-owner"
OWNER_PASS = secrets.token_urlsafe(12)
MANAGER_USER = "qa-manager"
MANAGER_PASS = secrets.token_urlsafe(12)


def main() -> None:
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
        assert set_status(owner, paid_ev, "ready").status_code == 200
        published = set_status(owner, paid_ev, "published")
        assert published.status_code == 200, published.text
        paid_rec = product["recording"]["id"]

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
        # buyer: order → receipt → approved by owner.
        o1 = buyer.post(f"/api/account/recordings/{paid_rec}/orders", json={"method": "card_transfer"}, headers=account_write_headers(buyer))
        assert o1.status_code == 201, o1.text
        assert buyer.put(f"/api/account/recording-orders/{o1.json()['id']}/receipt", content=PNG,
                         headers={**account_write_headers(buyer), "X-File-Name": "receipt.png", "X-Receipt-Note": quote("واریز ۱۴۰۵/۰۷/۲۸")}).status_code == 200
        ok = owner.post(f"/api/admin/recording-orders/{o1.json()['id']}/decision",
                        json={"decision": "approve", "reason": "رسید با مبلغ تطبیق داده شد"}, headers=owner_write_headers(owner))
        assert ok.status_code == 200, ok.text
        # pending: order + receipt, waiting for review.
        o2 = pending.post(f"/api/account/recordings/{paid_rec}/orders", json={"method": "card_transfer"}, headers=account_write_headers(pending))
        assert o2.status_code == 201
        assert pending.put(f"/api/account/recording-orders/{o2.json()['id']}/receipt", content=PNG,
                           headers={**account_write_headers(pending), "X-File-Name": "receipt2.png"}).status_code == 200
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
            f"NORA_DATABASE_URL=sqlite+pysqlite:///{DB}",
            "NORA_OWNER_ID=owner-qa",
            f"NORA_OWNER_USERNAME={OWNER_USER}",
            f"NORA_OWNER_PASSWORD_HASH='{hash_password(OWNER_PASS)}'",  # single-quoted: hash contains `$`
            "NORA_COOKIE_SECURE=true",
            "NORA_COOKIE_SAMESITE=none",
            f"NORA_BALE_BOT_TOKEN={BOT_TOKEN}",
            f"NORA_BOT_SERVICE_TOKEN={SERVICE_TOKEN}",
            "NORA_OWNER_BALE_USER_ID=70001",
        ]) + "\n", encoding="utf-8",
    )
    CREDS.write_text(
        "# پیش‌نمایش فاز ۹ (فقط دادهٔ آزمایشی، فایل محلی خارج از Git)\n\n"
        f"- مالک: `{OWNER_USER}` / `{OWNER_PASS}` → `/login.html?mode=staff&next=admin.html%23dash`\n"
        f"- مدیر: `{MANAGER_USER}` / `{MANAGER_PASS}` → همان مسیر\n"
        f"- اعضا (هویت بلهٔ آزمایشی، بدون رمز؛ نشست با امضای initData آزمایشی): buyer=91001 ({buyer_id}), pending=91002 ({pending_id}), free=91003 ({freer_id})\n"
        f"- رویدادها: paid={paid_ev} free={free_ev} plain={plain_ev} upcoming={up_ev}\n",
        encoding="utf-8",
    )
    print("seeded", {"paid": paid_ev, "free": free_ev, "plain": plain_ev, "upcoming": up_ev,
                     "buyer": buyer_id, "pending": pending_id, "free_holder": freer_id})


if __name__ == "__main__":
    os.environ.setdefault("NORA_PUBLIC_BASE_URL", "")
    main()
