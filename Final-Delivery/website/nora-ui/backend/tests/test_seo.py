from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.seo import (  # noqa: E402
    absolute_asset_url,
    apply_page_metadata,
    canonical_path,
    normalize_local_business,
    normalize_public_base_url,
    robots_txt,
    sitemap_xml,
    structured_data,
)


def test_public_origin_requires_explicit_safe_https_origin():
    assert normalize_public_base_url(" https://www.nora.seo-test-domain:443/ ") == "https://www.nora.seo-test-domain"
    assert normalize_public_base_url("https://xn--mgba3a4f16a.ir:8443") == "https://xn--mgba3a4f16a.ir:8443"
    assert normalize_public_base_url("") == ""
    for invalid in (
        "http://www.nora.seo-test-domain",
        "https://www.nora.seo-test-domain/path",
        "https://user:pass@www.nora.seo-test-domain",
        "https://localhost",
        "https://www.nora.example.org",
        "https://nora.test",
        "https://192.168.1.10",
        "https://example.invalid",
    ):
        with pytest.raises(ValueError):
            normalize_public_base_url(invalid)


def test_local_business_requires_complete_official_fields_and_validates_country_and_phone():
    assert normalize_local_business() is None
    with pytest.raises(ValueError, match="needs"):
        normalize_local_business(name="Only a name")
    valid = normalize_local_business(
        name="Example Test Office",
        street_address="1 Test Street",
        locality="Test City",
        postal_code="10000",
        country_code="us",
        telephone="+12125550100",
        description="Official test configuration",
    )
    assert valid is not None
    assert valid["country_code"] == "US"
    with pytest.raises(ValueError):
        normalize_local_business(
            name="Example Test Office", street_address="1 Test Street", locality="Test City",
            postal_code="10000", country_code="USA", telephone="+12125550100",
        )


def test_canonical_routes_encode_ids_and_reject_missing_or_unsafe_values():
    assert canonical_path("home") == "/"
    assert canonical_path("event", "course 1/آغاز") == "/event.html?id=course%201%2F%D8%A2%D8%BA%D8%A7%D8%B2"
    assert canonical_path("person", "") == ""
    assert canonical_path("event", "../private") == "/event.html?id=..%2Fprivate"
    assert canonical_path("unknown page") == ""
    assert absolute_asset_url("", "data:image/png;base64,AAAA") == ""
    assert absolute_asset_url("https://www.nora.seo-test-domain", "/images/cover.png") == "https://www.nora.seo-test-domain/images/cover.png"
    assert absolute_asset_url("https://www.nora.seo-test-domain", "../private.png") == ""


def test_robots_and_sitemap_never_infer_domain_or_publish_nonpublic_records():
    robots = robots_txt()
    assert "Sitemap:" not in robots
    assert "Disallow: /api/" in robots
    assert "Disallow: /form.html" not in robots
    with pytest.raises(ValueError, match="required"):
        sitemap_xml("")

    sitemap = sitemap_xml("https://www.nora.seo-test-domain", {
        "events": [
            {"id": "public-event"}, {"id": "draft-event", "status": "draft"},
            {"id": "private-event", "privacy": "private"}, {"id": "hidden-event", "hidden": True},
            {"id": "pending-event", "pend": True},
        ],
        "articles": [
            {"id": "public-article"}, {"id": "draft-article", "pub": False},
            {"id": "private-article", "pub": True, "privacy": "private"},
            {"id": "hidden-article", "pub": True, "hidden": True},
            {"id": "pending-article", "pub": True, "pend": True},
        ],
        "people": [
            {"id": "public-person"}, {"id": "private-person", "privacy": "private"},
            {"id": "hidden-person", "hidden": True}, {"id": "unlisted-person", "visibility": "unlisted"},
        ],
    })
    assert "https://www.nora.seo-test-domain/event.html?id=public-event" in sitemap
    assert "https://www.nora.seo-test-domain/post.html?id=public-article" in sitemap
    assert "https://www.nora.seo-test-domain/person.html?id=public-person" in sitemap
    assert sitemap.count("<url><loc>") == 5
    for private_id in (
        "draft-event", "private-event", "hidden-event", "pending-event",
        "draft-article", "private-article", "hidden-article", "pending-article",
        "private-person", "hidden-person", "unlisted-person",
    ):
        assert private_id not in sitemap
    assert "<loc>http://" not in sitemap


def test_metadata_injection_escapes_content_and_replaces_canonical_and_jsonld_safely():
    source = (
        '<html><head><title>Old title</title><meta name="description" content="old">'
        '<link rel="canonical" href="/old"></head><body><main><!--nora-seo-content--></main></body></html>'
    )
    output = apply_page_metadata(
        source,
        title='A "quoted" title <script>alert(1)</script>',
        description='description & <b>bold</b>',
        robots="index,follow",
        canonical="https://www.nora.seo-test-domain/event.html?id=a%2Fb",
        json_ld={"name": "</script><script>alert(1)</script>"},
        body_fragment='<h1>Safe &amp; escaped</h1>',
    )
    assert output.count("<title>") == 1
    assert "&lt;script&gt;" in output
    assert "content=\"description &amp; &lt;b&gt;bold&lt;/b&gt;\"" in output
    assert '<link rel="canonical" href="https://www.nora.seo-test-domain/event.html?id=a%2Fb"/>' in output
    assert "nora-seo-content" not in output
    assert "\\u003c/script\\u003e" in output
    assert "<script>alert(1)</script>" not in output


def test_jsonld_includes_only_supplied_business_data_and_page_breadcrumbs():
    without_business = structured_data(
        base_url="https://www.nora.seo-test-domain",
        title="Public event",
        description="A public event",
        page_url="https://www.nora.seo-test-domain/event.html?id=public",
        page_type="WebPage",
    )
    graph = without_business["@graph"]
    assert any(item["@type"] == "Organization" for item in graph)
    assert not any(item["@type"] == "LocalBusiness" for item in graph)
    assert any(item["@type"] == "BreadcrumbList" for item in graph)
    encoded = json.dumps(without_business, ensure_ascii=False)
    assert "seo-test-domain" in encoded

    supplied_business = normalize_local_business(
        name="Example Test Office", street_address="1 Test Street", locality="Test City",
        postal_code="10000", country_code="US", telephone="+12125550100",
        description="Official test configuration",
    )
    with_business = structured_data(
        base_url="https://www.nora.seo-test-domain",
        title="Public event",
        description="A public event",
        page_url="https://www.nora.seo-test-domain/event.html?id=public",
        page_type="WebPage",
        local_business=supplied_business,
    )
    local = next(item for item in with_business["@graph"] if item["@type"] == "LocalBusiness")
    assert local["name"] == "Example Test Office"
    assert local["address"]["streetAddress"] == "1 Test Street"
    assert local["address"]["addressCountry"] == "US"
    assert local["telephone"] == "+12125550100"
