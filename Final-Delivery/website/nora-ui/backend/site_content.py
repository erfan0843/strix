"""Allowlisted public-content snapshots for the Nora UI.

The browser's admin tools keep editable state locally. Only records explicitly
published by an owner are copied into this server-side public snapshot. Every
record is projected through an allowlist before persistence, so operational
fields (registration counts, invitation codes, private CRM data, and credentials)
never become public content.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

CONTENT_KEYS = ("events", "people", "articles", "partners", "banners", "cooperation", "library")
MAX_RECORDS = {
    "events": 500,
    "people": 500,
    "articles": 1000,
    "partners": 500,
    "banners": 100,
    "cooperation": 1,
    "library": 80,
}
_PUBLIC_FORM_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_DELIVERY_ID = re.compile(r"^[0-9a-f]{32}$")
_DATA_IMAGE = re.compile(r"^data:image/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$", re.I)
_DATA_MEDIA = re.compile(
    r"^data:(?:application/(?:pdf|zip|x-zip-compressed|octet-stream|epub[+]zip|vnd[.]openxmlformats-officedocument[.]wordprocessingml[.]document|vnd[.]openxmlformats-officedocument[.]presentationml[.]presentation)|audio/(?:mpeg|mp4|ogg|wav|webm)|video/(?:mp4|webm|ogg));base64,[A-Za-z0-9+/=]+$",
    re.I,
)
_DATA_FILE = re.compile(
    r"^data:(image/(?:jpeg|png|webp|gif)|application/(?:pdf|zip|x-zip-compressed|epub[+]zip|vnd[.]openxmlformats-officedocument[.](?:wordprocessingml[.]document|presentationml[.]presentation)|vnd[.]ms-powerpoint));base64,([A-Za-z0-9+/=]+)$",
    re.I,
)
_RELATIVE_URL = re.compile(r"^(?:\.{0,2}/|/)?[A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$")


class SiteContentError(ValueError):
    """A malformed or oversized public-content snapshot."""


def _text(value: Any, maximum: int, *, allow_number: bool = True) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        result = value.strip()
    elif allow_number and isinstance(value, (int, float)):
        result = str(value)
    else:
        return ""
    return result[:maximum]


def _list(value: Any, maximum: int) -> list[Any]:
    return value[:maximum] if isinstance(value, list) else []


def _text_list(value: Any, maximum: int = 40, item_length: int = 180) -> list[str]:
    return [item for item in (_text(entry, item_length) for entry in _list(value, maximum * 2)) if item][:maximum]


def _number(value: Any, *, minimum: int = 0, maximum: int = 100_000) -> int:
    if isinstance(value, bool):
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(minimum, min(maximum, result))


def _flag_active(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "none", "null"}
    return bool(value)


def _published_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return isinstance(value, str) and value.strip().lower() in {
        "1", "true", "yes", "on", "public", "published",
    }


def _public_record(record: Any, *, require_published: bool = False) -> bool:
    """Reject private/draft/pending records before they enter public pages or SEO."""
    if not isinstance(record, dict):
        return False
    if _flag_active(record.get("hidden")) or _flag_active(record.get("pend")):
        return False
    if "pub" in record and not _published_flag(record.get("pub")):
        return False
    for key in ("privacy", "visibility"):
        if key in record and record.get(key) is not None:
            visibility = str(record.get(key) or "").strip().lower()
            if visibility and visibility not in {"public", "published"}:
                return False
    status = _text(record.get("status"), 24, allow_number=False).lower()
    if status in {"draft", "private", "hidden", "pending", "unpublished", "rejected"}:
        return False
    return not require_published or _published_flag(record.get("pub"))


def _public_url(value: Any, *, image_data: bool = False) -> str:
    result = _text(value, 1_500_000 if image_data else 1_500, allow_number=False)
    if not result or "\\" in result or any(ord(char) < 32 for char in result):
        return ""
    if image_data and len(result) <= 1_500_000 and _DATA_IMAGE.fullmatch(result):
        return result
    try:
        parsed = urlsplit(result)
    except ValueError:
        return ""
    if parsed.scheme.lower() in {"http", "https"}:
        if not parsed.hostname or parsed.username or parsed.password:
            return ""
        return result
    if parsed.scheme.lower() in {"mailto", "tel"} and parsed.path:
        return result
    if not parsed.scheme and _RELATIVE_URL.fullmatch(result) and not re.search(r"(?:^|/)\.\.(?:/|$)", result):
        return result
    return ""


def _public_link(value: Any) -> str:
    """Allow safe same-site routes or HTTPS destinations for public call-to-action links."""
    result = _text(value, 2_048, allow_number=False)
    if not result or "\\" in result or any(ord(char) < 32 for char in result):
        return ""
    try:
        parsed = urlsplit(result)
    except ValueError:
        return ""
    if parsed.scheme:
        if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        return result
    if result.startswith("//") or parsed.netloc or not parsed.path and not parsed.fragment:
        return ""
    decoded_path = unquote(parsed.path)
    if (parsed.path and not _RELATIVE_URL.fullmatch(parsed.path)) or re.search(r"(?:^|/)\.\.(?:/|$)", decoded_path):
        return ""
    if parsed.query and not re.fullmatch(r"[A-Za-z0-9_.~%=&:+,-]{1,900}", parsed.query):
        return ""
    if parsed.fragment and not re.fullmatch(r"[A-Za-z0-9_.~%-]{1,160}", parsed.fragment):
        return ""
    return result


def _banner_datetime(value: Any) -> str:
    raw = _text(value, 40, allow_number=False)
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        return ""
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _public_media_url(value: Any) -> str:
    result = _text(value, 1_500_000, allow_number=False)
    if len(result) <= 1_500_000 and (_DATA_IMAGE.fullmatch(result) or _DATA_MEDIA.fullmatch(result)):
        return result
    return _public_url(result)


def _data_file(value: Any) -> tuple[str, str, int] | None:
    """Return an allowlisted inline file only after strict base64 validation."""
    raw = _text(value, 1_500_000, allow_number=False)
    match = _DATA_FILE.fullmatch(raw)
    if not match:
        return None
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error):
        return None
    if not content or len(content) > 8 * 1024 * 1024:
        return None
    return raw, match.group(1).lower(), len(content)


def _delivery_id(*parts: str) -> str:
    source = "nora-public-delivery\0" + "\0".join(parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


def _safe_filename(value: Any, fallback: str = "attachment") -> str:
    name = _text(value, 180, allow_number=False).replace(chr(92), "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable() and char not in {'"', "<", ">"})
    return name[:120] or fallback


def _forms(value: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in _list(value, 20):
        if not isinstance(item, dict):
            continue
        form_id = _text(item.get("id"), 120, allow_number=False)
        if not form_id or form_id in seen:
            continue
        seen.add(form_id)
        result.append({
            "id": form_id,
            "need": _text(item.get("need") or "reg", 24, allow_number=False),
            "n": _text(item.get("n") or item.get("name"), 160),
        })
    return result


def _parts(value: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _list(value, 80):
        if isinstance(item, str):
            part = {"title": _text(item, 240)}
        elif isinstance(item, dict):
            part = {
                "title": _text(item.get("title") or item.get("t") or item.get("n"), 240),
                "date": _text(item.get("date") or item.get("d"), 80),
                "time": _text(item.get("time") or item.get("t"), 80),
                "to": _text(item.get("to"), 80),
                "description": _text(item.get("description") or item.get("d"), 1_200),
            }
        else:
            continue
        if any(part.values()):
            result.append(part)
    return result


def _media(value: Any, event_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    file_kinds = {"image", "pdf", "slide", "file", "document"}
    file_suffixes = (".pdf", ".zip", ".epub", ".docx", ".pptx", ".ppt", ".jpg", ".jpeg", ".png", ".webp")
    for index, item in enumerate(_list(value, 100)):
        if not isinstance(item, dict):
            continue
        media_id = _text(item.get("id"), 100, allow_number=False) or f"media-{index}"
        kind = _text(item.get("k") or item.get("kind"), 24, allow_number=False).lower()
        title = _text(item.get("t") or item.get("n"), 240)
        mime = _text(item.get("mime"), 120, allow_number=False).lower()
        src = _public_media_url(item.get("src"))
        url = _public_url(item.get("url"))
        name = _safe_filename(item.get("file_name") or item.get("n") or title, "media")
        playable = kind in {"audio", "video", "aud", "vid"} or mime.startswith(("audio/", "video/"))
        looks_like_file = (
            kind in file_kinds
            or mime.startswith(("application/", "image/"))
            or name.lower().endswith(file_suffixes)
            or str(item.get("url") or item.get("src") or "").lower().split("?", 1)[0].endswith(file_suffixes)
        )
        file_data = _data_file(src) if looks_like_file and not playable else None
        row: dict[str, Any] = {
            "id": media_id,
            "k": kind or "file",
            "t": title,
            "d": _text(item.get("d") or item.get("at"), 240),
            "s": _text(item.get("s"), 80),
            "mime": mime,
            "src": src if playable or not looks_like_file else "",
            "url": url if playable or not looks_like_file else "",
            "external": bool(item.get("external")),
        }
        if looks_like_file and not playable:
            row["src"] = ""
            row["url"] = ""
            row["available"] = bool(file_data)
            if file_data:
                row.update({
                    "file_data": file_data[0],
                    "file_name": name,
                    "content_type": file_data[1],
                    "content_size": file_data[2],
                    "delivery_id": _delivery_id("event", event_id, media_id),
                })
        if row["id"] or row["t"] or row["src"] or row["url"]:
            result.append(row)
    return result


def _event(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    event_id = _text(record.get("id"), 100, allow_number=False)
    title = _text(record.get("t") or record.get("n") or record.get("name"), 240)
    if not event_id or not title or not _public_record(record):
        return None
    forms = _forms(record.get("forms"))
    past = bool(record.get("past") is True or record.get("pubPast") is True or record.get("state") == "past")
    candidate = _text(record.get("regForm"), 120, allow_number=False)
    if candidate and candidate not in {item["id"] for item in forms}:
        forms.append({"id": candidate, "need": "reg", "n": _text(record.get("regName"), 160)})
    return {
        "id": event_id,
        "t": title,
        "kind": _text(record.get("kind") or "رویداد", 80),
        "d": _text(record.get("d") or record.get("about") or record.get("description") or record.get("rep"), 10_000),
        "when": _text(record.get("when") or record.get("on") or record.get("d"), 120),
        # Machine-readable Jalali date the owner panel already stores (``on``);
        # the public list sorts by it and builds the month view from it.
        "on": _text(record.get("on"), 40),
        "time": _text(record.get("time"), 120),
        "place": _text(record.get("place"), 240),
        "mode": _text(record.get("mode"), 80),
        "poster": _public_url(record.get("poster"), image_data=True),
        "posterUp": _public_url(record.get("posterUp"), image_data=True),
        "tchr": _text(record.get("tchr"), 100, allow_number=False),
        "tags": _text_list(record.get("tags"), 20, 80),
        "parts": _parts(record.get("parts") or record.get("agenda") or record.get("sess")),
        "forms": forms,
        "price": _number(record.get("price"), maximum=100_000_000),
        "cap": _number(record.get("cap"), maximum=100_000),
        "past": past,
        "sess": _number(record.get("sess") or record.get("sessions"), maximum=500),
        "media": _media(record.get("media"), event_id) if past else [],
        "cert": bool(record.get("cert")),
        "certMin": _number(record.get("certMin"), maximum=100),
        "certNote": _text(record.get("certNote"), 1_000),
        "privacy": "public",
    }


def _person(record: Any) -> dict[str, Any] | None:
    if not _public_record(record):
        return None
    person_id = _text(record.get("id"), 100, allow_number=False)
    name = _text(record.get("n") or record.get("name"), 160)
    if not person_id or not name:
        return None
    links: list[dict[str, str]] = []
    for link in _list(record.get("links"), 12):
        if not isinstance(link, dict):
            continue
        kind = _text(link.get("k"), 24, allow_number=False).lower()
        value = _text(link.get("v"), 300, allow_number=False)
        if kind not in {"tel", "mail", "tg", "ig", "web"} or not value:
            continue
        if kind == "mail":
            value = _public_url("mailto:" + value.removeprefix("mailto:"))
        elif kind == "tel":
            value = _public_url("tel:" + value.removeprefix("tel:"))
        elif kind in {"tg", "ig"} and not value.startswith("http"):
            value = value.lstrip("@")
        else:
            value = _public_url(value if ":" in value else "https://" + value)
        if value:
            links.append({"k": kind, "v": value})
    form_id = _text(record.get("form"), 120, allow_number=False)
    return {
        "id": person_id,
        "n": name,
        "ini": _text(record.get("ini") or name[:1], 8),
        "r": _text(record.get("r") or record.get("role"), 240),
        "role2": _text(record.get("role2"), 240),
        "kind": "staff" if record.get("kind") == "staff" else "teacher",
        "bio": _text(record.get("bio"), 8_000),
        "quote": _text(record.get("quote"), 1_200),
        "where": _text(record.get("where"), 240),
        "yrs": _text(record.get("yrs"), 120),
        "courses": _text(record.get("courses"), 80),
        "rate": _text(record.get("rate"), 80),
        "tag": _text(record.get("tag"), 80),
        "exp": _text_list(record.get("exp"), 40, 160),
        "links": links,
        "photo": _public_url(record.get("photo"), image_data=True),
        "g": _text(record.get("g"), 240),
        "form": form_id,
        "formTxt": _text(record.get("formTxt"), 160),
    }


def _article_block(value: Any, article_id: str, index: int) -> dict[str, Any] | str | None:
    if isinstance(value, str):
        return _text(value, 8_000)
    if not isinstance(value, dict):
        return None
    block_type = _text(value.get("ty"), 20, allow_number=False)
    if block_type not in {"p", "h", "img", "vid", "aud", "q", "gal", "file", "bm", "tbl", "ul", "ol", "btn", "box", "tog", "hr"}:
        return None
    row: dict[str, Any] = {"ty": block_type}
    for key, limit in (("x", 8_000), ("t", 240), ("cap", 500), ("alt", 300), ("by", 200), ("kind", 40), ("ic", 40)):
        if key in value:
            raw = value[key]
            if isinstance(raw, list):
                row[key] = _text_list(raw, 100, 1_000)
            else:
                row[key] = _text(raw, limit)
    if block_type == "file":
        file_data = _data_file(_public_media_url(value.get("up") or value.get("src")))
        row["available"] = bool(file_data)
        if file_data:
            row.update({
                "file_data": file_data[0],
                "file_name": _safe_filename(value.get("file_name") or value.get("t") or "attachment.pdf"),
                "content_type": file_data[1],
                "content_size": file_data[2],
                "delivery_id": _delivery_id("article", article_id, str(index)),
            })
    else:
        for key in ("up", "src"):
            if key in value:
                row[key] = _public_media_url(value.get(key))
        if "href" in value:
            row["href"] = _public_url(value.get("href"))
    if "lv" in value:
        row["lv"] = 3 if _number(value.get("lv"), maximum=3) == 3 else 2
    if "w" in value:
        row["w"] = _number(value.get("w"), maximum=2_000)
    return row


def _article(record: Any) -> dict[str, Any] | None:
    if not _public_record(record, require_published=True):
        return None
    article_id = _text(record.get("id"), 100, allow_number=False)
    title = _text(record.get("t") or record.get("title"), 240)
    if not article_id or not title:
        return None
    blocks = [
        item for item in (
            _article_block(value, article_id, index)
            for index, value in enumerate(_list(record.get("blocks"), 100))
        ) if item
    ]
    return {
        "id": article_id,
        "t": title,
        "cat": _text(record.get("cat") or "مطلب", 80),
        "lead": _text(record.get("lead"), 1_000),
        "body": _text_list(record.get("body"), 100, 8_000),
        "blocks": blocks,
        "tags": _text_list(record.get("tags"), 40, 180),
        "cov": _public_url((record.get("cover") or {}).get("up") if isinstance(record.get("cover"), dict) else record.get("cov"), image_data=True),
        "who": _text(record.get("author") or record.get("who"), 160),
        "tchr": _text(record.get("tchr"), 100, allow_number=False),
        "views": _number(record.get("views"), maximum=1_000_000_000),
        "min": _number(record.get("min"), maximum=10_000),
        "g": _text((record.get("cover") or {}).get("g") if isinstance(record.get("cover"), dict) else record.get("g"), 240),
        "at": _text(record.get("at"), 80),
        "pin": bool(record.get("pin")),
        # پرچم انتشار باید در خروجی بماند؛ محتوای ذخیره‌شده دوباره پاک‌سازی می‌شود
        # (snapshot سئو، نقشهٔ سایت) و بدون آن مطلبِ منتشرشده حذف و post.html?id= به ۴۰۴ می‌افتاد.
        "pub": True,
    }


def _library(record: Any) -> dict[str, Any] | None:
    if (not isinstance(record, dict) or record.get("hidden") is True
            or record.get("pub") is False or record.get("pub") == 0
            or record.get("status") == "draft"):
        return None
    item_id = _text(record.get("id") or record.get("k"), 100, allow_number=False)
    title = _text(record.get("t") or record.get("title") or record.get("n"), 240)
    if not item_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", item_id) or not title:
        return None
    kind = _text(record.get("kind") or record.get("knd"), 40)
    source = _public_media_url(record.get("file") or record.get("src"))
    row: dict[str, Any] = {
        "id": item_id,
        "t": title,
        "kind": kind,
        "by": _text(record.get("by"), 180),
        "sub": _text(record.get("sub"), 240),
        "pub": True,
    }
    if kind.lower() in {"صدا", "audio", "پادکست"}:
        row["src"] = source
        row["mime"] = _text(record.get("mime"), 120, allow_number=False).lower()
        row["file_name"] = _safe_filename(record.get("fname") or record.get("file_name") or title, "audio")
    elif kind.lower() in {"کتاب", "book"}:
        file_data = _data_file(source)
        row["available"] = bool(file_data)
        if file_data:
            row.update({
                "file_data": file_data[0],
                "file_name": _safe_filename(record.get("fname") or record.get("file_name") or title, "book.pdf"),
                "content_type": file_data[1],
                "content_size": file_data[2],
                "delivery_id": _delivery_id("library", item_id),
            })
    return row


def _partner(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict) or record.get("hidden") is True or record.get("status") == "draft":
        return None
    partner_id = _text(record.get("id"), 100, allow_number=False)
    name = _text(record.get("n") or record.get("name"), 180)
    if not partner_id or not name:
        return None
    return {
        "id": partner_id,
        "n": name,
        "type": _text(record.get("type"), 160),
        "d": _text(record.get("d") or record.get("description"), 4_000),
        "logo": _public_url(record.get("logo"), image_data=True),
        "href": _public_url(record.get("href") or record.get("url")),
        "g": _text(record.get("g"), 240),
        "mon": _text(record.get("mon"), 8),
    }


def _banner(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    title = _text(record.get("t") or record.get("title"), 180)
    if not title:
        return None
    banner_id = _text(record.get("id"), 100, allow_number=False)
    if banner_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", banner_id):
        return None
    status = _text(record.get("status"), 16, allow_number=False).lower()
    if status not in {"draft", "published", "paused"}:
        status = "published" if record.get("pub") is True and record.get("hidden") is not True else "draft"
    layout = _text(record.get("layout"), 16, allow_number=False).lower()
    align = _text(record.get("align"), 16, allow_number=False).lower()
    theme = _text(record.get("theme"), 16, allow_number=False).lower()
    # نوع بنر برای برچسب‌گذاری شفاف محتوای تبلیغاتی/حامی در آینده؛ پیش‌فرض اعلان عادی است.
    kind = _text(record.get("kind"), 16, allow_number=False).lower()
    return {
        "id": banner_id,
        "status": status,
        "active": record.get("active") is not False and record.get("hidden") is not True,
        "order": _number(record.get("order"), maximum=1_000),
        "t": title,
        "eyebrow": _text(record.get("eyebrow") or record.get("tag"), 80),
        "subtitle": _text(record.get("subtitle") or record.get("m"), 180),
        "s": _text(record.get("s") or record.get("body") or record.get("description"), 800),
        "img": _public_url(record.get("img") or record.get("image"), image_data=True),
        "imgAlt": _text(record.get("imgAlt") or record.get("alt"), 240),
        "href": _public_link(record.get("href") or record.get("primary_href")),
        "primaryLabel": _text(record.get("primaryLabel") or record.get("primary_label"), 60),
        "secondaryHref": _public_link(record.get("secondaryHref") or record.get("secondary_href")),
        "secondaryLabel": _text(record.get("secondaryLabel") or record.get("secondary_label"), 60),
        "theme": theme if theme in {"ocean", "teal", "amber", "plum", "night"} else "ocean",
        "kind": kind if kind in {"sponsored", "partner"} else "notice",
        "layout": layout if layout in {"cover", "split", "text"} else "cover",
        "align": align if align in {"right", "center"} else "right",
        "overlay": _number(record.get("overlay"), maximum=90),
        "focusX": _number(record.get("focusX"), maximum=100),
        "focusY": _number(record.get("focusY"), maximum=100),
        "startsAt": _banner_datetime(record.get("startsAt") or record.get("starts_at")),
        "endsAt": _banner_datetime(record.get("endsAt") or record.get("ends_at")),
    }


def _banner_settings(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    interval = source.get("interval_seconds")
    if isinstance(interval, bool) or not isinstance(interval, (int, float)):
        interval = 7
    return {
        "enabled": source.get("enabled") is not False,
        "auto_rotate": source.get("auto_rotate") is True,
        "interval_seconds": _number(interval, minimum=4, maximum=20),
        "show_controls": source.get("show_controls") is not False,
    }


def _cooperation(record: Any) -> dict[str, str] | None:
    if not isinstance(record, dict):
        return None
    form_id = _text(record.get("formId"), 120, allow_number=False)
    if not _PUBLIC_FORM_ID.fullmatch(form_id):
        return None
    return {"formId": form_id}


def sanitize_site_content(value: Any, *, partial: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SiteContentError("invalid_site_content")
    allowed_fields = set(CONTENT_KEYS) | {"banner_settings"}
    unknown = set(value) - allowed_fields
    if unknown:
        raise SiteContentError("unexpected_site_content_fields")
    if not partial and not set(CONTENT_KEYS).issubset(value):
        raise SiteContentError("incomplete_site_content")
    sanitizers = {
        "events": _event,
        "people": _person,
        "articles": _article,
        "partners": _partner,
        "banners": _banner,
        "cooperation": _cooperation,
        "library": _library,
    }
    output: dict[str, Any] = {}
    for key, sanitizer in sanitizers.items():
        if key not in value:
            continue
        records = value[key]
        if not isinstance(records, list) or len(records) > MAX_RECORDS[key]:
            raise SiteContentError("invalid_site_content_records")
        normalized = [item for item in (sanitizer(row) for row in records) if item]
        seen: set[str] = set()
        for row in normalized:
            record_id = _text(row.get("id"), 100, allow_number=False) if isinstance(row, dict) else ""
            if record_id and record_id in seen:
                raise SiteContentError("duplicate_site_content_id")
            if record_id:
                seen.add(record_id)
        output[key] = normalized
    if "banner_settings" in value:
        if not isinstance(value["banner_settings"], dict):
            raise SiteContentError("invalid_banner_settings")
        output["banner_settings"] = _banner_settings(value["banner_settings"])
    return output


def public_site_content(content: Any) -> dict[str, Any]:
    """Project public content without drafts or downloadable private file bytes."""
    source = content if isinstance(content, dict) else {}
    public: dict[str, Any] = {key: list(source.get(key) or []) for key in CONTENT_KEYS}
    public["banners"] = [
        banner for banner in (_banner(item) for item in public["banners"])
        if banner and banner["status"] == "published" and banner["active"] is True
    ]
    public["banner_settings"] = _banner_settings(source.get("banner_settings"))
    for index, original in enumerate(public["events"]):
        if not isinstance(original, dict):
            continue
        event = dict(original)
        media_rows = []
        for media_index, original_media in enumerate(event.get("media") or []):
            if not isinstance(original_media, dict):
                continue
            media = dict(original_media)
            kind = str(media.get("k") or "").lower()
            mime = str(media.get("mime") or media.get("content_type") or "").lower()
            name = str(media.get("file_name") or media.get("t") or "").lower()
            playable = kind in {"audio", "video", "aud", "vid"} or mime.startswith(("audio/", "video/"))
            looks_like_file = (
                kind in {"image", "pdf", "slide", "file", "document"}
                or mime.startswith(("application/", "image/"))
                or name.endswith((".pdf", ".zip", ".epub", ".docx", ".pptx", ".ppt", ".jpg", ".jpeg", ".png", ".webp"))
            )
            if looks_like_file and not playable:
                raw = media.get("file_data") or media.get("src") or media.get("url")
                parsed = _data_file(raw)
                if parsed:
                    media.setdefault("delivery_id", _delivery_id(
                        "event", str(event.get("id") or index),
                        str(media.get("id") or f"media-{media_index}"),
                    ))
                    media["available"] = True
                    media.setdefault("file_name", _safe_filename(media.get("t"), "attachment"))
                    media.setdefault("content_type", parsed[1])
                    media.setdefault("content_size", parsed[2])
                else:
                    media["available"] = False
                media.pop("file_data", None)
                media["src"] = ""
                media["url"] = ""
            media_rows.append(media)
        event["media"] = media_rows
        public["events"][index] = event

    for index, original in enumerate(public["articles"]):
        if not isinstance(original, dict):
            continue
        article = dict(original)
        blocks = []
        for block_index, original_block in enumerate(article.get("blocks") or []):
            if not isinstance(original_block, dict) or original_block.get("ty") != "file":
                blocks.append(original_block)
                continue
            block = dict(original_block)
            parsed = _data_file(block.get("file_data") or block.get("up") or block.get("src"))
            if parsed:
                block.setdefault("delivery_id", _delivery_id(
                    "article", str(article.get("id") or index), str(block_index)
                ))
                block["available"] = True
                block.setdefault("file_name", _safe_filename(block.get("t"), "attachment"))
                block.setdefault("content_type", parsed[1])
                block.setdefault("content_size", parsed[2])
            else:
                block["available"] = False
            for key in ("file_data", "up", "src", "href"):
                block.pop(key, None)
            blocks.append(block)
        article["blocks"] = blocks
        public["articles"][index] = article

    for index, original in enumerate(public["library"]):
        if not isinstance(original, dict):
            continue
        item = dict(original)
        kind = str(item.get("kind") or "").lower()
        if kind in {"کتاب", "book"}:
            parsed = _data_file(item.get("file_data") or item.get("file") or item.get("src"))
            if parsed:
                item.setdefault("delivery_id", _delivery_id("library", str(item.get("id") or item.get("k") or "")))
                item["available"] = True
                item.setdefault("file_name", _safe_filename(item.get("fname") or item.get("t"), "book.pdf"))
                item.setdefault("content_type", parsed[1])
                item.setdefault("content_size", parsed[2])
            else:
                item["available"] = False
            for key in ("file_data", "file", "src"):
                item.pop(key, None)
        elif kind not in {"صدا", "audio", "پادکست"}:
            for key in ("file_data", "file", "src"):
                item.pop(key, None)
        else:
            item.pop("file_data", None)
            item.pop("file", None)
        public["library"][index] = item
    return public


def resolve_public_delivery_file(content: Any, delivery_id: str) -> tuple[bytes, str, str] | None:
    """Resolve a published attachment for the authenticated bot service only."""
    if not isinstance(delivery_id, str) or not _DELIVERY_ID.fullmatch(delivery_id):
        return None
    if not isinstance(content, dict):
        return None
    candidates: list[tuple[dict[str, Any], str]] = []
    for item in content.get("library", []) if isinstance(content.get("library"), list) else []:
        if isinstance(item, dict):
            candidates.append((item, _delivery_id("library", str(item.get("id") or item.get("k") or ""))))
    for event in content.get("events", []) if isinstance(content.get("events"), list) else []:
        if not isinstance(event, dict):
            continue
        for index, item in enumerate(event.get("media", []) if isinstance(event.get("media"), list) else []):
            if isinstance(item, dict):
                candidates.append((item, _delivery_id(
                    "event", str(event.get("id") or ""), str(item.get("id") or f"media-{index}")
                )))
    for article in content.get("articles", []) if isinstance(content.get("articles"), list) else []:
        if not isinstance(article, dict):
            continue
        for index, item in enumerate(article.get("blocks", []) if isinstance(article.get("blocks"), list) else []):
            if isinstance(item, dict) and item.get("ty") == "file":
                candidates.append((item, _delivery_id("article", str(article.get("id") or ""), str(index))))
    for item, expected_id in candidates:
        if item.get("delivery_id") != delivery_id and expected_id != delivery_id:
            continue
        source = item.get("file_data") or item.get("file") or item.get("src") or item.get("up")
        parsed = _data_file(source)
        if not parsed:
            return None
        try:
            payload = base64.b64decode(parsed[0].split(",", 1)[1], validate=True)
        except (ValueError, binascii.Error):
            return None
        if len(payload) != parsed[2]:
            return None
        fallback = {
            "application/pdf": "attachment.pdf",
            "application/epub+zip": "book.epub",
            "application/zip": "attachment.zip",
            "application/x-zip-compressed": "attachment.zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "attachment.docx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "attachment.pptx",
            "application/vnd.ms-powerpoint": "attachment.ppt",
            "image/jpeg": "attachment.jpg",
            "image/png": "attachment.png",
            "image/webp": "attachment.webp",
            "image/gif": "attachment.gif",
        }.get(parsed[1], "attachment")
        return payload, parsed[1], _safe_filename(item.get("file_name") or item.get("fname") or item.get("t"), fallback)
    return None
