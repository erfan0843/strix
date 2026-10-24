"""Publish clearly-labelled TEST site content (no banners) into the isolated preview DB."""
import sys
from owner_api import call, login
login()
st, cur = call("GET", "/api/owner/site-content")
assert st == 200, (st, cur)
version = cur["version"]
content = {
    "events": [
        {"id": "qa-ev-1", "t": "کارگاه آزمایشی ۱ (دادهٔ تست)", "kind": "کارگاه", "on": "1405/08/05", "when": "۵ آبان ۱۴۰۵",
         "time": "۱۸:۰۰", "place": "مکان آزمایشی", "mode": "حضوری", "d": "این رویداد فقط برای آزمون محیط ایزوله است.",
         "pub": True, "privacy": "public"},
        {"id": "qa-ev-2", "t": "نشست آزمایشی ۲ (دادهٔ تست)", "kind": "نشست", "on": "1405/08/12", "when": "۱۲ آبان ۱۴۰۵",
         "time": "۲۰:۰۰", "place": "آنلاین", "mode": "آنلاین", "d": "دادهٔ آزمایشی.", "pub": True, "privacy": "public"},
        {"id": "qa-ev-past", "t": "رویداد برگزارشدهٔ آزمایشی (دادهٔ تست)", "kind": "کارگاه", "on": "1405/06/10", "when": "۱۰ شهریور ۱۴۰۵",
         "place": "مکان آزمایشی", "past": True, "pub": True, "privacy": "public"},
    ],
    "articles": [
        {"id": "np-qa-1", "t": "مطلب آزمایشی ۱ (دادهٔ تست)", "cat": "یادداشت", "lead": "این مطلب فقط برای آزمون محیط ایزوله ساخته شده است.",
         "body": ["بند اول آزمایشی.", "بند دوم آزمایشی."], "pub": True, "at": "۱۴۰۵/۰۷/۲۵", "min": 2},
        {"id": "np-qa-2", "t": "مطلب آزمایشی ۲ (دادهٔ تست)", "cat": "گزارش", "lead": "دادهٔ آزمایشی دوم.",
         "body": ["بند آزمایشی."], "pub": True, "at": "۱۴۰۵/۰۷/۲۰", "min": 1},
    ],
    "people": [
        {"id": "qa-p1", "kind": "teacher", "n": "مدرس آزمایشی (دادهٔ تست)", "r": "نقش آزمایشی", "ini": "آ", "pub": True},
    ],
    "partners": [
        {"id": "qa-partner-1", "n": "نهاد همکار آزمایشی (دادهٔ تست)", "type": "آزمایشی", "pub": True},
    ],
}
if "--with-banners" in sys.argv:
    content["banners"] = [
        {"id": "qa-bnr-1", "status": "published", "active": True, "order": 1, "t": "بنر آزمایشی ۱ (دادهٔ تست)",
         "eyebrow": "آزمایشی", "subtitle": "زیرعنوان آزمایشی", "body": "متن کوتاه بنر آزمایشی برای بررسی نمایش.",
         "href": "events.html", "primaryLabel": "رویدادها", "theme": "ocean", "layout": "cover"},
        {"id": "qa-bnr-2", "status": "published", "active": True, "order": 2, "t": "بنر آزمایشی ۲ (دادهٔ تست)",
         "eyebrow": "آزمایشی", "body": "بنر دوم برای بررسی اسلاید.", "href": "support.html", "primaryLabel": "پشتیبانی",
         "secondaryHref": "events.html?status=past", "secondaryLabel": "آرشیو", "theme": "teal", "layout": "split"},
        {"id": "qa-bnr-draft", "status": "draft", "active": True, "t": "بنر پیش‌نویس (نباید دیده شود)"},
        {"id": "qa-bnr-off", "status": "published", "active": False, "t": "بنر غیرفعال (نباید دیده شود)"},
        {"id": "qa-bnr-expired", "status": "published", "active": True, "t": "بنر منقضی (نباید دیده شود)",
         "startsAt": "2020-01-01T00:00:00Z", "endsAt": "2020-02-01T00:00:00Z"},
    ]
    content["banner_settings"] = {"enabled": True, "auto_rotate": False, "interval_seconds": 7, "show_controls": True}
if "--no-banners" in sys.argv:
    content["banners"] = []
if "--banners-disabled" in sys.argv:
    content["banner_settings"] = {"enabled": False, "auto_rotate": False, "interval_seconds": 7, "show_controls": True}
st, body = call("PATCH", "/api/owner/site-content", {"content": content, "expected_version": version})
print(st, {k: len(v) if isinstance(v, list) else v for k, v in (body.get("content", {}) if isinstance(body, dict) else {}).items()} if st == 200 else body)
