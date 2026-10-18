"""Seed the isolated test server with labelled test data via the owner API (no direct DB writes)."""
import json, secrets, sys, urllib.request, http.cookiejar

BASE = "http://127.0.0.1:8000"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Origin", BASE)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    csrf = next((c.value for c in jar if c.name == "nora_csrf"), "")
    if csrf:
        req.add_header("X-CSRF-Token", csrf)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with opener.open(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw[:200])
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw[:200])


pw = open("/tmp/nora-preview/owner-pw.txt").read().strip()
st, body = call("POST", "/api/auth/login", {"username": "preview-owner", "password": pw})
assert st == 200, (st, body)

st, current = call("GET", "/api/owner/site-content")
assert st == 200, (st, current)
version = current.get("version", 0)

G = "linear-gradient(135deg,#1E6FD0,#0A3A82)"
XSS = "<img src=x onerror=alert(1)>"
content = {
    "events": [
        {"id": "qa-ev-1", "t": "کارگاه آزمایشی ۱ (دادهٔ تست)", "kind": "کارگاه", "on": "1405/09/19", "time": "۱۶:۳۰ تا ۱۹:۰۰",
         "place": "تهران", "mode": "حضوری", "g": G, "pub": True, "status": "published", "d": "توضیح آزمایشی رویداد یک.", "regForm": "<published-form-id>"},
        {"id": "qa-ev-2", "t": "نشست آزمایشی ۲ (دادهٔ تست)", "kind": "نشست", "on": "1405/09/29", "time": "۱۸:۰۰",
         "place": "آنلاین", "mode": "آنلاین", "g": G, "pub": True, "status": "published", "d": "توضیح آزمایشی رویداد دو."},
        {"id": "qa-ev-past", "t": "رویداد برگزارشدهٔ آزمایشی (دادهٔ تست)", "kind": "نشست", "on": "1403/12/11",
         "place": "تهران", "mode": "حضوری", "g": G, "pub": True, "status": "published", "d": "برگزار شده.", "past": True},
        {"id": "qa-ev-xss", "t": "رویداد XSS " + XSS, "kind": "کارگاه", "on": "1405/10/04", "place": XSS, "mode": "حضوری",
         "g": G, "pub": True, "status": "published", "d": "<script>alert(2)</script> متن"},
        {"id": "qa-np-hidden", "t": "رویداد پنهان (نباید دیده شود)", "kind": "کارگاه", "on": "1405/10/05", "g": G, "pub": True, "status": "published", "hidden": True},
    ],
    "people": [
        {"id": "qa-p1", "n": "استاد آزمایشی (دادهٔ تست)", "r": "مدرس", "bio": "زندگی‌نامهٔ آزمایشی.", "g": G, "pub": True},
        {"id": "qa-p-xss", "n": "فرد XSS " + XSS, "r": "<b>نقش</b>", "bio": "<script>alert(3)</script>", "g": G, "pub": True},
    ],
    "articles": [
        {"id": "np-qa-1", "t": "مطلب آزمایشی ۱ (دادهٔ تست)", "cat": "یادداشت", "tags": ["یادداشت"], "lead": "این مطلب فقط برای آزمون محیط ایزوله ساخته شده است.",
         "who": "تحریریهٔ نورا", "g": G, "pub": True, "min": 2, "views": 0, "at": "2026-06-01T12:00:00Z",
         "blocks": [{"ty": "p", "x": "متن آزمایشی مطلب یک."}]},
        {"id": "np-qa-2", "t": "مطلب آزمایشی ۲ (دادهٔ تست)", "cat": "گزارش", "tags": ["گزارش"], "lead": "مقدمهٔ دوم.",
         "who": "تحریریهٔ نورا", "g": G, "pub": True, "min": 3, "views": 0, "at": "2026-06-02T12:00:00Z",
         "blocks": [{"ty": "p", "x": "متن آزمایشی مطلب دو."}]},
        {"id": "np-qa-xss", "t": "مطلب XSS " + XSS, "cat": "گزارش", "tags": ["گزارش"], "lead": "<script>alert(4)</script>",
         "who": XSS, "g": G, "pub": True, "min": 1, "views": 0, "at": "2026-06-03T12:00:00Z",
         "blocks": [{"ty": "p", "x": "<iframe src=javascript:alert(5)></iframe> متن"}, {"ty": "h", "x": XSS, "lv": 2}]},
    ],
    "partners": [
        {"id": "qa-partner-1", "n": "نهاد همکار آزمایشی (دادهٔ تست)", "type": "مؤسسه", "d": "شرح آزمایشی.", "logo": "/icon-192.png",
         "href": "https://example.org/partner-test", "g": G, "mon": "ن", "pub": True,
         "links": [{"k": "email", "v": "mailto:hello@example.org"}, {"k": "tel", "v": "tel:+33123456789"}, {"k": "telegram", "v": "https://t.me/nora_test_channel"}]},
        {"id": "qa partner/2 ü", "n": "نهاد با شناسهٔ عجیب (دادهٔ تست)", "type": "انجمن", "d": "", "g": G, "mon": "ع", "pub": True},
        {"id": "qa-partner-broken-logo", "n": "نهاد با لوگوی شکسته (دادهٔ تست)", "type": "انجمن", "d": "لوگو موجود نیست.", "logo": "/uploads/does-not-exist-qa.webp", "g": G, "mon": "ش", "pub": True},
        {"id": "qa-partner-xss", "n": "نهاد XSS " + XSS, "type": "<b>x</b>", "d": "<script>alert(6)</script>", "g": G, "mon": "x", "pub": True},
        {"id": "qa-np-private", "n": "نهاد خصوصی (نباید دیده شود)", "type": "مؤسسه", "g": G, "mon": "خ", "pub": True, "privacy": "private"},
    ],
}
st, res = call("PATCH", "/api/owner/site-content", {"content": content, "expected_version": version},
               {"Idempotency-Key": "seed-" + secrets.token_hex(12)})
print("site-content PATCH", st, res if st != 200 else {"version": res.get("version")})
assert st == 200

form = {
    "name": "QA فرم ثبت‌نام رایگان (دادهٔ تست)", "model": "registration", "need": "reg", "slug": "qa/free-registration-2",
    "ev": "qa-ev-1", "settings": {"description": "فرم آزمایشی محیط ایزوله", "confirmation": "ثبت شد"},
    "fields": [
        {"id": "full-name", "t": "text", "l": "نام و نام خانوادگی", "required": True},
        {"id": "mobile", "t": "text", "l": "شمارهٔ همراه", "required": True},
    ],
}
st, created = call("POST", "/api/forms", form, {"Idempotency-Key": "seed-form-" + secrets.token_hex(10)})
print("create form", st, created if st != 201 else created["id"])
assert st == 201
fid = created["id"]
st, pub = call("POST", f"/api/forms/{fid}/publish", {"expected_version": created.get("version", 1)})
print("publish", st, pub if st != 200 else pub.get("status"))
assert st == 200
open("/tmp/nora-preview/form-id.txt", "w").write(fid)
print("FORM_ID", fid)
