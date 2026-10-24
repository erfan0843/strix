"""Publish clearly-labelled TEST partners (+ event→partner relation) into the isolated preview DB."""
import json, sys
from owner_api import call, login
login()
st, cur = call("GET", "/api/owner/site-content"); assert st == 200, (st, cur)
content = cur["content"]; version = cur["version"]
long_name = "نهاد همکار با نام بسیار طولانی برای آزمون شکست خط و چیدمان در موبایل و دسکتاپ (دادهٔ تست)"
long_desc = ("این شرح فقط برای آزمون چیدمان است و هیچ نهاد واقعی را معرفی نمی‌کند. " * 12).strip()
content["partners"] = [
    {"id": "qa-partner-1", "n": "نهاد همکار آزمایشی (دادهٔ تست)", "type": "نهاد فرهنگی · آزمایشی",
     "s": "همراه برنامه‌های آموزشی در محیط آزمایشی؛ این متن دادهٔ تست است.",
     "collab": "برگزاری کارگاه (تست)", "since": "مهر ۱۴۰۵", "focus": ["آموزش", "کارگاه", "کتاب‌خوانی"],
     "d": "شرح کامل همکاری آزمایشی.\nخط دوم شرح برای آزمون شکست خط.",
     "logo": "/icon-192.png", "href": "https://example.org/partner-test",
     "links": [{"k": "mail", "v": "hello@example.org"}, {"k": "tel", "v": "+33 1 23 45 67 89"},
               {"k": "tg", "v": "@nora_test_channel"}, {"k": "web", "v": "javascript:alert(1)"},
               {"k": "other", "v": "//evil.example/x"}],
     "mon": "آز", "g": "linear-gradient(135deg,#2E6B7A,#0B2447)", "pub": True},
    {"id": "qa partner/2 ü", "n": long_name, "type": "آزمایشی", "d": long_desc,
     "href": "https://example.org/" + "a-very-long-path-segment/" * 6 + "end?with=query&and=more",
     "mon": "طو", "g": "linear-gradient(135deg,#7A5A2A,#123A7A)", "pub": True},
    {"id": "qa-partner-broken-logo", "n": "نهاد با لوگوی شکسته (دادهٔ تست)", "type": "آزمایشی",
     "logo": "/uploads/does-not-exist-qa.webp", "s": "لوگوی این نهاد عمداً به مسیری ناموجود اشاره می‌کند.", "pub": True},
    {"id": "qa-partner-xss", "n": "<img src=x onerror=alert(1)> نهاد (دادهٔ تست)", "type": "<b>نوع</b>",
     "d": "<script>alert(1)</script> شرح", "logo": "javascript:alert(1)", "href": "https://user:pw@example.org/",
     "links": [{"k": "web", "v": "javascript:alert(1)"}], "pub": True},
    {"id": "qa-partner-unpublished", "n": "نهاد منتشرنشده (دادهٔ تست)", "pub": False},
    {"id": "qa-partner-private", "n": "نهاد خصوصی (دادهٔ تست)", "privacy": "private"},
    {"id": "qa-partner-paused", "n": "نهاد متوقف (دادهٔ تست)", "status": "paused"},
    {"id": "qa-partner-pending", "n": "نهاد منتظر (دادهٔ تست)", "pend": True},
]
for ev in content["events"]:
    if ev["id"] in ("qa-ev-1", "qa-ev-past"):
        ev["partnerId"] = "qa-partner-1"
        ev["partnerName"] = "نام قدیمی (نباید دیده شود)"
st, body = call("PATCH", "/api/owner/site-content", {"content": {"partners": content["partners"], "events": content["events"]}, "expected_version": version})
print("PATCH", st, "version", body.get("version") if isinstance(body, dict) else body)
import urllib.request
pub = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/public/site-content"))["content"]
print("public partner ids:", [p["id"] for p in pub["partners"]])
print("events with partnerId:", [(e["id"], e.get("partnerId"), e.get("partnerName")) for e in pub["events"]])
print("qa-partner-1 links:", next(p for p in pub["partners"] if p["id"]=="qa-partner-1")["links"])
