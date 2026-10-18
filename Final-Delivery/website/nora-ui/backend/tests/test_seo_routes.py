from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
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
from backend.models import Base, SiteContentRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402

TEST_ORIGIN = "https://www.nora.seo-test-domain"


class _HeadingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "h1":
            self.h1_count += 1


def count_h1(markup: str) -> int:
    parser = _HeadingParser()
    parser.feed(markup)
    return parser.h1_count


def make_client(public_base_url: str = ""):
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
        public_base_url=public_base_url,
    )
    app = create_app(settings, engine=engine)
    return engine, TestClient(app)


def publish_public_content(client: TestClient) -> None:
    factory = client.app.state.session_factory
    content = {
        "events": [
            {
                "id": "event-public-1",
                "t": "کارگاه عمومی",
                "privacy": "public",
                "d": "شرح برنامهٔ عمومی.",
            },
            {"id": "event-private-1", "t": "رویداد خصوصی", "privacy": "private"},
        ],
        "people": [
            {"id": "person-public-1", "n": "مدرس عمومی", "r": "مدرس", "bio": "زندگی‌نامهٔ عمومی"},
            {"id": "person-draft-1", "n": "پیش‌نویس", "status": "draft"},
            {"id": "person-private-1", "n": "پروفایل خصوصی", "privacy": "private"},
            {"id": "person-hidden-1", "n": "پروفایل پنهان", "hidden": True},
            {"id": "person-pending-1", "n": "پروفایل منتظر", "pend": True},
        ],

        "articles": [
            {
                "id": "article-public-1",
                "t": "مطلب عمومی",
                "pub": True,
                "lead": "خلاصهٔ عمومی مطلب.",
                "blocks": [{"ty": "p", "x": "متن عمومی مطلب."}],
            },
            {"id": "article-draft-1", "t": "مطلب پیش‌نویس", "pub": False},
            {"id": "article-private-1", "t": "مطلب خصوصی", "pub": True, "privacy": "private"},
            {"id": "article-hidden-1", "t": "مطلب پنهان", "pub": True, "hidden": True},
            {"id": "article-pending-1", "t": "مطلب منتظر", "pub": True, "pend": True},
            {"id": "article-draft-status-1", "t": "مطلب پیش‌نویس", "pub": True, "status": "draft"},
        ],
        "partners": [
            {
                "id": "partner public 1", "n": "نهاد همکار عمومی", "type": "نهاد فرهنگی",
                "s": "همراه برنامه‌های آموزشی نورا", "d": "شرح کامل همکاری",
                "logo": "/uploads/partner-logo.webp", "href": "https://partner.example.org/",
            },
            {"id": "partner-plain", "n": "نهاد بدون شرح"},
            {"id": "partner-draft-1", "n": "نهاد پیش‌نویس", "status": "draft"},
            {"id": "partner-private-1", "n": "نهاد خصوصی", "privacy": "private"},
            {"id": "partner-unpublished-1", "n": "نهاد منتشرنشده", "pub": False},
            {"id": "partner-hidden-1", "n": "نهاد پنهان", "hidden": True},
            {"id": "partner-pending-1", "n": "نهاد منتظر", "pend": True},
            {"id": "partner-paused-1", "n": "نهاد متوقف", "status": "paused"},
        ],
        "banners": [],
        "cooperation": [],
        "library": [],
    }
    with factory() as db:
        db.add(SiteContentRecord(id="public", content=content, version=1))
        db.commit()


@pytest.fixture
def bare_client():
    engine, client = make_client()
    with client:
        yield client
    engine.dispose()


def test_home_and_robots_never_derive_public_origin_from_request_host(bare_client: TestClient):
    response = bare_client.get("/", headers={"host": "attacker.example"})
    assert response.status_code == 200
    assert '<title>نورا | گروه فرهنگی خط زندگی</title>' in response.text
    assert '<meta name="description" content="رویدادها، مطالب و پروفایل‌های عمومی منتشرشدهٔ گروه فرهنگی خط زندگی را در نورا ببینید."/>' in response.text
    assert '<link rel="canonical" href="/"/>' in response.text
    assert "attacker.example" not in response.text
    assert "nora-structured-data" in response.text
    assert "LocalBusiness" not in response.text
    assert count_h1(response.text) == 1

    robots = bare_client.get("/robots.txt", headers={"host": "attacker.example"})
    assert robots.status_code == 200
    assert "Disallow: /api/" in robots.text
    assert "Sitemap:" not in robots.text

    sitemap = bare_client.get("/sitemap.xml")
    assert sitemap.status_code == 503
    assert "attacker.example" not in sitemap.text


def test_configured_origin_drives_canonical_robots_and_absolute_sitemap():
    engine, client = make_client(TEST_ORIGIN)
    with client:
        response = client.get("/events.html?utm_source=ignored", headers={"host": "attacker.example"})
        assert response.status_code == 200
        assert '<title>رویدادها و برنامه‌های نورا | گروه فرهنگی خط زندگی</title>' in response.text
        assert '<meta name="description" content="فهرست رویدادها و برنامه‌های عمومی منتشرشده در نورا."/>' in response.text
        assert f'<link rel="canonical" href="{TEST_ORIGIN}/events.html"/>' in response.text
        assert "attacker.example" not in response.text
        assert "nora-structured-data" in response.text
        assert count_h1(response.text) == 1

        robots = client.get("/robots.txt")
        assert f"Sitemap: {TEST_ORIGIN}/sitemap.xml" in robots.text
        sitemap = client.get("/sitemap.xml")
        assert sitemap.status_code == 200
        assert sitemap.headers.get("content-type", "").startswith("application/xml")
        assert f"{TEST_ORIGIN}/" in sitemap.text
        assert f"{TEST_ORIGIN}/events.html" in sitemap.text
        assert "attacker.example" not in sitemap.text
    engine.dispose()


def test_dynamic_seo_uses_only_published_projection_for_pages_and_sitemap():
    engine, client = make_client(TEST_ORIGIN)
    with client:
        publish_public_content(client)

        event = client.get("/event.html?id=event-public-1&utm_source=ignored")
        assert event.status_code == 200
        assert "کارگاه عمومی | رویدادهای نورا" in event.text
        assert '<meta name="description" content="شرح برنامهٔ عمومی."/>' in event.text
        assert f'<link rel="canonical" href="{TEST_ORIGIN}/event.html?id=event-public-1"/>' in event.text
        assert "utm_source" not in event.text
        assert count_h1(event.text) == 1
        assert "aria-label=\"مسیر صفحه\"" in event.text
        graph_text = event.text.split('id="nora-structured-data"', 1)[1].split("</script>", 1)[0]
        graph = json.loads(graph_text.split(">", 1)[1])
        assert any(item.get("@type") == "WebPage" for item in graph["@graph"])
        assert any(item.get("@type") == "BreadcrumbList" for item in graph["@graph"])

        article = client.get("/post.html?id=article-public-1")
        assert article.status_code == 200
        assert "مطلب عمومی | مطالب نورا" in article.text
        assert '<meta name="description" content="خلاصهٔ عمومی مطلب."/>' in article.text
        assert f'<link rel="canonical" href="{TEST_ORIGIN}/post.html?id=article-public-1"/>' in article.text
        assert count_h1(article.text) == 1

        person = client.get("/person.html?id=person-public-1")
        assert person.status_code == 200
        assert "مدرس عمومی | پروفایل نورا" in person.text
        assert '<meta name="description" content="زندگی‌نامهٔ عمومی"/>' in person.text
        assert f'<link rel="canonical" href="{TEST_ORIGIN}/person.html?id=person-public-1"/>' in person.text
        assert count_h1(person.text) == 1

        partner = client.get("/partner.html?id=partner%20public%201&utm_source=ignored")
        assert partner.status_code == 200
        assert "نهاد همکار عمومی | نهادهای همکار نورا" in partner.text
        assert '<meta name="description" content="همراه برنامه‌های آموزشی نورا"/>' in partner.text
        assert f'<link rel="canonical" href="{TEST_ORIGIN}/partner.html?id=partner%20public%201"/>' in partner.text
        assert 'name="robots" content="index,follow"' in partner.text
        assert f'<meta property="og:image" content="{TEST_ORIGIN}/uploads/partner-logo.webp"/>' in partner.text
        assert 'lang="fa" dir="rtl"' in partner.text
        assert count_h1(partner.text) == 1
        assert "utm_source" not in partner.text
        partner_graph_text = partner.text.split('id="nora-structured-data"', 1)[1].split("</script>", 1)[0]
        partner_graph = json.loads(partner_graph_text.split(">", 1)[1])["@graph"]
        profile = next(item for item in partner_graph if item.get("@type") == "ProfilePage")
        assert profile["mainEntity"] == {
            "@type": "Organization", "name": "نهاد همکار عمومی", "description": "همراه برنامه‌های آموزشی نورا",
            "url": "https://partner.example.org/", "logo": f"{TEST_ORIGIN}/uploads/partner-logo.webp",
            "image": f"{TEST_ORIGIN}/uploads/partner-logo.webp",
        }, "only published owner facts; no address/telephone/legal id/ratings are invented"
        crumbs = next(item for item in partner_graph if item.get("@type") == "BreadcrumbList")["itemListElement"]
        assert [crumb["name"] for crumb in crumbs] == ["خانه", "نهادهای همکار", "نهاد همکار عمومی | نهادهای همکار نورا"]
        assert crumbs[1]["item"] == f"{TEST_ORIGIN}/#partners"

        plain_partner = client.get("/partner.html?id=partner-plain")
        assert plain_partner.status_code == 200
        assert '<meta name="description" content="نهاد بدون شرح، نهاد همکار گروه فرهنگی خط زندگی در نورا."/>' in plain_partner.text
        assert "og:image" not in plain_partner.text.split("<body", 1)[0].replace('<meta property="og:image" content="icon-512.png"/>', ""), \
            "no logo means no fabricated social image beyond the static template default"

        missing_partner = client.get("/partner.html?id=partner-does-not-exist")
        assert missing_partner.status_code == 404
        assert "نهاد همکار پیدا نشد | نورا" in missing_partner.text
        assert 'name="robots" content="noindex,nofollow,noarchive"' in missing_partner.text
        assert "rel=\"canonical\"" not in missing_partner.text
        assert "این نهاد همکار در دسترس نیست" in missing_partner.text

        private = client.get("/event.html?id=event-private-1")
        assert private.status_code == 404
        assert 'name="robots" content="noindex,nofollow,noarchive"' in private.text
        assert "rel=\"canonical\"" not in private.text

        for path in (
            "/person.html?id=person-private-1", "/person.html?id=person-hidden-1",
            "/person.html?id=person-pending-1", "/post.html?id=article-private-1",
            "/post.html?id=article-hidden-1", "/post.html?id=article-pending-1",
            "/post.html?id=article-draft-status-1",
            "/partner.html?id=partner-draft-1", "/partner.html?id=partner-private-1",
            "/partner.html?id=partner-unpublished-1", "/partner.html?id=partner-hidden-1",
            "/partner.html?id=partner-pending-1", "/partner.html?id=partner-paused-1",
        ):
            not_public = client.get(path)
            assert not_public.status_code == 404
            assert 'name="robots" content="noindex,nofollow,noarchive"' in not_public.text
            assert "rel=\"canonical\"" not in not_public.text

        preview = client.get("/post.html?id=article-public-1&d=1")
        assert preview.status_code == 200
        assert 'name="robots" content="noindex,nofollow,noarchive"' in preview.text
        assert "rel=\"canonical\"" not in preview.text

        sitemap = client.get("/sitemap.xml")
        assert f"{TEST_ORIGIN}/event.html?id=event-public-1" in sitemap.text
        assert f"{TEST_ORIGIN}/post.html?id=article-public-1" in sitemap.text
        assert f"{TEST_ORIGIN}/person.html?id=person-public-1" in sitemap.text
        assert f"{TEST_ORIGIN}/partner.html?id=partner%20public%201" in sitemap.text
        assert f"{TEST_ORIGIN}/partner.html?id=partner-plain" in sitemap.text
        for private_id in (
            "event-private-1", "article-draft-1", "person-draft-1", "person-private-1",
            "person-hidden-1", "person-pending-1", "article-private-1", "article-hidden-1",
            "article-pending-1", "article-draft-status-1", "partner-draft-1", "partner-private-1",
            "partner-unpublished-1", "partner-hidden-1", "partner-pending-1", "partner-paused-1",
        ):
            assert private_id not in sitemap.text
    engine.dispose()


def test_missing_routes_return_index_safe_custom_404(bare_client: TestClient):
    response = bare_client.get("/not-a-real-page.html")
    assert response.status_code == 404
    assert '<title>صفحه پیدا نشد | نورا</title>' in response.text
    assert 'name="robots" content="noindex,nofollow,noarchive"' in response.text
    assert "rel=\"canonical\"" not in response.text
    assert '<h1 id="page-title" class="art-title">صفحه پیدا نشد</h1>' in response.text

    static_missing = bare_client.get("/missing.js")
    assert static_missing.status_code == 404
    assert '<h1 id="page-title" class="art-title">صفحه پیدا نشد</h1>' in static_missing.text


def test_article_page_survives_resanitised_stored_content(tmp_path, monkeypatch):
    """Content saved through the owner PATCH is stored already-sanitised; the SEO
    snapshot sanitises it again, so a published article must keep its ``pub`` flag
    or ``post.html?id=`` turns into 404 for every article."""
    from backend.site_content import public_site_content, sanitize_site_content

    raw = {key: [] for key in ("events", "people", "articles", "partners", "banners", "cooperation", "library")}
    raw["articles"] = [{"id": "article-stored-1", "t": "مطلب ذخیره‌شده", "pub": True, "lead": "لید"}]
    stored = sanitize_site_content(raw)
    assert stored["articles"] and stored["articles"][0]["pub"] is True
    again = public_site_content(sanitize_site_content(stored))
    assert [item["id"] for item in again["articles"]] == ["article-stored-1"]
