"""Phase-9.3 incremental preview seed (TEST DB ONLY, synthetic data; never point it at an operational database).

Usage:  NORA_PREVIEW_DIR=<dir with nora.db from tools/phase9-preview-seed.py> python tools/phase9.3-preview-seed.py
Run it while the preview server is stopped. It ADDS (never rebuilds) the acceptance scenario of phase 9.3:
an in-person workshop that was held, with a registration form; one member registered AND checked in
(`qa-attendee`), one member registered but absent (`qa-absent`); after the event the owner attaches a
recording (YouTube session + handout), opens the courtesy «attendee_access», publishes the product and
sells it through a purchase form. Nothing is written to the database directly: every row goes through
the same admin / public / account APIs the panel and the site use.
Identifiers are appended to nora-ui/PREVIEW-LOGIN.local.md (gitignored) — never printed, never committed.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))
sys.path.insert(0, str(UI / "backend" / "tests"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_event_registration_gate import create_published_event, create_published_form, iso, update_event  # noqa: E402
from test_recordings_api import ORIGIN, build_sellable_product, purchase_form, set_status  # noqa: E402
from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, bale_login, owner_login, owner_write_headers  # noqa: E402

PREVIEW_DIR = Path(os.environ.get("NORA_PREVIEW_DIR") or (Path.home() / "nora-preview"))
DB = PREVIEW_DIR / "nora.db"
CREDS = UI / "PREVIEW-LOGIN.local.md"
TEST_HELPER_OWNER_PASSWORD = "correct-horse-staple-42"  # fixed value hard-coded in backend/tests/test_workflows_api.py::owner_login
ATTENDEE_BALE_ID = 91011
ABSENT_BALE_ID = 91012


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"{DB} missing — run tools/phase9-preview-seed.py first")
    engine = create_engine(f"sqlite+pysqlite:///{DB}", connect_args={"check_same_thread": False})
    settings = Settings(
        database_url=None, owner_id="owner-qa", owner_username="nora-owner",
        owner_password_hash=hash_password(TEST_HELPER_OWNER_PASSWORD), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as owner:
        owner_login(owner)
        listing = owner.get("/api/admin/content/events")
        assert listing.status_code == 200, listing.text
        version = int(listing.json().get("version") or 0)

        # 1) Upcoming in-person workshop with an open registration form (members must be able to register).
        held_ev, version = create_published_event(
            owner, version, t="کارگاه حضوری رصد ماه (برگزارشده، با آرشیو حاضران)", kind="کارگاه", on="۱۴۰۵/۰۷/۲۵",
            d="کارگاه حضوری یک‌روزه؛ ضبط جلسات پس از برگزاری برای حاضران رایگان و برای دیگران با خرید دسترسی.",
            place="رصدخانهٔ انجمن", mode="حضوری",
            startsAt=iso(timedelta(days=6)), endsAt=iso(timedelta(days=6)), regClosesAt=iso(timedelta(days=5)),
        )
        reg_form = create_published_form(owner, event_id=held_ev, key="preview-93-reg-attendee-01")

        attendee = TestClient(app)
        attendee_id = bale_login(attendee, ATTENDEE_BALE_ID)
        absent = TestClient(app)
        absent_id = bale_login(absent, ABSENT_BALE_ID)
        for client, name in ((attendee, "حاضر آزمایشی"), (absent, "غایب آزمایشی")):
            assert client.get(f"/api/public/forms/{reg_form}/draft").status_code == 200
            submitted = client.post(f"/api/public/forms/{reg_form}/responses", json={"answers": {"full-name": name}}, headers=ORIGIN)
            assert submitted.status_code == 200 and submitted.json()["status"] == "accepted", submitted.text
        attendee_response = attendee.get("/api/account/registrations").json()["items"][0]["id"]
        # 2) The day of the event: the attendee is checked in through the attendance panel API; the other one never shows up.
        checked = owner.post(f"/api/admin/attendance/responses/{attendee_response}/check-in", json={}, headers=owner_write_headers(owner))
        assert checked.status_code == 200, checked.text

        # 3) The event is over: window moved to the past (registration closes with it).
        version = update_event(owner, held_ev, version, startsAt=iso(timedelta(days=-3)), endsAt=iso(timedelta(days=-3)),
                               regClosesAt=iso(timedelta(days=-4)), past=True)

        # 4) Owner attaches the recording to the SAME event: courtesy for checked-in attendees, sale for everyone else.
        product = build_sellable_product(
            owner, held_ev, title="نسخهٔ ضبط‌شدهٔ کارگاه حضوری رصد ماه", summary="دو جلسه ویدئو و جزوهٔ کارگاه.",
            price=900_000, outcomes="شناخت فازهای ماه، رصد با دوربین دوچشمی", audience="حاضران کارگاه و علاقه‌مندان",
            access_terms="مشاهدهٔ برخط؛ حاضران کارگاه بدون خرید", refund_policy="تا ۷ روز با درخواست کتبی",
            attendee_access=True, access_days=90,
        )
        rec_id = product["recording"]["id"]
        s2 = owner.post(f"/api/admin/events/{held_ev}/recording/sessions",
                        json={"title": "جلسهٔ دوم: رصد عملی", "duration_minutes": 55}, headers=owner_write_headers(owner))
        assert s2.status_code == 201, s2.text
        yt = owner.post(f"/api/admin/events/{held_ev}/resources",
                        json={"kind": "youtube", "title": "ویدئوی جلسهٔ دوم (یوتیوب)", "link_url": "https://youtu.be/jNQXAC9IVRw",
                              "access": "purchased", "session_id": s2.json()["id"]},
                        headers=owner_write_headers(owner))
        assert yt.status_code == 201, yt.text
        # §6.4: a purchased YouTube/Aparat source needs an explicit external-exposure acknowledgement to be published.
        published_yt = owner.put(f"/api/admin/events/{held_ev}/resources/{yt.json()['id']}",
                                 json={"status": "published", "acknowledge_external_exposure": True},
                                 headers=owner_write_headers(owner))
        assert published_yt.status_code == 200, published_yt.text
        assert owner.put(f"/api/admin/events/{held_ev}/recording/sessions/{s2.json()['id']}", json={"status": "published"},
                         headers=owner_write_headers(owner)).status_code == 200
        # The test helper numbers its idempotency keys from 0; the phase-9 seed already used the first ones.
        import test_recordings_api as _rec_tests
        _rec_tests.PURCHASE_FORM_KEYS = iter(range(930, 999))
        form_id = purchase_form(owner, rec_id, price=900_000)
        assert set_status(owner, held_ev, "ready").status_code == 200
        assert set_status(owner, held_ev, "published").status_code == 200

        # Server truth: the attendee's library lists the courtesy; the absent member's does not.
        mine = attendee.get("/api/account/recordings").json()
        assert any(i["recording_id"] == rec_id and i["access"]["source"] == "attended" for i in mine["items"]), mine
        assert not any(i["recording_id"] == rec_id for i in absent.get("/api/account/recordings").json()["items"])
    engine.dispose()
    with CREDS.open("a", encoding="utf-8") as fh:
        fh.write(
            "\n## فاز ۹.۳ (افزوده‌شده، فقط دادهٔ آزمایشی)\n"
            f"- اعضا: attendee={ATTENDEE_BALE_ID} ({attendee_id}) حاضر و چک‌این‌شده · absent={ABSENT_BALE_ID} ({absent_id}) ثبت‌نامی بدون حضور\n"
            f"- رویداد حضوری برگزارشده با آرشیو حاضران: held93={held_ev} · محصول: {rec_id}\n"
            f"- فرم ثبت‌نام (بسته‌شده با پایان رویداد): {reg_form} · فرم خرید دسترسی: `form.html?fid={form_id}&kind=reg`\n"
        )
    print("seeded phase 9.3", {"held93": held_ev, "recording": rec_id, "purchase_form": form_id,
                               "members": "see PREVIEW-LOGIN.local.md"})


if __name__ == "__main__":
    os.environ.setdefault("NORA_PUBLIC_BASE_URL", "")
    main()
