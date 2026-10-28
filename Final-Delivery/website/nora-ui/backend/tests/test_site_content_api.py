from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402


@pytest.fixture
def client():
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
        session_ttl_seconds=3600,
        cookie_secure=False,
        bale_bot_username="nora_test_bot",
        bot_service_token="site-content-test-service-token-0123456789", 
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text


def csrf(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://testserver",
        "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
    }


def test_public_site_content_not_available_until_owner_publishes(client: TestClient):
    response = client.get("/api/public/site-content")
    assert response.status_code == 404
    assert response.json()["detail"] == "site_content_not_published"
    assert client.get("/api/owner/site-content").status_code == 401
    assert client.patch("/api/owner/site-content", json={"content": {"events": []}, "expected_version": 0}).status_code == 401


def test_owner_publishes_allowlisted_content_with_version_and_public_projection(client: TestClient):
    login(client)
    assert client.get("/api/owner/site-content").json()["version"] == 0
    content = {
        "events": [
            {
                "id": "event-public-1", "t": "کارگاه منتشرشده", "privacy": "public",
                "d": "شرح برنامهٔ منتشرشده", "when": "جمعه ۱۰ مهر", "on": "۱۴۰۵/۰۷/۱۰", "time": "۱۶:۰۰",
                "place": "پاریس", "parts": [{"title": "جلسهٔ نخست", "date": "۱۴۰۵/۰۷/۱۰"}],
                "code": "invite-secret", "regs": 19, "taken": 17, "spots": 2,
                "attendees": [{"name": "شخص خصوصی", "phone": "۰۹۱۲"}],
            },
            {"id": "event-hidden", "t": "رویداد پنهان", "privacy": "private"},
            {"id": "event-draft", "t": "پیش‌نویس", "privacy": "public", "status": "draft"},
        ],
        "people": [{
            "id": "person-1", "n": "مدرس منتشرشده", "kind": "teacher", "r": "مدرس",
            "bio": "زندگی‌نامهٔ عمومی", "mobile": "شمارهٔ خصوصی", "email": "private@example.test",
            "links": [{"k": "mail", "v": "public@example.test"}],
        }],
        "articles": [
            {"id": "article-public", "t": "مطلب منتشرشده", "pub": True, "blocks": [{"ty": "p", "x": "متن"}]},
            {"id": "article-draft", "t": "مطلب پیش‌نویس", "pub": False},
        ],
    }
    denied = client.patch(
        "/api/owner/site-content", json={"content": content, "expected_version": 0},
        headers={"Origin": "http://testserver"},
    )
    assert denied.status_code == 403

    published = client.patch(
        "/api/owner/site-content", json={"content": content, "expected_version": 0}, headers=csrf(client)
    )
    assert published.status_code == 200, published.text
    assert published.json()["version"] == 1

    public = client.get("/api/public/site-content")
    assert public.status_code == 200, public.text
    snapshot = public.json()["content"]
    assert [event["id"] for event in snapshot["events"]] == ["event-public-1"]
    event = snapshot["events"][0]
    assert event["d"] == "شرح برنامهٔ منتشرشده"
    assert event["when"] == "جمعه ۱۰ مهر"
    assert event["on"] == "۱۴۰۵/۰۷/۱۰", "the sortable Jalali date is part of the public projection"
    assert not {"code", "regs", "taken", "spots", "attendees"} & set(event)
    assert "person-private" not in str(snapshot)
    person = snapshot["people"][0]
    assert person["bio"] == "زندگی‌نامهٔ عمومی"
    assert "mobile" not in person and "email" not in person
    assert person["links"] == [{"k": "mail", "v": "mailto:public@example.test"}]
    assert [article["id"] for article in snapshot["articles"]] == ["article-public"]

    stale = client.patch(
        "/api/owner/site-content", json={"content": {"events": []}, "expected_version": 0}, headers=csrf(client)
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "site_content_version_conflict"
    assert stale.json()["detail"]["current_version"] == 1


def test_owner_banner_manager_keeps_drafts_private_and_applies_versioned_settings(client: TestClient):
    login(client)
    initial = client.get("/api/owner/site-content")
    assert initial.status_code == 200
    assert initial.json()["version"] == 0
    assert initial.json()["content"]["banner_settings"] == {
        "enabled": True, "auto_rotate": False, "interval_seconds": 7, "show_controls": True,
    }

    banner_content = {
        "events": [{"id": "banner-preserves-event", "t": "رویداد عمومی", "privacy": "public"}],
        "banners": [
            {
                "id": "banner-live", "status": "published", "active": True, "order": 2,
                "t": "برنامهٔ این هفته", "eyebrow": "ثبت‌نام", "subtitle": "زمان و مکان",
                "s": "برای دریافت جزئیات برنامه را باز کنید.", "img": "https://nora.test/banner.webp",
                "imgAlt": "تصویر برنامه", "href": "events.html#week", "primaryLabel": "جزئیات برنامه",
                "secondaryHref": "https://events.example.org/info", "secondaryLabel": "راهنمای کامل",
                "theme": "teal", "layout": "split", "align": "center", "overlay": 62,
                "focusX": 34, "focusY": 68, "startsAt": "2026-01-01T00:00:00Z",
                "endsAt": "2027-01-01T00:00:00Z", "kind": "sponsored",
            },
            {"id": "banner-draft", "status": "draft", "t": "پیش‌نویس خصوصی", "href": "javascript:alert(1)",
             "primaryLabel": "پیوند ناامن", "kind": "javascript:x"},
            {"id": "banner-paused", "status": "paused", "active": True, "t": "بنر متوقف"},
            {"id": "banner-statusless", "t": "بدون وضعیت انتشار"},
            {"id": "banner-inactive", "status": "published", "active": False, "t": "بنر خاموش"},
        ],
        "banner_settings": {"enabled": False, "auto_rotate": True, "interval_seconds": 45, "show_controls": False},
    }
    published = client.patch(
        "/api/owner/site-content",
        json={"content": banner_content, "expected_version": 0},
        headers=csrf(client),
    )
    assert published.status_code == 200, published.text
    assert published.json()["version"] == 1
    owner_view = published.json()["content"]
    assert [banner["id"] for banner in owner_view["banners"]] == [
        "banner-live", "banner-draft", "banner-paused", "banner-statusless", "banner-inactive",
    ]
    assert owner_view["banners"][1]["href"] == ""
    assert owner_view["banners"][0]["kind"] == "sponsored"
    assert owner_view["banners"][1]["kind"] == "notice", "unknown banner kinds fall back to a plain notice"
    assert owner_view["banners"][2]["kind"] == "notice", "missing kind defaults to notice"
    assert next(row for row in owner_view["banners"] if row["id"] == "banner-statusless")["status"] == "draft"
    assert owner_view["banner_settings"] == {
        "enabled": False, "auto_rotate": True, "interval_seconds": 20, "show_controls": False,
    }

    public = client.get("/api/public/site-content")
    assert public.status_code == 200
    public_content = public.json()["content"]
    assert [banner["id"] for banner in public_content["banners"]] == ["banner-live"]
    live = public_content["banners"][0]
    assert live["layout"] == "split" and live["align"] == "center"
    assert live["img"] == "https://nora.test/banner.webp"
    assert live["href"] == "events.html#week"
    assert live["kind"] == "sponsored"
    assert public_content["banner_settings"]["enabled"] is False
    assert "banner-draft" not in str(public_content)

    settings_only = client.patch(
        "/api/owner/site-content",
        json={"content": {"banner_settings": {
            "enabled": True, "auto_rotate": False, "interval_seconds": 5, "show_controls": True,
        }}, "expected_version": 1},
        headers=csrf(client),
    )
    assert settings_only.status_code == 200, settings_only.text
    assert settings_only.json()["version"] == 2
    assert [banner["id"] for banner in settings_only.json()["content"]["banners"]] == [
        "banner-live", "banner-draft", "banner-paused", "banner-statusless", "banner-inactive",
    ]
    assert settings_only.json()["content"]["events"][0]["id"] == "banner-preserves-event"
    assert settings_only.json()["content"]["banner_settings"]["interval_seconds"] == 5


def test_only_published_registration_forms_are_attached_to_public_events(client: TestClient):

    login(client)
    # forms.ev is a checked reference: the event row has to exist before a form can name it
    event_row = client.patch(
        "/api/owner/site-content",
        json={"content": {"events": [{"id": "event-form-1", "t": "رویداد ثبت‌نام", "privacy": "public"}]}, "expected_version": 0},
        headers=csrf(client),
    )
    assert event_row.status_code == 200, event_row.text
    draft = client.post(
        "/api/forms",
        json={
            "name": "فرم ثبت‌نام رویداد",
            "model": "registration",
            "need": "reg",
            "ev": "event-form-1",
            "fields": [{"id": "name", "t": "text", "l": "نام و نام خانوادگی", "required": True}],
            "settings": {},
        },
        headers={**csrf(client), "Idempotency-Key": "site-content-form-001"},
    )
    assert draft.status_code == 201, draft.text
    form_id = draft.json()["id"]
    published_form = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf(client)
    )
    assert published_form.status_code == 200, published_form.text

    update = client.patch(
        "/api/owner/site-content",
        json={
            "content": {"events": [{
                "id": "event-form-1", "t": "رویداد ثبت‌نام", "privacy": "public",
                "forms": [{"id": form_id, "need": "reg", "n": "فرم محلی ادعایی"}],
                "regForm": "not-a-server-form",
            }]},
            "expected_version": 1,
        },
        headers=csrf(client),
    )
    assert update.status_code == 200, update.text
    public_event = client.get("/api/public/site-content").json()["content"]["events"][0]
    assert public_event["forms"] == [{"id": form_id, "need": "reg", "n": "فرم ثبت‌نام رویداد"}]
    assert "regForm" not in public_event


def test_cooperation_form_reference_is_public_only_while_published(client: TestClient):
    login(client)
    created = client.post(
        "/api/forms",
        json={
            "name": "فرم همکاری نورا",
            "model": "questionnaire",
            "need": "other",
            "fields": [{"id": "name", "t": "fullname", "l": "نام و نام خانوادگی", "required": True}],
            "settings": {},
        },
        headers={**csrf(client), "Idempotency-Key": "cooperation-form-0001"},
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf(client)
    )
    assert published.status_code == 200, published.text

    update = client.patch(
        "/api/owner/site-content",
        json={
            "content": {
                "cooperation": [{
                    "formId": form_id,
                    "title": "عنوان دلخواهِ تأییدنشده",
                    "owner_id": "نباید عمومی شود",
                }]
            },
            "expected_version": 0,
        },
        headers=csrf(client),
    )
    assert update.status_code == 200, update.text
    public = client.get("/api/public/site-content").json()["content"]
    assert public["cooperation"] == [{"formId": form_id}]
    assert "owner_id" not in str(public["cooperation"])
    assert client.get(f"/form.html?fid={form_id}&kind=other").status_code == 200

    paused = client.post(
        f"/api/forms/{form_id}/pause", json={"expected_version": 2}, headers=csrf(client)
    )
    assert paused.status_code == 200, paused.text
    assert client.get("/api/public/site-content").json()["content"]["cooperation"] == []


def test_site_content_rejects_unknown_fields_and_invalid_versions(client: TestClient):
    login(client)
    wrong_csrf = client.patch(
        "/api/owner/site-content",
        json={"content": {"unknown": []}, "expected_version": 0},
        headers={"Origin": "http://testserver"},
    )
    assert wrong_csrf.status_code == 403
    invalid_version = client.patch(
        "/api/owner/site-content",
        json={"content": {"unknown": []}, "expected_version": True},
        headers=csrf(client),
    )
    assert invalid_version.status_code == 422
    invalid_content = client.patch(
        "/api/owner/site-content",
        json={"content": {"unknown": []}, "expected_version": 0},
        headers=csrf(client),
    )
    assert invalid_content.status_code == 422


def test_published_files_are_bot_delivered_without_breaking_admin_review(client: TestClient):
    login(client)
    pdf = b"%PDF-1.7\nNora shared delivery test\n%%EOF\n"
    pdf_url = "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii")
    audio_url = "data:audio/mpeg;base64," + base64.b64encode(b"\x00\x01\x02audio").decode("ascii")
    published = client.patch(
        "/api/owner/site-content",
        json={
            "content": {
                "events": [{
                    "id": "event-file-delivery", "t": "آرشیو آزمون", "privacy": "public", "past": True,
                    "media": [{"id": "media-pdf", "k": "pdf", "t": "برگهٔ جلسه", "file_name": "جلسه.pdf",
                               "mime": "application/pdf", "src": pdf_url}],
                }],
                "articles": [{
                    "id": "article-file-delivery", "t": "مطلب پیوست‌دار", "pub": True,
                    "blocks": [{"ty": "file", "t": "راهنما", "file_name": "راهنما.pdf", "up": pdf_url}],
                }],
                "library": [
                    {"id": "book-delivery", "t": "کتاب باشگاه", "kind": "کتاب", "fname": "کتاب.pdf", "file": pdf_url},
                    {"id": "audio-delivery", "t": "صدای باشگاه", "kind": "صدا", "mime": "audio/mpeg", "file": audio_url},
                ],
            },
            "expected_version": 0,
        },
        headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")},
    )
    assert published.status_code == 200, published.text

    response = client.get("/api/public/site-content")
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_bot_url"] == "https://ble.ir/nora_test_bot"
    snapshot = body["content"]
    serialized = str(snapshot)
    assert pdf_url not in serialized and "file_data" not in serialized and base64.b64encode(pdf).decode("ascii") not in serialized
    assert snapshot["library"][1]["src"] == audio_url  # playback remains public
    assert snapshot["library"][0]["delivery_id"] and snapshot["library"][0]["available"] is True
    assert snapshot["events"][0]["media"][0]["delivery_id"]
    assert snapshot["articles"][0]["blocks"][0]["delivery_id"]

    delivery_ids = [
        snapshot["library"][0]["delivery_id"],
        snapshot["events"][0]["media"][0]["delivery_id"],
        snapshot["articles"][0]["blocks"][0]["delivery_id"],
    ]
    for delivery_id in delivery_ids:
        assert client.get(f"/api/bot/content-files/{delivery_id}").status_code == 401
        delivered = client.get(
            f"/api/bot/content-files/{delivery_id}",
            headers={"Authorization": "Bearer site-content-test-service-token-0123456789"},
        )
        assert delivered.status_code == 200, delivered.text
        assert delivered.content == pdf
        assert delivered.headers["content-type"].startswith("application/pdf")
        assert "attachment" in delivered.headers["content-disposition"]

    invalid = client.get(
        "/api/bot/content-files/../not-an-id",
        headers={"Authorization": "Bearer site-content-test-service-token-0123456789"},
    )
    assert invalid.status_code in {404, 422}



def test_partner_privacy_is_enforced_at_the_server_boundary_and_profile_fields_survive(client: TestClient):
    """Partners must obey the same publish/visibility flags as people and articles.

    Reproduction for the partner-page audit: before the fix ``_partner()`` only
    rejected ``hidden`` and ``status == draft``; ``pub=False``, ``privacy=private``,
    ``pend=True`` and ``paused``/``pending`` statuses leaked into the public API
    while the sanitiser dropped the very flags the browser relied on to hide them.
    """
    login(client)
    content = {
        "partners": [
            {
                "id": "partner public 1", "n": "نهاد <b>عمومی</b>", "type": "نهاد فرهنگی",
                "s": "همراه برنامه‌های آموزشی", "collab": "برگزاری کارگاه", "since": "مهر ۱۴۰۵",
                "focus": ["آموزش", "کارگاه", "", None, {"x": 1}], "d": "شرح کامل همکاری",
                "logo": "/uploads/logo.webp", "href": "partner.example.org/about",
                "links": [
                    {"k": "mail", "v": "hello@partner.example.org"},
                    {"k": "tel", "v": "+33 1 23 45 67 89"},
                    {"k": "tg", "v": "@partner_channel"},
                    {"k": "web", "v": "javascript:alert(1)"},
                    {"k": "other", "v": "//evil.example/x"},
                    {"k": "ig", "v": "https://user:pw@instagram.com/x"},
                ],
                "mon": "عم", "g": "linear-gradient(135deg,#2E6B7A,#0B2447)",
                "internalNote": "یادداشت خصوصی مالک",
            },
            {"id": "partner-unpublished", "n": "نهاد منتشرنشده", "pub": False},
            {"id": "partner-private", "n": "نهاد خصوصی", "privacy": "private"},
            {"id": "partner-pending", "n": "نهاد منتظر", "pend": True},
            {"id": "partner-paused", "n": "نهاد متوقف", "status": "paused"},
            {"id": "partner-pending-status", "n": "نهاد در انتظار", "status": "pending"},
            {"id": "partner-draft", "n": "نهاد پیش‌نویس", "status": "draft"},
            {"id": "partner-hidden", "n": "نهاد پنهان", "hidden": True},
            {"id": "partner-xss", "n": "<img src=x onerror=alert(1)>", "logo": "javascript:alert(1)",
             "href": "https://user:secret@partner.example.org/", "d": "<script>alert(1)</script>"},
        ],
        "events": [
            {"id": "event-with-partner", "t": "رویداد با نهاد", "privacy": "public",
             "partnerId": "partner public 1", "partnerName": "نام قدیمی"},
        ],
    }
    saved = client.patch(
        "/api/owner/site-content", json={"content": content, "expected_version": 0}, headers=csrf(client)
    )
    assert saved.status_code == 200, saved.text

    public = client.get("/api/public/site-content")
    assert public.status_code == 200
    snapshot = public.json()["content"]
    partner_ids = [row["id"] for row in snapshot["partners"]]
    assert "partner public 1" in partner_ids
    for private_id in ("partner-unpublished", "partner-private", "partner-pending", "partner-paused",
                       "partner-pending-status", "partner-draft", "partner-hidden"):
        assert private_id not in str(snapshot), f"{private_id} must not reach the public projection"

    live = next(row for row in snapshot["partners"] if row["id"] == "partner public 1")
    assert live["n"] == "نهاد <b>عمومی</b>", "names stay text; escaping is the renderer's job"
    assert live["type"] == "نهاد فرهنگی"
    assert live["s"] == "همراه برنامه‌های آموزشی"
    assert live["collab"] == "برگزاری کارگاه"
    assert live["since"] == "مهر ۱۴۰۵"
    assert live["focus"] == ["آموزش", "کارگاه"]
    assert live["d"] == "شرح کامل همکاری"
    assert live["logo"] == "/uploads/logo.webp"
    assert live["href"] == "https://partner.example.org/about"
    assert live["links"] == [
        {"k": "mail", "v": "mailto:hello@partner.example.org"},
        {"k": "tel", "v": "tel:+33 1 23 45 67 89"},
        {"k": "tg", "v": "partner_channel"},
    ], "only allowlisted contact kinds with safe values are published"
    assert "internalNote" not in live

    xss = next(row for row in snapshot["partners"] if row["id"] == "partner-xss")
    assert xss["logo"] == "" and xss["href"] == "", "javascript: logos and credentialed URLs are dropped"

    event = snapshot["events"][0]
    assert event["partnerId"] == "partner public 1", "the event→partner relation survives sanitisation"
    assert "partnerName" not in event or event["partnerName"] == "", \
        "the display name comes from the published partner record, never from a stale event field"
