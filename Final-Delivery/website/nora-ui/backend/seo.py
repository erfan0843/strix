"""SEO metadata and public URL helpers for the Nora UI.

The domain is deliberately configuration-only: canonical URLs and sitemap
locations must never be guessed from an untrusted Host header or a sample URL.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
from typing import Any, Mapping
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape as xml_escape

SITE_NAME = "نورا"
ORGANIZATION_NAME = "گروه فرهنگی خط زندگی"
SITE_DESCRIPTION = "رویدادها، مطالب و پروفایل‌های عمومی منتشرشده در نورا."
DEFAULT_HOME_DESCRIPTION = (
    "رویدادها، مطالب و پروفایل‌های عمومی منتشرشدهٔ گروه فرهنگی خط زندگی را در نورا ببینید."
)
DEFAULT_EVENTS_DESCRIPTION = "فهرست رویدادها و برنامه‌های عمومی منتشرشده در نورا."
_RESERVED_HOST_SUFFIXES = {
    "example", "invalid", "localhost", "local", "internal", "lan", "test", "onion",
}
_RESERVED_EXAMPLE_DOMAINS = {"example.com", "example.net", "example.org"}
_DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_COUNTRY_CODE = re.compile(r"[A-Za-z]{2}\Z")
_TELEPHONE = re.compile(r"\+?[0-9][0-9 .()/-]{5,30}\Z")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_public_base_url(value: str | None) -> str:
    """Accept only an explicit HTTPS origin, never a path or request Host."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) > 512 or any(char.isspace() for char in raw) or "\\" in raw:
        raise ValueError("NORA_PUBLIC_BASE_URL must be a public HTTPS origin")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise ValueError("NORA_PUBLIC_BASE_URL must be a public HTTPS origin") from None
    hostname = (parsed.hostname or "").rstrip(".")
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("NORA_PUBLIC_BASE_URL must be a public HTTPS origin without a path")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_host = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise ValueError("NORA_PUBLIC_BASE_URL must contain a valid public hostname") from None
        if any(
            ascii_host == domain or ascii_host.endswith("." + domain)
            for domain in _RESERVED_EXAMPLE_DOMAINS
        ):
            raise ValueError("NORA_PUBLIC_BASE_URL must not use a reserved example domain")
        labels = ascii_host.split(".")
        if (
            len(ascii_host) > 253
            or len(labels) < 2
            or labels[-1] in _RESERVED_HOST_SUFFIXES
            or not all(_DOMAIN_LABEL.fullmatch(label) for label in labels)
        ):
            raise ValueError("NORA_PUBLIC_BASE_URL must contain a public fully-qualified hostname")
        hostname = ascii_host
    else:
        if not address.is_global:
            raise ValueError("NORA_PUBLIC_BASE_URL must not use a private or reserved IP address")
        hostname = address.compressed
        if address.version == 6:
            hostname = f"[{hostname}]"
    port_suffix = f":{port}" if port is not None and port != 443 else ""
    return f"https://{hostname}{port_suffix}"


def normalize_local_business(
    *,
    name: str = "",
    street_address: str = "",
    locality: str = "",
    postal_code: str = "",
    country_code: str = "",
    telephone: str = "",
    description: str = "",
) -> dict[str, str] | None:
    """Validate explicitly supplied official business details; no defaults are invented."""
    values = {
        "name": str(name or "").strip(),
        "street_address": str(street_address or "").strip(),
        "locality": str(locality or "").strip(),
        "postal_code": str(postal_code or "").strip(),
        "country_code": str(country_code or "").strip().upper(),
        "telephone": str(telephone or "").strip(),
        "description": str(description or "").strip(),
    }
    if not any(values.values()):
        return None
    required = ("name", "street_address", "locality", "postal_code", "country_code", "telephone")
    if any(not values[key] for key in required):
        raise ValueError(
            "LocalBusiness schema needs NORA_SEO_BUSINESS_NAME, STREET_ADDRESS, "
            "LOCALITY, POSTAL_CODE, COUNTRY_CODE, and TELEPHONE together"
        )
    if any(len(values[key]) > limit for key, limit in {
        "name": 160, "street_address": 180, "locality": 120, "postal_code": 32,
        "country_code": 2, "telephone": 32, "description": 500,
    }.items()):
        raise ValueError("LocalBusiness schema fields exceed their maximum length")
    if any(_CONTROL_CHARS.search(values[key]) for key in values):
        raise ValueError("LocalBusiness schema fields must not contain control characters")
    if not _COUNTRY_CODE.fullmatch(values["country_code"]):
        raise ValueError("NORA_SEO_BUSINESS_COUNTRY_CODE must be a two-letter country code")
    if not _TELEPHONE.fullmatch(values["telephone"]):
        raise ValueError("NORA_SEO_BUSINESS_TELEPHONE must be a public telephone number")
    return values


def _plain_text(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    value = " ".join(value.split())
    return value[:limit].rstrip()


def _public_id(value: Any) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    result = str(value).strip()
    return result[:100] if result and not _CONTROL_CHARS.search(result) else ""


def _seo_flag_active(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "none", "null"}
    return bool(value)


def _seo_published_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return isinstance(value, str) and value.strip().lower() in {
        "1", "true", "yes", "on", "public", "published",
    }


def _encoded_id(value: Any) -> str:
    return quote(_public_id(value), safe="-._~")


def canonical_path(page_name: str, item_id: str | None = None) -> str:
    """Return the stable public route, excluding tracking and preview parameters."""
    page = str(page_name or "").strip().lower()
    if page in {"home", "index"}:
        return "/"
    if page in {"event", "post", "person"}:
        identifier = _public_id(item_id)
        if not identifier:
            return ""
        return f"/{page}.html?id={_encoded_id(identifier)}"
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", page):
        return ""
    return f"/{page}.html"


def canonical_url(base_url: str, path: str) -> str:
    if not path or not path.startswith("/") or path.startswith("//"):
        return ""
    base = normalize_public_base_url(base_url)
    return f"{base}{path}" if base else path


def robots_txt(base_url: str = "") -> str:
    lines = [
        "User-agent: *",
        "Allow: /",
        # Let crawlers read noindex metadata on utility pages; robots.txt is not access control.
        "Disallow: /api/",
    ]
    base = normalize_public_base_url(base_url)
    if base:
        lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines) + "\n"


def sitemap_xml(base_url: str, content: Mapping[str, Any] | None = None) -> str:
    """Build an absolute-URL sitemap from the explicit canonical origin."""
    base = normalize_public_base_url(base_url)
    if not base:
        raise ValueError("NORA_PUBLIC_BASE_URL is required to generate an absolute sitemap")
    paths = {"/", "/events.html"}
    snapshot = content if isinstance(content, Mapping) else {}
    for kind, key in (("event", "events"), ("post", "articles"), ("person", "people")):
        rows = snapshot.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            status = _plain_text(row.get("status"), 24).lower()
            visibility = _plain_text(row.get("privacy") or row.get("visibility"), 24).lower()
            if (
                _seo_flag_active(row.get("hidden"))
                or _seo_flag_active(row.get("pend"))
                or ("pub" in row and not _seo_published_flag(row.get("pub")))
                or (visibility and visibility not in {"public", "published"})
                or status in {"draft", "private", "hidden", "pending", "unpublished", "rejected"}
            ):
                continue
            path = canonical_path(kind, _public_id(row.get("id")))
            if path:
                paths.add(path)
    entries = "".join(f"  <url><loc>{xml_escape(base + path)}</loc></url>\n" for path in sorted(paths))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}</urlset>\n"
    )


def _safe_json(value: Any) -> str:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _absolute_asset(base_url: str, path: Any) -> str:
    value = _plain_text(path, 1_500)
    if not value:
        return ""
    if value.startswith("https://"):
        return value
    base = normalize_public_base_url(base_url)
    if base and value.startswith("/") and not value.startswith("//"):
        return base + value
    if base and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value) and ".." not in value.split("/"):
        return base + "/" + value.lstrip("./")
    return ""


def absolute_asset_url(base_url: str, value: Any) -> str:
    """Resolve a public image URL for social metadata without trusting relative traversal."""
    return _absolute_asset(base_url, value)


def structured_data(
    *,
    base_url: str,
    title: str,
    description: str,
    page_url: str,
    page_type: str = "WebPage",
    item: Mapping[str, Any] | None = None,
    local_business: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create JSON-LD using only supplied public content and explicit business data."""
    base = normalize_public_base_url(base_url)
    graph: list[dict[str, Any]] = []
    org: dict[str, Any] = {
        "@type": "Organization",
        "name": ORGANIZATION_NAME,
        "alternateName": SITE_NAME,
        "description": SITE_DESCRIPTION,
    }
    website: dict[str, Any] = {"@type": "WebSite", "name": SITE_NAME, "inLanguage": "fa"}
    if base:
        org.update({"@id": f"{base}/#organization", "url": base})
        website.update({"@id": f"{base}/#website", "url": base, "publisher": {"@id": f"{base}/#organization"}})
    graph.extend((org, website))
    if local_business:
        local: dict[str, Any] = {
            "@type": "LocalBusiness",
            "name": local_business["name"],
            "telephone": local_business["telephone"],
            "address": {
                "@type": "PostalAddress",
                "streetAddress": local_business["street_address"],
                "addressLocality": local_business["locality"],
                "postalCode": local_business["postal_code"],
                "addressCountry": local_business["country_code"],
            },
        }
        if local_business.get("description"):
            local["description"] = local_business["description"]
        if base:
            local.update({"@id": f"{base}/#localbusiness", "url": base})
        graph.append(local)

    page: dict[str, Any] = {
        "@type": page_type,
        "name": _plain_text(title, 240),
        "description": _plain_text(description, 600),
        "inLanguage": "fa",
    }
    if page_url.startswith("https://"):
        page["url"] = page_url
        page["@id"] = page_url + "#webpage"
    if base:
        page["isPartOf"] = {"@id": f"{base}/#website"}
        page["publisher"] = {"@id": f"{base}/#organization"}

    public_item = item if isinstance(item, Mapping) else {}
    if page_type == "Article":
        page["headline"] = _plain_text(public_item.get("t") or title, 240)
        if public_item.get("who"):
            page["author"] = {"@type": "Person", "name": _plain_text(public_item.get("who"), 160)}
        page["publisher"] = {"@id": f"{base}/#organization"} if base else {"@type": "Organization", "name": ORGANIZATION_NAME}
        cover = _absolute_asset(base, public_item.get("cov"))
        if cover:
            page["image"] = cover
    elif page_type == "ProfilePage":
        person: dict[str, Any] = {
            "@type": "Person",
            "name": _plain_text(public_item.get("n") or title, 160),
        }
        if public_item.get("r"):
            person["jobTitle"] = _plain_text(public_item.get("r"), 240)
        if public_item.get("bio"):
            person["description"] = _plain_text(public_item.get("bio"), 600)
        photo = _absolute_asset(base, public_item.get("photo"))
        if photo:
            person["image"] = photo
        page["mainEntity"] = person

    graph.append(page)
    if base and page_url.startswith("https://") and page_url.rstrip("/") != base:
        crumbs = [{"@type": "ListItem", "position": 1, "name": "خانه", "item": base + "/"}]
        if page_type in {"Article", "ProfilePage"}:
            crumbs.append({"@type": "ListItem", "position": 2, "name": "مطالب" if page_type == "Article" else "پروفایل‌ها",
                           "item": base + ("/#articles" if page_type == "Article" else "/#teachers")})
        elif page_type == "WebPage" and "/event.html?" in page_url:
            crumbs.append({"@type": "ListItem", "position": 2, "name": "رویدادها", "item": base + "/events.html"})
        crumbs.append({"@type": "ListItem", "position": len(crumbs) + 1, "name": _plain_text(title, 240), "item": page_url})
        graph.append({"@type": "BreadcrumbList", "itemListElement": crumbs})
    return {"@context": "https://schema.org", "@graph": graph}


def _replace_tag(html_text: str, pattern: re.Pattern[str], replacement: str, *, insert_before: str = "</head>") -> str:
    if pattern.search(html_text):
        return pattern.sub(replacement, html_text, count=1)
    position = html_text.lower().find(insert_before.lower())
    return html_text[:position] + replacement + "\n" + html_text[position:] if position >= 0 else html_text


def _replace_content_attr(tag: str, content: str) -> str:
    escaped = html.escape(content, quote=True)
    attr = re.compile(r"\bcontent\s*=\s*([\"']).*?\1", re.I | re.S)
    if attr.search(tag):
        return attr.sub(f'content="{escaped}"', tag, count=1)
    return tag[:-1] + f' content="{escaped}">'


def apply_page_metadata(
    html_text: str,
    *,
    title: str,
    description: str,
    robots: str,
    canonical: str = "",
    og_type: str = "website",
    image: str = "",
    json_ld: Mapping[str, Any] | None = None,
    body_fragment: str | None = None,
) -> str:
    """Apply escaped page metadata to an existing HTML template."""
    html_text = re.sub(r"<title\b[^>]*>.*?</title\s*>", f"<title>{html.escape(title)}</title>", html_text, count=1, flags=re.I | re.S)
    selectors = (
        ("name", "description", description),
        ("property", "og:type", og_type),
        ("property", "og:site_name", SITE_NAME),
        ("property", "og:title", title),
        ("property", "og:description", description),
        ("name", "twitter:title", title),
        ("name", "twitter:description", description),
        ("name", "robots", robots),
    )
    for attr, key, value in selectors:
        tag_pattern = re.compile(
            rf"<meta\b(?=[^>]*\b{attr}\s*=\s*([\"']){re.escape(key)}\1)[^>]*>", re.I | re.S
        )
        tag = tag_pattern.search(html_text)
        replacement = _replace_content_attr(tag.group(0), value) if tag else f'<meta {attr}="{html.escape(key, quote=True)}" content="{html.escape(value, quote=True)}"/>'
        html_text = _replace_tag(html_text, tag_pattern, replacement)

    if image:
        tag_pattern = re.compile(r'<meta\b(?=[^>]*\bproperty\s*=\s*(["\'])og:image\1)[^>]*>', re.I | re.S)
        tag = tag_pattern.search(html_text)
        replacement = _replace_content_attr(tag.group(0), image) if tag else f'<meta property="og:image" content="{html.escape(image, quote=True)}"/>'
        html_text = _replace_tag(html_text, tag_pattern, replacement)

    canonical_pattern = re.compile(r'<link\b(?=[^>]*\brel\s*=\s*(["\'])canonical\1)[^>]*>', re.I | re.S)
    if canonical:
        canonical_tag = f'<link rel="canonical" href="{html.escape(canonical, quote=True)}"/>'
        html_text = _replace_tag(html_text, canonical_pattern, canonical_tag)
    elif canonical_pattern.search(html_text):
        html_text = canonical_pattern.sub("", html_text, count=1)

    if body_fragment is not None:
        html_text = html_text.replace("<!--nora-seo-content-->", body_fragment, 1)
    if json_ld is not None:
        script = f'<script id="nora-structured-data" type="application/ld+json">{_safe_json(json_ld)}</script>'
        marker = "<!--nora-seo-jsonld-->"
        if marker in html_text:
            html_text = html_text.replace(marker, script, 1)
        else:
            position = html_text.lower().find("</head>")
            if position >= 0:
                html_text = html_text[:position] + script + "\n" + html_text[position:]
    return html_text


def default_page_description(page_name: str) -> str:
    return {
        "home": DEFAULT_HOME_DESCRIPTION,
        "index": DEFAULT_HOME_DESCRIPTION,
        "events": DEFAULT_EVENTS_DESCRIPTION,
        "event": "اطلاعات رویدادهای عمومی و برنامه‌های منتشرشده در نورا.",
        "post": "مطالب و نوشته‌های عمومی منتشرشده در نورا.",
        "person": "پروفایل‌های عمومی و تأییدشدهٔ نورا.",
        "support": "راهنمای استفاده و اطلاعات پشتیبانی نورا.",
        "login": "ورود امن به حساب نورا.",
        "account": "مدیریت اعلان‌ها و فایل‌های حساب کاربری در نورا.",
        "admin": "پنل مدیریت نورا برای کاربران مجاز.",
        "builder": "مرکز مدیریت فرم‌ها در نورا.",
        "create": "ساخت و ویرایش فرم در پنل مجاز نورا.",
        "form": "فرم عمومی نورا؛ وضعیت و دسترسی هر فرم از سرور بررسی می‌شود.",
        "offline": "راهنمای بازگشت به نورا هنگام قطع اتصال اینترنت.",
        "404": "صفحه‌ای از دفتر نورا جا مانده؛ به خانه برگردید یا رویدادهای نورا را ببینید.",
        "final-page-review": "پیش‌نمایش نمایشی صفحهٔ تکمیل درخواست در نورا.",
        "loading-preview": "پیش‌نمایش حالت بارگذاری نورا.",
        "nora-pay-preview": "پیش‌نمایش رابط پرداخت نورا؛ این صفحه پرداخت واقعی انجام نمی‌دهد.",
    }.get(page_name, DEFAULT_HOME_DESCRIPTION)


def dynamic_page_values(page_name: str, item: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    """Return (title, description, canonical path, schema type, og type)."""
    if page_name == "event":
        title = f"{_plain_text(item.get('t'), 180)} | رویدادهای نورا"
        description = _plain_text(item.get("d"), 240) or f"اطلاعات رویداد {_plain_text(item.get('t'), 160)} در نورا."
        return title, description, canonical_path("event", _public_id(item.get("id"))), "WebPage", "article"
    if page_name == "post":
        title = f"{_plain_text(item.get('t'), 180)} | مطالب نورا"
        description = _plain_text(item.get("lead"), 240)
        if not description:
            for block in item.get("blocks", []) if isinstance(item.get("blocks"), list) else []:
                if isinstance(block, Mapping) and block.get("ty") == "p":
                    description = _plain_text(block.get("x"), 240)
                    if description:
                        break
        if not description:
            description = f"مطلب «{_plain_text(item.get('t'), 160)}» در نورا."
        return title, description, canonical_path("post", _public_id(item.get("id"))), "Article", "article"
    title = f"{_plain_text(item.get('n'), 160)} | پروفایل نورا"
    description = _plain_text(item.get("bio"), 240) or _plain_text(item.get("r"), 240) or f"پروفایل عمومی {_plain_text(item.get('n'), 140)} در نورا."
    return title, description, canonical_path("person", _public_id(item.get("id"))), "ProfilePage", "profile"
