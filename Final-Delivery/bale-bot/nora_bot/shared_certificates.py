"""آینهٔ گواهی‌های صادرشده در سرور مشترک (ربات صادرکننده می‌ماند).

ربات تنها جایی است که گواهی صادر یا باطل می‌کند؛ این ماژول پس از هر صدور/ابطال،
همان ردیف را به ثبت مشترک سرور می‌فرستد تا پنل مدیران از منبع معتبر بخواند.
قواعد:

* کلید مالک فقط ``bale_user_id`` است؛ سرور آن را به حساب وب نگاشت می‌کند و
  اگر هویتی نباشد (``owner_identity_not_found``) ردیف ذخیره نمی‌شود — هیچ
  حساب یا نگاشتی این‌جا ساخته نمی‌شود.
* کلید پایدار هر ردیف ``<source_id>:<id>`` است (``source_id`` شناسهٔ همین
  پایگاه در جدول ``nora_legacy_migration_meta``)؛ ارسال تکراری بی‌اثر است.
* فایل‌ها (PDF/PNG) فقط از داخل ریشه‌های مجاز خوانده و با همان مکانیزم فایل
  خصوصی سرور (``/api/bot/files``) بارگذاری می‌شوند.
* خطاهای سرور هرگز جریان صدور ربات را نمی‌شکنند؛ فقط لاگ کوتاه بدون دادهٔ
  شخصی ثبت می‌شود. نتیجهٔ آخرین همگام‌سازی در ستون‌های
  ``shared_certificate_id`` / ``shared_synced_at`` همان ردیف می‌نشیند.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_META_TABLE = "nora_legacy_migration_meta"
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\Z")
_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_MAX_FILE = 8 * 1024 * 1024
_SOURCE_KINDS = {"event": "event", "batch": "batch", "form": "form", "manual": "manual", "center": "center"}
SYNC_COLUMNS = {"shared_certificate_id": "TEXT", "shared_synced_at": "TEXT"}

Executor = Callable[..., Any]


class CertificateSyncError(RuntimeError):
    """خطای امن بدون دادهٔ شخصی؛ ``code`` برای خلاصهٔ CLI."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ───────────────────────── اجراکننده‌ها ─────────────────────────
def runtime_executor() -> Executor:
    """اجراکنندهٔ زمان اجرا: همان ``database.db_execute`` ربات."""
    from database import db_execute

    return db_execute


def connection_executor(conn: sqlite3.Connection) -> Executor:
    """اجراکننده روی یک اتصال sqlite3 (برای CLI و آزمون‌ها)؛ همان قرارداد ``db_execute``."""
    conn.row_factory = sqlite3.Row

    def run(query: str, params: tuple = (), fetch: str | None = None):
        cur = conn.execute(query, params)
        if fetch == "one":
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch == "all":
            return [dict(r) for r in cur.fetchall()]
        conn.commit()
        return cur.lastrowid

    return run


def _table_columns(run: Executor, table: str) -> set[str]:
    return {row["name"] for row in run(f"PRAGMA table_info({table})", fetch="all") or []}


def ensure_sync_columns(run: Executor) -> None:
    """ستون‌های پیوند را اگر نباشند اضافه می‌کند (idempotent؛ بدون تغییر دادهٔ موجود)."""
    have = _table_columns(run, "certificates")
    for column, kind in SYNC_COLUMNS.items():
        if column not in have:
            run(f"ALTER TABLE certificates ADD COLUMN {column} {kind}")
    run(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cert_shared_id ON certificates(shared_certificate_id) "
        "WHERE shared_certificate_id IS NOT NULL"
    )


def source_id(run: Executor, *, create: bool) -> str | None:
    """شناسهٔ پایدار این پایگاه؛ با ``create=False`` فقط می‌خواند."""
    exists = run(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (_META_TABLE,), fetch="one"
    )
    if not exists:
        if not create:
            return None
        run(f'CREATE TABLE IF NOT EXISTS "{_META_TABLE}" (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    row = run(f'SELECT value FROM "{_META_TABLE}" WHERE key=?', ("source_id",), fetch="one")
    if row:
        value = str(row["value"])
        if not _UUID.fullmatch(value):
            raise CertificateSyncError("migration_source_id_invalid")
        return value
    if not create:
        return None
    value = str(uuid.uuid4())
    run(f'INSERT INTO "{_META_TABLE}" (key,value) VALUES (?,?)', ("source_id", value))
    return value


# ───────────────────────── ساخت payload ─────────────────────────
def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", "").strip()
    return text[:limit]


def _iso(value: Any) -> str | None:
    """``issued_at`` ربات به شکل ``YYYY-MM-DD HH:MM:SS`` (UTC، از SQLite) است."""
    if not value:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], pattern).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def load_certificate(run: Executor, cert_id: int) -> dict[str, Any] | None:
    return run("SELECT * FROM certificates WHERE id=?", (int(cert_id),), fetch="one")


def build_payload(run: Executor, cert: dict[str, Any], *, source: str, source_key: str) -> dict[str, Any]:
    """دادهٔ قابل‌ارسال از یک ردیف گواهی؛ بدون نام/شماره‌ای که در پایگاه ربات نیست."""
    event_title = ""
    event_ref = ""
    if cert.get("event_id"):
        event_ref = str(int(cert["event_id"]))
        row = run("SELECT title FROM events WHERE id=?", (int(cert["event_id"]),), fetch="one")
        event_title = _text((row or {}).get("title"), 200)
    title = ""
    if cert.get("event_cert_id"):
        row = run("SELECT title FROM event_certs WHERE id=?", (int(cert["event_cert_id"]),), fetch="one")
        title = _text((row or {}).get("title"), 200)
    if not title and cert.get("template_id"):
        row = run("SELECT name FROM cert_templates WHERE id=?", (int(cert["template_id"]),), fetch="one")
        title = _text((row or {}).get("name"), 200)
    holder = ""
    if cert.get("bale_user_id"):
        row = run(
            "SELECT first_name, last_name, bale_first_name, bale_last_name FROM users WHERE bale_user_id=?",
            (int(cert["bale_user_id"]),), fetch="one",
        ) or {}
        holder = " ".join(part for part in (
            _text(row.get("first_name") or row.get("bale_first_name"), 80),
            _text(row.get("last_name") or row.get("bale_last_name"), 80),
        ) if part)
    kind = _SOURCE_KINDS.get(str(cert.get("source") or "event").strip().lower(), "event")
    issued_by = _text(cert.get("issued_by"), 40)
    if issued_by and not _USER_ID.fullmatch(issued_by):
        issued_by = ""
    verify_count = cert.get("verify_count") or 0
    try:
        verify_count = max(0, min(int(verify_count), 1_000_000))
    except (TypeError, ValueError):
        verify_count = 0
    return {
        "status": "revoked" if int(cert.get("revoked") or 0) else "issued",
        "source": source,
        "source_id": source_key,
        "legacy_id": int(cert["id"]),
        "kind": kind,
        "serial": _text(cert.get("serial"), 80),
        "full_code": _text(cert.get("full_code"), 120),
        "doc_no": _text(cert.get("doc_no"), 80),
        "person_code": _text(cert.get("person_code"), 80),
        "event_ref": event_ref,
        "event_title": event_title,
        "title": title,
        "holder_name": holder[:160],
        "issued_on": _text(cert.get("issued_on"), 32),
        "expires_on": _text(cert.get("expires_on"), 32),
        "issued_at": _iso(cert.get("issued_at")),
        "issued_by_bale_user_id": issued_by,
        "verify_count": verify_count,
    }


# ───────────────────────── فایل‌ها ─────────────────────────
def default_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    try:
        import config

        roots.append(Path(config.FILES_DIR))
    except Exception:
        pass
    return tuple(roots)


def resolve_file(raw_path: Any, *, base_dir: Path, allowed_roots: tuple[Path, ...]) -> Path | None:
    """مسیر فایل را فقط اگر داخل ریشه‌های مجاز، موجود و در حد مجاز باشد برمی‌گرداند."""
    if not isinstance(raw_path, str) or not raw_path.strip() or not allowed_roots:
        return None
    resolved_roots = []
    for root in allowed_roots:
        try:
            resolved_roots.append(Path(root).expanduser().resolve())
        except (OSError, RuntimeError):
            continue
    raw = Path(raw_path.strip())
    candidates = [raw] if raw.is_absolute() else [base_dir / raw, Path.cwd() / raw]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if not resolved.is_file() or not any(resolved.is_relative_to(root) for root in resolved_roots):
            continue
        try:
            size = resolved.stat().st_size
        except OSError:
            return None
        if 1 <= size <= _MAX_FILE:
            return resolved
    return None


def _sniff_ok(content: bytes, slot: str) -> bool:
    if slot == "pdf":
        return content.startswith(b"%PDF-")
    return content.startswith(b"\x89PNG\r\n\x1a\n")


# ───────────────────────── همگام‌سازی یک ردیف ─────────────────────────
def sync_certificate(
    cert_id: int,
    *,
    run: Executor | None = None,
    api_client=None,
    source: str = "bot",
    allowed_roots: tuple[Path, ...] | None = None,
    base_dir: Path | None = None,
    upload_files: bool = True,
) -> dict[str, Any]:
    """یک گواهی را به سرور می‌فرستد و نتیجه را روی همان ردیف ثبت می‌کند.

    خروجی: ``{"outcome": "mirrored"|"unmapped"|"failed"|"missing", "shared_id": str|None, "code": str|None}``.
    ``unmapped`` یعنی مالک هویت سرور ندارد؛ ردیف ربات دست‌نخورده می‌ماند.
    """
    run = run or runtime_executor()
    if api_client is None:
        import shared_api as api_client  # noqa: PLC0415
    cert = load_certificate(run, cert_id)
    if not cert:
        return {"outcome": "missing", "shared_id": None, "code": "certificate_not_found"}
    owner = cert.get("bale_user_id")
    if owner is None or not _USER_ID.fullmatch(str(owner)):
        return {"outcome": "unmapped", "shared_id": None, "code": "certificate_without_owner_key"}
    ensure_sync_columns(run)
    key_source = source_id(run, create=True)
    external_key = f"{key_source}:{int(cert['id'])}"
    payload = build_payload(run, cert, source=source, source_key=key_source or "")
    try:
        first = api_client.submit_certificate(str(owner), external_key, payload)
    except Exception as exc:  # SharedAPIError یا شبکه
        code = getattr(exc, "code", None) or type(exc).__name__
        if code == "owner_identity_not_found":
            return {"outcome": "unmapped", "shared_id": None, "code": code}
        return {"outcome": "failed", "shared_id": None, "code": str(code)[:80]}
    result = first
    if upload_files:
        roots = allowed_roots if allowed_roots is not None else default_roots()
        base = base_dir or _database_dir()
        refs: dict[str, str] = {}
        for slot, column in (("pdf", "pdf_path"), ("png", "png_path")):
            path = resolve_file(cert.get(column), base_dir=base, allowed_roots=tuple(roots))
            if path is None and slot == "pdf" and str(cert.get("file_path") or "").lower().endswith(".pdf"):
                path = resolve_file(cert.get("file_path"), base_dir=base, allowed_roots=tuple(roots))
            if path is None:
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if not _sniff_ok(content, slot):
                continue
            try:
                refs[slot] = api_client.upload_private_file(
                    str(owner), content, f"certificate-{int(cert['id'])}.{slot}",
                    f"cert-file:{key_source}:{int(cert['id'])}:{slot}",
                )
            except Exception as exc:
                return {"outcome": "failed", "shared_id": first.get("id"), "code": str(getattr(exc, "code", "file_upload_failed"))[:80]}
        if refs:
            try:
                result = api_client.submit_certificate(str(owner), external_key, payload, refs)
            except Exception as exc:
                return {"outcome": "failed", "shared_id": first.get("id"), "code": str(getattr(exc, "code", "file_link_failed"))[:80]}
    shared_id = result.get("id")
    run(
        "UPDATE certificates SET shared_certificate_id=?, shared_synced_at=datetime('now') WHERE id=?",
        (shared_id, int(cert["id"])),
    )
    return {"outcome": "mirrored", "shared_id": shared_id, "code": None, "created": bool(first.get("created"))}


def _database_dir() -> Path:
    try:
        import config

        return Path(config.DB_PATH).expanduser().resolve().parent
    except Exception:
        return Path.cwd()


def sync_after_change(cert_id: Any) -> None:
    """قلاب بهترین‌تلاش برای مسیرهای صدور/ابطال ربات؛ هرگز استثنا بیرون نمی‌دهد."""
    try:
        if cert_id is None:
            return
        import config

        if not getattr(config, "SHARED_API_URL", "") or not getattr(config, "SHARED_API_TOKEN", ""):
            return
        outcome = sync_certificate(int(cert_id))
        if outcome.get("outcome") == "failed":
            from database import log

            log(f"⚠️ همگام‌سازی گواهی #{int(cert_id)} با سرور: {outcome.get('code')}")
    except Exception as exc:  # pragma: no cover - defensive
        try:
            from database import log

            log(f"⚠️ همگام‌سازی گواهی: {type(exc).__name__}")
        except Exception:
            pass
