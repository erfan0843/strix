"""Tiny owner-API client for the isolated preview env (test data only)."""
import json, http.cookiejar, urllib.request, urllib.error, uuid, pathlib
ORIGIN = "http://127.0.0.1:8000"
STATE = pathlib.Path("/tmp/nora-preview")
jar = http.cookiejar.MozillaCookieJar(str(STATE / "owner-cookies.txt"))
try:
    jar.load(ignore_discard=True, ignore_expires=True)
except FileNotFoundError:
    pass
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def csrf():
    for c in jar:
        if c.name == "nora_csrf":
            return c.value
    return ""

def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(ORIGIN + path, data=data, method=method)
    req.add_header("Origin", ORIGIN)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        req.add_header("X-CSRF-Token", csrf())
    if method == "POST":
        req.add_header("Idempotency-Key", str(uuid.uuid4()))
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with opener.open(req, timeout=30) as r:
            raw = r.read()
            jar.save(ignore_discard=True, ignore_expires=True)
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()[:400]
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")

def login():
    pw = (STATE / "owner-pw.txt").read_text().strip()
    st, body = call("POST", "/api/auth/login", {"username": "preview-owner", "password": pw})
    assert st == 200, (st, body)
    return body

if __name__ == "__main__":
    print(login())
    print(call("GET", "/api/auth/me"))
