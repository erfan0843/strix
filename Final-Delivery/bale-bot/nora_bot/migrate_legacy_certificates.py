"""انتقال کنترل‌شدهٔ گواهی‌های قدیمی ربات به ثبت مشترک سرور — پیش‌فرض فقط‌خواندنی.

این اسکریپت **کپی** نمی‌سازد و هیچ ردیفی را در پایگاه ربات حذف یا بازنویسی
نمی‌کند؛ فقط برای هر گواهی که کلید مالک معتبر (``bale_user_id``) دارد، همان
ردیف را به ``/api/bot/certificates`` می‌فرستد و شناسهٔ سرور را در ستون
``shared_certificate_id`` همان ردیف می‌نشاند (قابل تکرار؛ idempotent).

* بدون ``--apply --yes`` هیچ اتصال شبکه‌ای برقرار و هیچ چیزی نوشته نمی‌شود.
* با ``--apply`` ابتدا پشتیبان خصوصی گرفته می‌شود، مالک سرور پیش‌بررسی می‌شود،
  سپس ردیف‌ها یکی‌یکی ارسال می‌شوند.
* گواهی‌ای که مالکش هویت سرور ندارد («unmapped») دست‌نخورده می‌ماند و فقط
  شمارش می‌شود — هیچ نگاشت خودکاری انجام نمی‌شود.
* گزارش خلاصه بدون نام، شماره یا شناسهٔ شخصی است.

اجرای این اسکریپت روی پایگاه عملیاتی فقط با تصمیم صریح مالک و پس از آزمایش
روی نسخهٔ آزمایشی مجاز است.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import shared_certificates as sc

_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")


class MigrationError(RuntimeError):
    """خطای امن بدون دادهٔ شخصی."""


def _backup_database(database_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    source = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
    destination = backup_dir / f"nora-legacy-before-certificates-{stamp}-{uuid.uuid4().hex[:8]}.sqlite"
    target = None
    try:
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        target = sqlite3.connect(destination)
        source.backup(target)
        target.commit()
        target.close()
        target = None
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
        return destination
    except Exception:
        if target is not None:
            target.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        source.close()


def _preflight_owner(api_client, owner_bale_user_id: str | None) -> None:
    if not owner_bale_user_id or not _USER_ID.fullmatch(owner_bale_user_id):
        raise MigrationError("owner_bale_user_id_required")
    if api_client is not None:
        return
    import shared_api

    shared_api._api_base()
    identity = shared_api.get_identity(owner_bale_user_id)
    if identity.role != "owner":
        raise MigrationError("server_owner_identity_required")


def scan(run, *, base_dir: Path, allowed_roots: tuple[Path, ...]) -> dict[str, Any]:
    """شمارش فقط‌خواندنی: چه چیزی قابل‌ارسال است و چه چیزی باید جدا بماند."""
    columns = sc._table_columns(run, "certificates")
    if not columns:
        raise MigrationError("legacy_certificates_table_not_found")
    has_link = "shared_certificate_id" in columns
    rows = run("SELECT * FROM certificates ORDER BY id", fetch="all") or []
    summary = {
        "total": len(rows), "already_linked": 0, "candidates": 0, "without_owner_key": 0,
        "revoked_candidates": 0, "with_pdf": 0, "with_png": 0, "file_unavailable": 0,
    }
    candidate_ids: list[int] = []
    for row in rows:
        if has_link and row.get("shared_certificate_id"):
            summary["already_linked"] += 1
            continue
        owner = row.get("bale_user_id")
        if owner is None or not _USER_ID.fullmatch(str(owner)):
            summary["without_owner_key"] += 1
            continue
        summary["candidates"] += 1
        candidate_ids.append(int(row["id"]))
        if int(row.get("revoked") or 0):
            summary["revoked_candidates"] += 1
        pdf = sc.resolve_file(row.get("pdf_path"), base_dir=base_dir, allowed_roots=allowed_roots)
        png = sc.resolve_file(row.get("png_path"), base_dir=base_dir, allowed_roots=allowed_roots)
        if pdf:
            summary["with_pdf"] += 1
        if png:
            summary["with_png"] += 1
        if (row.get("pdf_path") and not pdf) or (row.get("png_path") and not png):
            summary["file_unavailable"] += 1
    return {"summary": summary, "candidate_ids": candidate_ids}


def run_migration(
    database_path: str | Path,
    *,
    apply: bool = False,
    owner_bale_user_id: str | int | None = None,
    allowed_roots: tuple[str | Path, ...] = (),
    backup_dir: str | Path | None = None,
    api_client=None,
    include_revoked: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise MigrationError("database_file_not_found")
    owner_id = str(owner_bale_user_id) if owner_bale_user_id is not None else None
    roots = tuple(Path(root).expanduser() for root in allowed_roots) or sc.default_roots()
    backup_path = None
    if apply:
        _preflight_owner(api_client, owner_id)
        backup_root = Path(backup_dir).expanduser() if backup_dir else path.parent / "migration-backups"
        backup_path = _backup_database(path, backup_root)
        conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)
    else:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    run = sc.connection_executor(conn)
    try:
        scanned = scan(run, base_dir=path.parent, allowed_roots=roots)
        summary: dict[str, Any] = {
            "mode": "apply" if apply else "dry-run",
            **scanned["summary"],
            "mirrored": 0, "unmapped": 0, "failed": 0, "skipped_revoked": 0,
            "issues": {}, "backup": backup_path.name if backup_path else None,
        }
        if not apply:
            summary["note"] = "هیچ رکورد، فایل یا سرویس خارجی تغییر نکرد."
            return summary
        if api_client is None:
            import shared_api as api_client  # noqa: PLC0415
        sc.ensure_sync_columns(run)
        sc.source_id(run, create=True)
        processed = 0
        for cert_id in scanned["candidate_ids"]:
            if limit is not None and processed >= limit:
                break
            row = sc.load_certificate(run, cert_id) or {}
            if not include_revoked and int(row.get("revoked") or 0):
                summary["skipped_revoked"] += 1
                continue
            processed += 1
            outcome = sc.sync_certificate(
                cert_id, run=run, api_client=api_client, source="bot_legacy",
                allowed_roots=roots, base_dir=path.parent,
            )
            kind = outcome.get("outcome")
            if kind == "mirrored":
                summary["mirrored"] += 1
            elif kind == "unmapped":
                summary["unmapped"] += 1
                code = outcome.get("code") or "owner_identity_not_found"
                summary["issues"][code] = summary["issues"].get(code, 0) + 1
            else:
                summary["failed"] += 1
                code = outcome.get("code") or "migration_item_failed"
                code = code if re.fullmatch(r"[A-Za-z0-9_]{1,80}", str(code)) else "migration_item_failed"
                summary["issues"][code] = summary["issues"].get(code, 0) + 1
        return summary
    finally:
        conn.close()


def _print_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    print("گزارش انتقال گواهی‌های قدیمی به ثبت مشترک")
    print(f"حالت: {summary['mode']}")
    print(f"کل ردیف‌ها: {summary['total']} · از قبل متصل: {summary['already_linked']}")
    print(f"قابل‌ارسال (کلید مالک معتبر): {summary['candidates']} · بدون کلید مالک (جدا می‌ماند): {summary['without_owner_key']}")
    print(f"باطل‌شده در بین قابل‌ارسال‌ها: {summary['revoked_candidates']}")
    print(f"فایل PDF در دسترس: {summary['with_pdf']} · PNG: {summary['with_png']} · فایل ثبت‌شده ولی در دسترس نیست: {summary['file_unavailable']}")
    if summary["mode"] == "dry-run":
        print(summary.get("note", ""))
        return
    if summary["backup"]:
        print(f"پشتیبان: {summary['backup']}")
    print(f"آینه‌شده: {summary['mirrored']} · بدون هویت سرور (unmapped): {summary['unmapped']} · ناموفق: {summary['failed']}")
    if summary["issues"]:
        print("موارد نیازمند رسیدگی:")
        for code, count in sorted(summary["issues"].items()):
            print(f"  • {code}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="بازبینی یا انتقال کنترل‌شدهٔ گواهی‌های قدیمی به ثبت مشترک؛ پیش‌فرض فقط‌خواندنی است."
    )
    parser.add_argument("--database", required=True, help="مسیر فایل SQLite ربات (نسخهٔ آزمایشی یا با تصمیم صریح مالک)")
    parser.add_argument("--owner-id", help="شناسهٔ بلهٔ مالک برای پیش‌بررسی مجوز سرور")
    parser.add_argument("--file-root", action="append", default=[], help="ریشهٔ مجاز فایل گواهی؛ قابل تکرار")
    parser.add_argument("--backup-dir", help="مسیر پشتیبان خصوصی برای حالت --apply")
    parser.add_argument("--skip-revoked", action="store_true", help="گواهی‌های باطل‌شده ارسال نشوند")
    parser.add_argument("--limit", type=int, help="حداکثر تعداد ردیف در این اجرا (برای ارسال مرحله‌ای)")
    parser.add_argument("--apply", action="store_true", help="ارسال به API و ثبت شناسهٔ سرور روی ردیف")
    parser.add_argument("--yes", action="store_true", help="تأیید صریح برای --apply")
    parser.add_argument("--json", action="store_true", help="خروجی خلاصهٔ JSON بدون دادهٔ شخصی")
    args = parser.parse_args(argv)
    if args.yes and not args.apply:
        parser.error("--yes فقط همراه --apply مجاز است")
    if args.apply and not args.yes:
        parser.error("برای هر تغییری، هم --apply و هم --yes لازم است")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit باید عدد مثبت باشد")
    try:
        import config

        configured_owner_id = str(config.SUPER_ADMIN_ID) if config.SUPER_ADMIN_ID else None
    except Exception:
        configured_owner_id = os.getenv("SUPER_ADMIN_ID")
    try:
        summary = run_migration(
            args.database,
            apply=args.apply,
            owner_bale_user_id=args.owner_id or configured_owner_id,
            allowed_roots=tuple(args.file_root),
            backup_dir=args.backup_dir,
            include_revoked=not args.skip_revoked,
            limit=args.limit,
        )
    except Exception as exc:
        code = getattr(exc, "code", None)
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,80}", code):
            code = str(exc) if isinstance(exc, (MigrationError, sc.CertificateSyncError)) else "migration_preflight_or_io_error"
        print(f"❌ انتقال انجام نشد: {code}")
        return 2
    _print_summary(summary, as_json=args.json)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
