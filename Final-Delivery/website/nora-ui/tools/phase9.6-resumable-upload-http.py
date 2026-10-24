"""Phase 9.6 §4.1 — resumable upload contract over real HTTP against a running TEST/staging server.

Exercises, with a file larger than the inline limit (default 24 MiB; `--mib` to change):
  storage health · session open · chunk + checksum · wrong offset (409) · wrong checksum (400) ·
  interruption (short chunk) + resume from the server-reported offset · single finalize (second → 410) ·
  size + SHA-256 of the stored bytes equal the source · temp (.incoming) cleanup · oversize session (413) ·
  abort cleanup · no physical name/path/internal key in download headers · private dir not under the web root.

Usage (nothing from the env is printed):
  NORA_QA_ORIGIN=http://127.0.0.1:8000 NORA_QA_CREDENTIALS=<gitignored creds file> \
  [NORA_QA_PRIVATE_DIR=<same dir as the server's NORA_PRIVATE_STORAGE_DIR, for local temp-file checks>] \
  python tools/phase9.6-resumable-upload-http.py <event id> <output dir> [--mib 24]
Exit 0 when every check passed, 1 otherwise. Refuses to start when free disk < 3 × file size.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote

import httpx

ORIGIN = os.environ.get("NORA_QA_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
CREDS = Path(os.environ.get("NORA_QA_CREDENTIALS", "PREVIEW-LOGIN.local.md"))
PRIVATE_DIR = os.environ.get("NORA_QA_PRIVATE_DIR", "")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
EVENT = args[0] if args else ""
OUT = Path(args[1] if len(args) > 1 else "phase9.6-upload")
MIB = int(sys.argv[sys.argv.index("--mib") + 1]) if "--mib" in sys.argv else 24
OUT.mkdir(parents=True, exist_ok=True)
LOG: list[str] = []
FAILED = 0
MP4_HEAD = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


def say(line: str) -> None:
    LOG.append(line)
    (OUT / "resumable-upload-http.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")


def check(name: str, cond: bool, note: str, dbg=None) -> bool:
    global FAILED
    if not cond:
        FAILED += 1
    say(f"{'✓' if cond else '✗'} {name}: {note}" + ("" if cond or dbg is None else " | " + json.dumps(dbg, ensure_ascii=False, default=str)[:500]))
    return cond


def code(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:  # noqa: BLE001
        return ""
    return str(detail.get("code") or "") if isinstance(detail, dict) else str(detail or "")


class Client:
    def __init__(self):
        self.http = httpx.Client(base_url=ORIGIN, timeout=120.0)
        self.jar: dict[str, str] = {}

    def req(self, method: str, path: str, *, write: bool = True, headers: dict | None = None, **kw) -> httpx.Response:
        h = dict(headers or {})
        if self.jar:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.jar.items())
        if write:
            h.setdefault("Origin", ORIGIN)
            h.setdefault("X-CSRF-Token", self.jar.get("nora_csrf", ""))
        response = self.http.request(method, path, headers=h, **kw)
        for raw in response.headers.get_list("set-cookie"):
            cookie = SimpleCookie()
            cookie.load(raw)
            for key, morsel in cookie.items():
                self.jar[key] = morsel.value
        return response


def main() -> int:
    if not EVENT:
        raise SystemExit("event id required")
    text = CREDS.read_text(encoding="utf-8")
    match = re.search(r"مالک: `([^`]+)` / `([^`]+)`", text)
    if not match:
        raise SystemExit("credentials file not parsed")
    owner = Client()
    login = owner.req("POST", "/api/auth/staff-login", json={"username": match.group(1), "password": match.group(2)})
    if login.status_code != 200:
        raise SystemExit(f"owner login failed: {login.status_code}")
    say(f"# فاز ۹.۶ §۴.۱ — آپلود ازسرگیرنده روی {ORIGIN} (رویداد {EVENT}، فایل {MIB} MiB)")

    health = owner.req("GET", "/api/admin/storage/health", write=False)
    hb = health.json() if health.status_code == 200 else {}
    say(f"• سلامت ذخیره‌سازی: {health.status_code} state={hb.get('state')} backend={hb.get('backend')} free={hb.get('free_bytes')} max={hb.get('max_bytes') or hb.get('max_mib')}")
    if hb.get("state") not in {"ok", "warning"}:
        check("پیش‌نیاز: ذخیره‌سازی خصوصی پیکربندی‌شده", False, f"state={hb.get('state')} — آزمون ازسرگیری بدون دایرکتوری خصوصی معنا ندارد", hb)
        return 1
    size = MIB * 1024 * 1024
    free = shutil.disk_usage(PRIVATE_DIR or "/").free
    say(f"• دیسک آزاد (df محلی): {free // (1024 * 1024)} MiB؛ نیاز حداقل ۳× فایل = {3 * MIB} MiB")
    if free < 3 * size:
        check("پیش‌نیاز: فضای کافی", False, "فضای آزاد کمتر از ۳ برابر فایل؛ آزمون سنگین اجرا نشد")
        return 1

    resource = owner.req("POST", f"/api/admin/events/{EVENT}/resources", json={"title": f"ویدیوی بزرگ آزمون ۹.۶ ({MIB} MiB)", "access": "purchased", "delivery": "view"})
    check("منبع پیش‌نویس ساخته شد", resource.status_code == 201, f"→ {resource.status_code}", resource.text[:200])
    rid = resource.json()["id"]
    base = f"/api/admin/events/{EVENT}/resources/{rid}/upload-sessions"

    # deterministic pseudo-random payload (no need to keep it all in RAM twice)
    rng = hashlib.sha256(b"nora-qa-9.6").digest()
    body = bytearray(MP4_HEAD)
    while len(body) < size:
        rng = hashlib.sha256(rng).digest()
        body.extend(rng * 1024)
    data = bytes(body[:size])
    digest = hashlib.sha256(data).hexdigest()
    say(f"• sha256(منبع) = {digest[:16]}… size={size}")

    opened = owner.req("POST", base, json={"size": size, "sha256": digest, "file_name": "جلسهٔ بزرگ.mp4"})
    s = opened.json() if opened.status_code == 201 else {}
    chunk = int(s.get("chunk_bytes") or 4 * 1024 * 1024)
    sid = s.get("id", "")
    check("گشودن نشست: 201، offset=0، اندازهٔ تکه از سرور", opened.status_code == 201 and s.get("offset") == 0 and chunk > 0, f"→ {opened.status_code} chunk={chunk} expires_at={s.get('expires_at')}", opened.text[:200])
    for key in ("storage_key", "path", "temp_path"):
        check(f"پاسخ نشست کلید داخلی «{key}» را افشا نمی‌کند", key not in s, "")

    def push(offset: int, part: bytes, *, checksum: str | None = None) -> httpx.Response:
        h = {"Upload-Offset": str(offset), "Content-Type": "application/octet-stream",
             "Upload-Checksum": "sha256 " + (checksum or hashlib.sha256(part).hexdigest())}
        return owner.req("PATCH", f"{base}/{sid}", content=part, headers=h)

    t0 = time.monotonic()
    first = push(0, data[:chunk])
    check("تکهٔ ۱ با checksum: 200، offset = chunk", first.status_code == 200 and first.json().get("offset") == chunk, f"→ {first.status_code} offset={first.json().get('offset') if first.status_code == 200 else None}")
    stale = push(0, data[:chunk])
    check("تکرار تکهٔ ۱ (offset کهنه): 409 offset_mismatch با offset درست", stale.status_code == 409 and code(stale) == "offset_mismatch" and stale.json()["detail"].get("offset") == chunk, f"→ {stale.status_code} {code(stale)}")
    bad = push(chunk, data[chunk:2 * chunk], checksum="0" * 64)
    state = owner.req("GET", f"{base}/{sid}", write=False).json()
    check("checksum غلط: 400 chunk_checksum_mismatch و هیچ بایتی نگه داشته نشد", bad.status_code == 400 and code(bad) == "chunk_checksum_mismatch" and state.get("offset") == chunk, f"→ {bad.status_code} {code(bad)} offset={state.get('offset')}")
    # interruption: only part of chunk 2 arrives (short chunk), then the client "dies" and resumes from GET offset
    short = chunk // 3
    interrupted = push(chunk, data[chunk:chunk + short])
    resumed = owner.req("GET", f"{base}/{sid}", write=False).json()
    check("قطع: تکهٔ کوتاه پذیرفته شد و GET نشست offset واقعی را می‌دهد", interrupted.status_code == 200 and resumed.get("offset") == chunk + short and resumed.get("status") == "open",
          f"→ {interrupted.status_code} offset={resumed.get('offset')} status={resumed.get('status')}")
    early = owner.req("POST", f"{base}/{sid}/complete", json={})
    check("تکمیل زودهنگام: 409 upload_incomplete", early.status_code == 409 and code(early) == "upload_incomplete", f"→ {early.status_code} {code(early)}")
    offset = int(resumed.get("offset") or 0)
    pushes = 2
    while offset < size:
        part = data[offset:offset + chunk]
        r = push(offset, part)
        pushes += 1
        if r.status_code != 200:
            check("ازسرگیری تا پایان", False, f"PATCH @{offset} → {r.status_code} {code(r)}")
            return 1
        offset = int(r.json()["offset"])
    elapsed = time.monotonic() - t0
    check("ازسرگیری از offset سرور تا پایان", offset == size, f"{pushes} PATCH، {elapsed:.1f}s، {size / elapsed / 1024 / 1024:.1f} MiB/s")
    extra = push(size, b"x")
    check("پس از کامل شدن، بایت اضافه 413", extra.status_code == 413, f"→ {extra.status_code} {code(extra)}")
    conflict = owner.req("POST", f"{base}/{sid}/complete", json={"sha256": "f" * 64})
    check("تکمیل با sha256 متفاوت از اعلام اولیه: 422 sha256_conflict", conflict.status_code == 422 and code(conflict) == "sha256_conflict", f"→ {conflict.status_code} {code(conflict)}")
    done = owner.req("POST", f"{base}/{sid}/complete", json={"sha256": digest})
    saved = done.json() if done.status_code == 200 else {}
    check("تکمیل: 200، اندازه = منبع، content_type ویدیو، storage ready", done.status_code == 200 and saved.get("size") == size and saved.get("content_type") == "video/mp4"
          and (saved.get("storage") or {}).get("state") == "ready", f"→ {done.status_code} size={saved.get('size')} storage={saved.get('storage')}", done.text[:200])
    twice = owner.req("POST", f"{base}/{sid}/complete", json={})
    check("تکمیل دوباره: 410 upload_session_completed (یک‌باره)", twice.status_code == 410 and code(twice) == "upload_session_completed", f"→ {twice.status_code} {code(twice)}")
    leak_keys = [k for k in saved if k in {"storage_key", "path", "file_path"}]
    check("پاسخ تکمیل کلید/مسیر فیزیکی ندارد", not leak_keys, f"keys={sorted(saved)[:12]}", leak_keys)

    # bytes back: staff download (owner), compare hash and size; inspect headers for leaks
    download = f"/api/public/events/{EVENT}/resources/{rid}/download"
    served = owner.req("GET", download, write=False)
    got = hashlib.sha256(served.content).hexdigest() if served.status_code == 200 else ""
    check("بایت‌های ذخیره‌شده: sha256 و اندازه با منبع برابر", served.status_code == 200 and got == digest and len(served.content) == size, f"→ {served.status_code} sha256={got[:16]}… len={len(served.content)}")
    head_leak = [f"{k}: {v}" for k, v in served.headers.items() if any(t in v for t in ("/home/", "/var/", "/srv/", ".incoming", "private-store")) or k.lower() in {"x-storage-key", "x-file-path"}]
    check("سرآیندهای دانلود بدون مسیر/نام فیزیکی/کلید داخلی", not head_leak, f"content-disposition={served.headers.get('content-disposition')}", head_leak)
    rng_ = owner.req("GET", download, write=False, headers={"Range": f"bytes={size - 16}-"})
    check("Range روی فایل بزرگ: 206 و ۱۶ بایت پایانی درست", rng_.status_code == 206 and rng_.content == data[-16:], f"→ {rng_.status_code} content-range={rng_.headers.get('content-range')}")
    guest = Client()
    g_draft = guest.req("GET", download, write=False)
    check("مهمان روی منبع پیش‌نویس: 404 (وجود منبع افشا نمی‌شود)", g_draft.status_code == 404 and len(g_draft.content) < 512, f"→ {g_draft.status_code} body={len(g_draft.content)}B")
    published = owner.req("PUT", f"/api/admin/events/{EVENT}/resources/{rid}", json={"status": "published"})
    g = guest.req("GET", download, write=False)
    check("مهمان روی منبع منتشرشدهٔ خریداری‌شده: 401 و هیچ بایتی", published.status_code == 200 and g.status_code == 401 and len(g.content) < 512, f"publish {published.status_code} · guest → {g.status_code} body={len(g.content)}B")

    # oversize session, abort cleanup
    cap = int(hb.get("max_bytes") or (int(hb.get("max_mib") or 512) * 1024 * 1024))
    over = owner.req("POST", base, json={"size": cap + 1, "file_name": "x.mp4"})
    check("نشست بزرگ‌تر از سقف: 413", over.status_code == 413, f"→ {over.status_code} max_bytes={(over.json().get('detail') or {}).get('max_bytes') if over.status_code == 413 else None}")
    second = owner.req("POST", base, json={"size": 3 * chunk, "file_name": "abort.mp4"})
    sid2 = second.json().get("id", "") if second.status_code == 201 else ""
    owner.req("PATCH", f"{base}/{sid2}", content=data[:chunk], headers={"Upload-Offset": "0", "Content-Type": "application/octet-stream", "Upload-Checksum": "sha256 " + hashlib.sha256(data[:chunk]).hexdigest()})
    aborted = owner.req("DELETE", f"{base}/{sid2}")
    check("لغو نشست نیمه‌کاره: status=aborted", aborted.status_code == 200 and aborted.json().get("status") == "aborted", f"→ {aborted.status_code} {aborted.text[:80]}")

    if PRIVATE_DIR:
        incoming = Path(PRIVATE_DIR) / ".incoming"
        parts = sorted(p.name for p in incoming.iterdir()) if incoming.is_dir() else []
        check("پاک‌سازی temp: .incoming خالی پس از تکمیل و لغو", parts == [], f"files={parts}")
        webroot = Path(__file__).resolve().parents[1]
        check("دایرکتوری خصوصی زیر ریشهٔ وب نیست", not Path(PRIVATE_DIR).resolve().is_relative_to(webroot), f"private ∉ {webroot.name}/")
        stored = [p for p in Path(PRIVATE_DIR).rglob("*") if p.is_file() and p.stat().st_size == size]
        check("فایل روی دیسک با اندازهٔ منبع و sha256 برابر", len(stored) >= 1 and any(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p in stored), f"matches={len(stored)}")
    else:
        say("• بررسی محلی temp/مسیر انجام نشد (NORA_QA_PRIVATE_DIR تنظیم نیست) — روی staging با دسترسی به دیسک اجرا شود.")
    # the private store must not be reachable as a static path through the web server
    for probe in ("/private/", "/.incoming/", "/private-store/"):
        r = guest.req("GET", probe, write=False)
        check(f"مسیر ایستای {probe} از وب قابل دسترسی نیست", r.status_code in {401, 403, 404}, f"→ {r.status_code}")
    say(f"\nresource={rid} session={sid}")
    say(f"نتیجه: {len([l for l in LOG if l.startswith('✓')])} ✓ · {FAILED} ✗")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
