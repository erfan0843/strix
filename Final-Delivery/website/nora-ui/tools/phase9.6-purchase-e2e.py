"""Phase 9.6 §3 — real HTTP purchase→access scenario against a running TEST server (synthetic data only).

Builds a fresh held event + paid product + purchase form through the admin API, then walks the whole
contract over plain HTTP (no TestClient, no in-process shortcuts): guest → form, unpublished form,
card-to-card pending vs approved, rejected, duplicates, IDOR, new session without re-purchase,
sale stop keeps entitlement, revoke closes access, free claim without a fake transaction, wallet
fail-closed, external-exposure acknowledgement, read-only audit API and its permission gate.

Usage (test server + test DB only; nothing from the env is printed):
  NORA_QA_ORIGIN=http://127.0.0.1:8000 NORA_QA_BALE_BOT_TOKEN=<test-only token> \
  NORA_QA_CREDENTIALS=<path to gitignored PREVIEW-LOGIN.local.md> \
  python tools/phase9.6-purchase-e2e.py <output dir>
Exit 0 when every check passed, 1 otherwise. The event it creates is titled «[QA ۹.۶] …».
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

ORIGIN = os.environ.get("NORA_QA_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
BOT_TOKEN = os.environ.get("NORA_QA_BALE_BOT_TOKEN", "")
CREDS = Path(os.environ.get("NORA_QA_CREDENTIALS", "PREVIEW-LOGIN.local.md"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "phase9.6-e2e")
OUT.mkdir(parents=True, exist_ok=True)
RUN = secrets.token_hex(3)
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CARD = {"number": "6037997599999993", "bank": "بانک آزمایشی", "holder": "نورا"}
LOG: list[str] = []
FAILED = 0


def say(line: str) -> None:
    LOG.append(line)
    (OUT / "purchase-e2e.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")


def check(name: str, cond: bool, note: str, dbg=None) -> bool:
    global FAILED
    if not cond:
        FAILED += 1
    say(f"{'✓' if cond else '✗'} {name}: {note}" + ("" if cond or dbg is None else " | " + json.dumps(dbg, ensure_ascii=False)[:600]))
    return cond


def note(name: str, text: str) -> None:
    say(f"• {name}: {text}")


class Client:
    """httpx client with a hand-rolled cookie jar (httpx drops `Secure` cookies over plain http)."""

    def __init__(self, label: str):
        self.label = label
        self.http = httpx.Client(base_url=ORIGIN, timeout=60.0, follow_redirects=False)
        self.jar: dict[str, str] = {}

    def _store(self, response: httpx.Response) -> None:
        for raw in response.headers.get_list("set-cookie"):
            cookie = SimpleCookie()
            cookie.load(raw)
            for key, morsel in cookie.items():
                if morsel["max-age"] == "0" or morsel.value == "":
                    self.jar.pop(key, None)
                else:
                    self.jar[key] = morsel.value

    def req(self, method: str, path: str, *, write: bool = False, csrf: str = "", headers: dict | None = None, **kw) -> httpx.Response:
        h = dict(headers or {})
        if self.jar:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.jar.items())
        if write:
            h.setdefault("Origin", ORIGIN)
            token = self.jar.get(csrf or "nora_account_csrf") or self.jar.get("nora_csrf", "")
            if token:
                h.setdefault("X-CSRF-Token", token)
        response = self.http.request(method, path, headers=h, **kw)
        self._store(response)
        return response

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, **kw):
        return self.req("POST", path, write=True, **kw)

    def put(self, path, **kw):
        return self.req("PUT", path, write=True, **kw)


def detail_code(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(detail, dict):
        return str(detail.get("code") or detail.get("reason") or "")
    return str(detail or "")


_LOGINS: dict[int, int] = {}


def detail_reason(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:  # noqa: BLE001
        return ""
    return str(detail.get("reason") or detail.get("code") or "") if isinstance(detail, dict) else str(detail or "")


def mine(client: Client, path: str, recording_id: str) -> list[dict]:
    """Rows of one account that belong to the synthetic product (accounts may carry rows from other QA runs)."""
    body = client.get(path).json()
    rows = body.get("items", []) if isinstance(body, dict) else body
    return [row for row in rows if isinstance(row, dict) and row.get("recording_id") == recording_id]


def init_data(user_id: int) -> str:
    _LOGINS[user_id] = _LOGINS.get(user_id, 0) + 1  # replay protection: each session gets its own query_id
    fields = {"auth_date": str(int(time.time())), "query_id": f"qa96-{user_id}-{RUN}-{_LOGINS[user_id]}",
              "user": json.dumps({"id": user_id, "first_name": "آزمایش"}, ensure_ascii=False)}
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def member(user_id: int) -> tuple[Client, str]:
    client = Client(f"member-{user_id}")
    response = client.post("/api/auth/bale-mini-app", json={"init_data": init_data(user_id)}, csrf="")
    if response.status_code != 200:
        raise SystemExit(f"member login failed for {user_id}: {response.status_code} {response.text[:200]}")
    return client, response.json()["account_id"]


def staff(kind: str) -> Client:
    text = CREDS.read_text(encoding="utf-8")
    match = re.search(("مالک" if kind == "owner" else "مدیر") + r": `([^`]+)` / `([^`]+)`", text)
    if not match:
        raise SystemExit("credentials file not parsed")
    client = Client(kind)
    response = client.post("/api/auth/staff-login", json={"username": match.group(1), "password": match.group(2)}, csrf="nora_csrf")
    if response.status_code != 200:
        raise SystemExit(f"{kind} login failed: {response.status_code}")
    return client


def iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    if not BOT_TOKEN:
        raise SystemExit("NORA_QA_BALE_BOT_TOKEN (test-only) is required")
    say(f"# فاز ۹.۶ §۳ — سناریوی HTTP خرید→دسترسی روی {ORIGIN} (دادهٔ مصنوعی، اجرای {RUN})")
    owner = staff("owner")
    manager = staff("manager")
    guest = Client("guest")

    # ── S0: synthetic held event + paid product; without a published purchase form it cannot be published ──
    def create_event() -> httpx.Response:
        version = 0
        for _attempt in range(3):
            response = owner.post("/api/admin/content/events", json={"record": {
                "t": f"[QA ۹.۶] کارگاه برگزارشده {RUN}", "kind": "کارگاه", "d": "رویداد مصنوعی برای آزمون خرید→دسترسی فاز ۹.۶.",
                "on": "۱۴۰۵/۰۷/۰۱", "time": "۱۰ تا ۱۳", "place": "سالن آزمایشی", "mode": "حضوری",
                "startsAt": iso(timedelta(days=-9)), "endsAt": iso(timedelta(days=-8)), "regClosesAt": iso(timedelta(days=-10)), "past": True},
                "expected_version": version, "status": "published"}, csrf="nora_csrf")
            if response.status_code != 409 or detail_code(response) != "site_content_version_conflict":
                return response
            version = int(response.json()["detail"].get("current_version") or 0)
        return response

    created = create_event()
    if created.status_code != 200:
        check("S0 رویداد برگزارشدهٔ مصنوعی", False, f"POST /api/admin/content/events → {created.status_code}", created.text[:300])
        return 1
    check("S0 رویداد برگزارشدهٔ مصنوعی", True, f"POST /api/admin/content/events → 200")
    event_id = created.json()["record"]["id"]
    base = f"/api/admin/events/{event_id}/recording"
    product = owner.put(base, json={"title": "نسخهٔ ضبط‌شدهٔ کارگاه QA", "summary": "ویدیو و جزوه", "price": 1_250_000, "payment_card": CARD,
                                    "access_terms": "دسترسی نامحدود", "refund_policy": "تا ۴۸ ساعت"}, csrf="nora_csrf")
    check("S0 محصول پولی (پیش‌نویس)", product.status_code == 200 and product.json()["status"] == "draft", f"PUT recording → {product.status_code}", product.text[:300])
    recording_id = product.json()["id"]
    session = owner.post(f"{base}/sessions", json={"title": "جلسهٔ اول", "duration_minutes": 50}, csrf="nora_csrf")
    session_id = session.json()["id"]
    resource = owner.post(f"/api/admin/events/{event_id}/resources", json={"title": "ویدیوی جلسهٔ اول", "access": "purchased", "session_id": session_id, "delivery": "view"}, csrf="nora_csrf")
    resource_id = resource.json()["id"]
    uploaded = owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}/file", content=MP4, csrf="nora_csrf", headers={"X-File-Name": quote("جلسه ۱.mp4")})
    check("S0 جلسه + منبع خریداری‌شده + فایل", session.status_code == 201 and resource.status_code == 201 and uploaded.status_code == 200,
          f"sessions {session.status_code} · resources {resource.status_code} · file {uploaded.status_code}")
    owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}", json={"status": "published"}, csrf="nora_csrf")
    owner.put(f"{base}/sessions/{session_id}", json={"status": "published"}, csrf="nora_csrf")
    ready = owner.post(f"{base}/status", json={"status": "ready"}, csrf="nora_csrf")
    blocked = owner.post(f"{base}/status", json={"status": "published"}, csrf="nora_csrf")
    check("S0 محصول پولی بدون فرم خرید منتشر نمی‌شود", ready.status_code == 200 and blocked.status_code == 409
          and "purchase_form_required" in (blocked.json().get("detail") or {}).get("blockers", []),
          f"ready {ready.status_code} · publish → {blocked.status_code} {detail_code(blocked)} blockers={(blocked.json().get('detail') or {}).get('blockers')}")
    download = f"/api/public/events/{event_id}/resources/{resource_id}/download"

    def new_form(price: int, methods: tuple[str, ...], *, publish: bool, key: str, settings_extra: dict | None = None) -> httpx.Response:
        settings: dict = {"enabledPaymentMethods": list(methods)}
        if price > 0:
            settings["fin"] = [{"l": "دسترسی به نسخهٔ ضبط‌شده", "p": price, "off": 0, "req": True, "d": ""}]
        if "card_transfer" in methods:
            settings.update({"receiptReviewRequired": True, "paymentCard": dict(CARD), "paymentInstructions": "مبلغ را واریز و رسید را بارگذاری کنید."})
        settings.update(settings_extra or {})
        response = owner.post("/api/forms", json={"name": f"خرید نسخهٔ ضبط‌شده {key}", "model": "registration", "need": "reg", "purpose": "recording_access",
                                                  "recording_id": recording_id, "settings": settings,
                                                  "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}]},
                              csrf="nora_csrf", headers={"Idempotency-Key": f"qa96-{RUN}-{key}"})
        if publish and response.status_code == 201:
            published = owner.post(f"/api/forms/{response.json()['id']}/publish", json={"expected_version": 1}, csrf="nora_csrf")
            response.headers["x-qa-publish"] = str(published.status_code) + " " + detail_code(published)
        return response

    draft_form = new_form(1_250_000, ("card_transfer",), publish=False, key="draft")
    draft_form_id = draft_form.json()["id"]
    still_blocked = owner.post(f"{base}/status", json={"status": "published"}, csrf="nora_csrf")
    check("S0 فرم خرید پیش‌نویس کافی نیست", still_blocked.status_code == 409 and "purchase_form_not_published" in (still_blocked.json().get("detail") or {}).get("blockers", []),
          f"publish with draft form → {still_blocked.status_code} blockers={(still_blocked.json().get('detail') or {}).get('blockers')}")
    wallet_form = new_form(1_250_000, ("bale_wallet",), publish=True, key="wallet")
    check("S0 روش کیف پول بله بدون پیکربندی امن منتشر نمی‌شود (fail-closed)", wallet_form.status_code == 201 and wallet_form.headers.get("x-qa-publish", "").split(" ")[0] in {"409", "422"},
          f"create {wallet_form.status_code} · publish → {wallet_form.headers.get('x-qa-publish')}")
    webhook = guest.post("/api/payments/bale/webhook/not-a-real-token", json={"pre_checkout_query": {"id": "x"}})
    check("S0 وب‌هوک بله بدون پیکربندی: 503 (هیچ تأییدی ممکن نیست)", webhook.status_code == 503 and detail_code(webhook) == "bale_payment_not_configured", f"→ {webhook.status_code} {detail_code(webhook)}")
    published_form = owner.post(f"/api/forms/{draft_form_id}/publish", json={"expected_version": 1}, csrf="nora_csrf")
    form_id = draft_form_id
    publish = owner.post(f"{base}/status", json={"status": "published"}, csrf="nora_csrf")
    admin_view = owner.get(base).json()["recording"]
    check("S0 انتشار پس از انتشار فرم؛ قیمت/روش فقط از فرم", published_form.status_code == 200 and publish.status_code == 200
          and admin_view["commerce"].get("form_id") == form_id and admin_view["commerce"].get("source") == "form",
          f"form publish {published_form.status_code} · product publish {publish.status_code} · commerce={json.dumps(admin_view.get('commerce'), ensure_ascii=False)[:160]}")
    locked = owner.put(base, json={"price": 999}, csrf="nora_csrf")
    check("S0 قیمت دوم روی محصول پذیرفته نمی‌شود", locked.status_code == 409 and detail_code(locked) == "commercial_settings_in_form", f"PUT price → {locked.status_code} {detail_code(locked)}")
    second_form = new_form(1_250_000, ("card_transfer",), publish=True, key="second")
    check("S0 فرم خرید منتشرشدهٔ دوم برای همان محصول رد می‌شود", second_form.headers.get("x-qa-publish", "").startswith("409"), f"publish → {second_form.headers.get('x-qa-publish')}")
    unpublished_form_id = second_form.json()["id"]

    # ── S1: guest ──
    public = guest.get(f"/api/public/events/{event_id}/recording")
    view = public.json().get("recording") or {}
    check("S1 مهمان: محصول را می‌بیند، CTA ورود، فرم خرید همان فرم منتشرشده", public.status_code == 200 and view.get("viewer", {}).get("cta", {}).get("kind") == "login"
          and view.get("purchase", {}).get("form_id") == form_id and view["purchase"].get("source") == "form" and "payment_card" not in view,
          f"→ {public.status_code} cta={view.get('viewer', {}).get('cta', {}).get('kind')} purchase={json.dumps(view.get('purchase'), ensure_ascii=False)}")
    g_dl = guest.get(download)
    g_form = guest.get(f"/api/public/forms/{form_id}/draft")
    g_submit = guest.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "مهمان"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    check("S1 مهمان: دانلود 401، فرم قابل مشاهده، ارسال بدون حساب 401", g_dl.status_code == 401 and g_form.status_code == 200 and g_submit.status_code == 401 and detail_code(g_submit) == "account_required",
          f"download {g_dl.status_code} · form {g_form.status_code} · submit {g_submit.status_code} {detail_code(g_submit)}")
    unpub = guest.get(f"/api/public/forms/{unpublished_form_id}/draft")
    unpub_submit = guest.post(f"/api/public/forms/{unpublished_form_id}/responses", json={"answers": {"full-name": "x"}})
    check("S1 فرم منتشرنشده قابل خرید نیست", unpub.status_code in {404, 409, 410} and unpub_submit.status_code in {401, 404, 409, 410},
          f"draft {unpub.status_code} · submit {unpub_submit.status_code} {detail_code(unpub_submit)}")

    # ── S2: buyer, card-to-card, pending ──
    buyer, buyer_account = member(95001)
    v = buyer.get(f"/api/public/events/{event_id}/recording").json()["recording"]
    claim = buyer.post(f"/api/account/recordings/{recording_id}/claim")
    legacy = buyer.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"})
    check("S2 عضو: CTA خرید با form_id؛ ادعای رایگان 409؛ مسیر قدیمی سفارش 410 → فرم", v["viewer"]["cta"].get("kind") == "buy" and v["viewer"]["cta"].get("form_id") == form_id
          and claim.status_code == 409 and detail_code(claim) == "recording_not_free" and legacy.status_code == 410 and detail_code(legacy) == "use_purchase_form",
          f"cta={v['viewer']['cta'].get('kind')} · claim {claim.status_code} {detail_code(claim)} · orders {legacy.status_code} {detail_code(legacy)}")
    buyer.get(f"/api/public/forms/{form_id}/draft")
    no_pay = buyer.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار"}})
    bought = buyer.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار QA"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    check("S2 ارسال بدون روش پرداخت 422؛ خرید کارت‌به‌کارت → awaiting_receipt", no_pay.status_code == 422 and bought.status_code == 200 and bought.json().get("payment_status") == "awaiting_receipt"
          and bought.json().get("purchase", {}).get("access_state") == "none", f"no-payment {no_pay.status_code} {detail_code(no_pay)} · buy {bought.status_code} {bought.json().get('payment_status')}")
    orders = mine(buyer, "/api/account/recording-orders", recording_id)
    order_id = orders[0]["id"] if orders else ""
    check("S2 دفتر داخلی: یک سفارش با مبلغ فرم", len(orders) == 1 and orders[0]["amount"] == 1_250_000 and orders[0]["purchase_form_id"] == form_id,
          f"orders={len(orders)} amount={orders[0]['amount'] if orders else None}")
    dl_pending = buyer.get(download)
    receipt = buyer.post(f"/api/public/forms/{form_id}/receipt", content=PNG, headers={"Content-Type": "image/png", "X-File-Name": quote("receipt.png"), "X-Receipt-Note": quote("واریز شد", safe="")})
    dl_after_receipt = buyer.get(download)
    lib = mine(buyer, "/api/account/recordings", recording_id)
    check("S2 رسید ≠ تأیید: پیش و پس از رسید دانلود 403، کتابخانه خالی", dl_pending.status_code == 403 and receipt.status_code == 200 and receipt.json().get("review_task_id")
          and dl_after_receipt.status_code == 403 and lib == [], f"before {dl_pending.status_code} {detail_reason(dl_pending)} · receipt {receipt.status_code} · after {dl_after_receipt.status_code} {detail_reason(dl_after_receipt)} · library={len(lib)}")
    task_id = receipt.json().get("review_task_id", "")
    dup = buyer.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار QA"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    orders2 = mine(buyer, "/api/account/recording-orders", recording_id)
    check("S2 ارسال دوبارهٔ همان خرید در حالت معلق: سفارش/پاسخ دوم ساخته نمی‌شود", dup.status_code in {200, 409} and len(orders2) == 1,
          f"resubmit {dup.status_code} {detail_code(dup) or 'همان پاسخ معلق برگشت'} · orders={len(orders2)}")
    regs = buyer.get("/api/account/registrations").json()
    reg_items = regs.get("items", regs if isinstance(regs, list) else [])
    check("S2 خرید ≠ ثبت‌نام: رویداد در «ثبت‌نام‌ها» به عنوان ثبت‌نام ظاهر نمی‌شود",
          not any((item.get("event") or {}).get("id") == event_id and item.get("registered") for item in reg_items if isinstance(item, dict)),
          f"registrations={len(reg_items)}")

    # ── S3: IDOR ──
    stranger, _ = member(95002)
    s_order = stranger.get(f"/api/account/recording-orders/{order_id}")
    s_dl = stranger.get(download)
    s_lib = {"items": mine(stranger, "/api/account/recordings", recording_id)}
    foreign_order = buyer.get("/api/account/recording-orders/0e0c2d39-e439-40fa-a896-4a60cf7fda56")
    wrong_event = buyer.get(f"/api/public/events/ev-dbbc5c5acb/resources/{resource_id}/download")
    check("S3 IDOR: سفارش دیگری 404، دانلود غریبه 403، کتابخانهٔ غریبه خالی، سفارش حساب دیگر 404، منبع زیر رویداد دیگر 404",
          s_order.status_code == 404 and s_dl.status_code == 403 and s_lib.get("items") == [] and foreign_order.status_code == 404 and wrong_event.status_code == 404,
          f"{s_order.status_code}/{s_dl.status_code}/{len(s_lib.get('items', []))}/{foreign_order.status_code}/{wrong_event.status_code}")
    s_task = stranger.post(f"/api/admin/inbox/{task_id}/decision", json={"decision": "approved", "reason": "x", "expected_version": 1})
    check("S3 عضو عادی نمی‌تواند رسید را تأیید کند", s_task.status_code in {401, 403}, f"→ {s_task.status_code}")

    # ── S4: manager approves in the shared inbox → access ──
    inbox = manager.get("/api/admin/inbox").json()
    item = next((row for row in inbox.get("items", []) if row["id"] == task_id), None)
    approved = manager.post(f"/api/admin/inbox/{task_id}/decision", json={"decision": "approved", "reason": "رسید با مبلغ تطبیق داده شد", "expected_version": item["version"] if item else 1})
    repeat = manager.post(f"/api/admin/inbox/{task_id}/decision", json={"decision": "approved", "reason": "دوباره", "expected_version": item["version"] if item else 1})
    check("S4 مدیر (receipt_approve): تأیید 200، تکرار 409", approved.status_code == 200 and repeat.status_code == 409,
          f"approve {approved.status_code} {detail_code(approved)} · repeat {repeat.status_code}", {"inbox_item": bool(item)})
    served = buyer.get(download)
    partial = buyer.get(download, headers={"Range": "bytes=4-7"})
    bad_range = buyer.get(download, headers={"Range": f"bytes={len(MP4) + 5}-"})
    lib = mine(buyer, "/api/account/recordings", recording_id)
    check("S4 خریدار: 200 با بایت‌های درست، Range 206، 416، کتابخانه فعال", served.status_code == 200 and served.content == MP4 and served.headers.get("x-nora-resource-access") == "purchased"
          and partial.status_code == 206 and partial.content == b"ftyp" and bad_range.status_code == 416 and len(lib) == 1 and lib[0]["access"]["state"] == "active",
          f"{served.status_code}/{partial.status_code}/{bad_range.status_code} library={len(lib)} state={lib[0]['access']['state'] if lib else None}")
    leak = [k for k in served.headers if "path" in k.lower() or "storage" in k.lower()] + [v for v in served.headers.values() if "/home/" in v or "private" in v.lower()]
    check("S4 بدون افشای نام فیزیکی/مسیر در سرآیندها", not leak, f"content-disposition={served.headers.get('content-disposition')}", leak)
    orders3 = mine(buyer, "/api/account/recording-orders", recording_id)
    check("S4 دفتر: همان یک سفارش، paid_manual", len(orders3) == 1 and orders3[0]["status"] == "paid_manual", f"orders={len(orders3)} status={orders3[0]['status'] if orders3 else None}")
    inter = buyer.get(f"/api/public/events/{event_id}/interaction").json()
    part = inter.get("viewer", {}).get("participation", {})
    certs = buyer.get("/api/account/certificates").json()
    cert_items = certs.get("items", certs if isinstance(certs, list) else [])
    check("S4 خرید ≠ حضور ≠ گواهی: registered/attended نادرست، گواهی صفر", part.get("registered") is False and part.get("attended") is False and inter["viewer"].get("buyer") is True
          and not [c for c in cert_items if isinstance(c, dict) and (c.get("event_id") == event_id or (c.get("event") or {}).get("id") == event_id)],
          f"participation={json.dumps(part, ensure_ascii=False)} buyer={inter['viewer'].get('buyer')} certs_for_event=0")
    twice = buyer.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار QA"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    check("S4 خرید دوباره روی حق فعال: 409 access_already_active", twice.status_code == 409 and detail_code(twice) == "access_already_active", f"→ {twice.status_code} {detail_code(twice)}")
    fresh, fresh_account = member(95001)  # new session / re-login
    v2 = fresh.get(f"/api/public/events/{event_id}/recording").json()["recording"]
    fresh_dl = fresh.get(download)
    check("S4 نشست تازه/ورود دوباره: بدون درخواست خرید مجدد (CTA view، دانلود 200)", fresh_account == buyer_account and v2["viewer"]["cta"].get("kind") == "view" and fresh_dl.status_code == 200,
          f"cta={v2['viewer']['cta'].get('kind')} download={fresh_dl.status_code}")

    # ── S5: rejected receipt → no access, fresh order allowed ──
    other, _ = member(95003)
    other.get(f"/api/public/forms/{form_id}/draft")
    o_buy = other.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار دوم"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    o_receipt = other.post(f"/api/public/forms/{form_id}/receipt", content=PNG, headers={"Content-Type": "image/png", "X-File-Name": quote("r.png")})
    o_task = o_receipt.json().get("review_task_id", "") if o_receipt.status_code == 200 else ""
    inbox = manager.get("/api/admin/inbox").json()
    item = next((row for row in inbox.get("items", []) if row["id"] == o_task), None)
    rejected = manager.post(f"/api/admin/inbox/{o_task}/decision", json={"decision": "rejected", "reason": "مبلغ رسید با فرم نمی‌خواند", "expected_version": item["version"] if item else 1})
    o_dl = other.get(download)
    o_orders = mine(other, "/api/account/recording-orders", recording_id)
    o_lib = mine(other, "/api/account/recordings", recording_id)
    check("S5 رسید ردشده: دانلود 403، کتابخانه خالی، وضعیت سفارش rejected", o_buy.status_code == 200 and o_receipt.status_code == 200 and rejected.status_code == 200
          and o_dl.status_code == 403 and o_lib == [] and o_orders and o_orders[0]["status"] == "rejected",
          f"buy {o_buy.status_code} · receipt {o_receipt.status_code} · reject {rejected.status_code} {detail_code(rejected)} · dl {o_dl.status_code} {detail_reason(o_dl)} · order={o_orders[0]['status'] if o_orders else None}")
    o_again = other.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار دوم"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    check("S5 پس از رد، خرید تازه ممکن است", o_again.status_code == 200, f"→ {o_again.status_code} {detail_code(o_again)}")

    # ── S6: free product (existing synthetic free product) — no fake transaction ──
    free_event = "ev-42372e6c0e"
    free_view = guest.get(f"/api/public/events/{free_event}/recording").json().get("recording") or {}
    free_id = free_view.get("id", "")
    freeman, _ = member(95004)
    claimed = freeman.post(f"/api/account/recordings/{free_id}/claim")
    claimed_again = freeman.post(f"/api/account/recordings/{free_id}/claim")
    f_orders = mine(freeman, "/api/account/recording-orders", free_id)
    check("S6 محصول رایگان: ادعا 201 بدون تراکنش، تکرار idempotent، سفارش صفر", claimed.status_code == 201 and claimed.json().get("access", {}).get("source") == "free"
          and claimed_again.status_code in {200, 201} and claimed_again.json().get("created") is False and f_orders == [],
          f"claim {claimed.status_code} · again {claimed_again.status_code} created={claimed_again.json().get('created') if claimed_again.status_code < 400 else '?'} · orders={len(f_orders)}")

    # ── S7: sale stop keeps entitlement; revoke closes it server-side ──
    paused = owner.post(f"{base}/status", json={"status": "sales_paused", "reason": "به‌روزرسانی ویدیوها"}, csrf="nora_csrf")
    dl_paused = buyer.get(download)
    s_view = stranger.get(f"/api/public/events/{event_id}/recording").json()["recording"]
    stranger.get(f"/api/public/forms/{form_id}/draft")
    s_buy = stranger.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "غریبه"}, "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}})
    check("S7 توقف فروش: دارندهٔ قبلی همچنان 200، دیگران off_sale و فرم 409", paused.status_code == 200 and dl_paused.status_code == 200
          and s_view["viewer"]["cta"].get("kind") == "off_sale" and s_buy.status_code == 409 and detail_code(s_buy) == "recording_not_on_sale",
          f"pause {paused.status_code} · holder dl {dl_paused.status_code} · stranger cta={s_view['viewer']['cta'].get('kind')} · buy {s_buy.status_code} {detail_code(s_buy)}")
    refund_url = f"/api/admin/recording-orders/{order_id}/refund"
    refund_manager = manager.post(refund_url, json={"reference": "QA-REF", "reason": "x"})
    refund_noref = owner.post(refund_url, json={"reason": "انصراف خریدار"}, csrf="nora_csrf")
    refunded = owner.post(refund_url, json={"reference": f"QA-REF-{RUN}", "reason": "انصراف خریدار (آزمون ۹.۶)"}, csrf="nora_csrf")
    refund_again = owner.post(refund_url, json={"reference": "again", "reason": "دوباره"}, csrf="nora_csrf")
    dl_revoked = buyer.get(download)
    lib = mine(buyer, "/api/account/recordings", recording_id)
    v3 = buyer.get(f"/api/public/events/{event_id}/recording").json()["recording"]
    check("S7 بازپرداخت فقط finance با مرجع: مدیر 403، بدون مرجع 422، مالک 200، تکرار 409؛ دسترسی سرور-سمت بسته (403 access_revoked)",
          refund_manager.status_code == 403 and refund_noref.status_code == 422 and refunded.status_code == 200 and refunded.json().get("access", {}).get("state") == "revoked"
          and refund_again.status_code == 409 and dl_revoked.status_code == 403 and detail_reason(dl_revoked) == "access_revoked" and lib and lib[0]["access"]["state"] == "revoked",
          f"{refund_manager.status_code}/{refund_noref.status_code}/{refunded.status_code}/{refund_again.status_code} · dl {dl_revoked.status_code} {detail_reason(dl_revoked)} · library={lib[0]['access']['state'] if lib else None} · cta={v3['viewer']['cta'].get('kind')}")
    free_base = f"/api/admin/events/{free_event}/recording"
    free_rows = owner.get(f"{free_base}/access").json()
    free_row = next((r for r in free_rows.get("items", []) if r.get("status") == "active" and r.get("source") == "free" and r.get("account_id") == claimed.json().get("access", {}).get("account_id", "∅")), None)
    if free_row is None:
        free_row = next((r for r in free_rows.get("items", []) if r.get("id") == claimed.json().get("access", {}).get("id")), None)
    bad_revoke = owner.post(f"{free_base}/access/{free_row['id'] if free_row else 'x'}/revoke", json={}, csrf="nora_csrf")
    revoke = manager.post(f"{free_base}/access/{free_row['id'] if free_row else 'x'}/revoke", json={"reason": "آزمون لغو دسترسی ۹.۶"})
    revoke_again = owner.post(f"{free_base}/access/{free_row['id'] if free_row else 'x'}/revoke", json={"reason": "دوباره"}, csrf="nora_csrf")
    free_resources = (guest.get(f"/api/public/events/{free_event}/recording").json().get("recording") or {}).get("sessions", [])
    free_resource_id = next((res["id"] for sess in free_resources for res in sess.get("resources", []) if res.get("access") == "purchased"), None)
    free_dl = freeman.get(f"/api/public/events/{free_event}/resources/{free_resource_id}/download") if free_resource_id else None
    f_lib = mine(freeman, "/api/account/recordings", free_id)
    check("S7 لغو دستی با دلیل اجباری (مدیر/مالک، idempotent): بدون دلیل 4xx، لغو 200، تکرار 200 همان ردیف، دانلود 403، کتابخانه revoked",
          free_row is not None and bad_revoke.status_code in {400, 422} and revoke.status_code == 200 and revoke_again.status_code == 200
          and revoke_again.json().get("status") == "revoked" and (free_dl is None or free_dl.status_code == 403) and f_lib and f_lib[0]["access"]["state"] == "revoked",
          f"no-reason {bad_revoke.status_code} · revoke {revoke.status_code} · again {revoke_again.status_code} · dl {(free_dl.status_code if free_dl else 'no purchased resource')} {detail_reason(free_dl) if free_dl else ''} · library={f_lib[0]['access']['state'] if f_lib else None}")

    # ── S8: external exposure acknowledgement for a paid product ──
    yt = owner.post(f"/api/admin/events/{event_id}/resources", json={"kind": "youtube", "title": "درس بیرونی", "link_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "access": "purchased", "status": "published"}, csrf="nora_csrf")
    check("S8 منبع یوتیوب خریداری‌شده روی محصول پولی بدون تأیید ریسک: 409", yt.status_code == 409 and detail_code(yt) == "external_exposure_acknowledgement_required", f"→ {yt.status_code} {detail_code(yt)}")

    # ── S9: audit API read-only + permission gate ──
    a_owner = owner.get("/api/admin/integrity/recordings")
    a_manager = manager.get("/api/admin/integrity/recordings")
    a_member = buyer.get("/api/admin/integrity/recordings")
    a_guest = guest.get("/api/admin/integrity/recordings")
    body = a_owner.json() if a_owner.status_code == 200 else {}
    check("S9 ممیزی: مالک/مدیر 200 و read_only، عضو 403، مهمان 401", a_owner.status_code == 200 and a_manager.status_code == 200 and body.get("read_only") is True
          and a_member.status_code == 403 and a_guest.status_code == 401, f"{a_owner.status_code}/{a_manager.status_code}/{a_member.status_code}/{a_guest.status_code}")
    note("S9 نتیجهٔ ممیزی پس از کل سناریو", f"severity={json.dumps(body.get('severity'))} counts={json.dumps(body.get('counts'), ensure_ascii=False)}")
    mine_findings = [f for f in body.get("findings", []) if f.get("refs", {}).get("recording_id") in {recording_id, free_id} or f.get("refs", {}).get("form_id") in {form_id, unpublished_form_id}]
    check("S9 پس از کل سناریو هیچ ناسازگاری برای این محصول ثبت نشده (بازپرداخت و لغو سازگار)", mine_findings == [], "findings for this product = 0", mine_findings)
    say(f"\nevent={event_id} recording={recording_id} form={form_id} unpublished_form={unpublished_form_id} order={order_id}")
    say(f"نتیجه: {len([l for l in LOG if l.startswith('✓')])} ✓ · {FAILED} ✗")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
