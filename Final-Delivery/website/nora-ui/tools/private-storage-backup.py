#!/usr/bin/env python3
"""Operator tool for the private file store (phase 9.4) — read-only unless you say ``restore``.

Files uploaded for paid/private resources live OUTSIDE the database (``NORA_PRIVATE_STORAGE_DIR``);
the DB only keeps ``event_resources.storage_key``.  A database backup therefore does NOT contain the
videos: back the directory up separately and check both halves against each other.

    verify                      compare DB rows ↔ files; prints JSON; exit 1 if anything referenced is missing/mismatched
    snapshot <dir>              copy every *committed* file (never ``.incoming``) + MANIFEST.json with sha256
    restore  <dir> [--force]    copy files from a snapshot back (hash-checked); never overwrites an existing file unless --force

Nothing here deletes anything: orphans and stale ``.part`` files are *listed* for a human decision.
Environment: NORA_DATABASE_URL (same as the server), NORA_PRIVATE_STORAGE_DIR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend import storage as storage_mod  # noqa: E402
from backend.models import EventResourceRecord  # noqa: E402

CHUNK = 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for piece in iter(lambda: handle.read(CHUNK), b""):
            digest.update(piece)
    return digest.hexdigest()


def database_url() -> str:
    url = os.getenv("NORA_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("NORA_DATABASE_URL is required (same value as the server)")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def storage_root() -> Path:
    raw = os.getenv("NORA_PRIVATE_STORAGE_DIR", "").strip()
    if not raw:
        raise SystemExit("NORA_PRIVATE_STORAGE_DIR is required")
    return Path(raw).expanduser()


def referenced_rows() -> list[tuple[str, str, int | None, str | None]]:
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with Session(engine) as db:
            rows = db.execute(
                select(EventResourceRecord.id, EventResourceRecord.storage_key, EventResourceRecord.content_size,
                       EventResourceRecord.content_hash).where(EventResourceRecord.storage_key.is_not(None))
            ).all()
        return [(str(r[0]), str(r[1]), r[2], r[3]) for r in rows]
    finally:
        engine.dispose()


def record_marker(key: str, value: dict[str, object]) -> None:
    """Phase 9.5: remember the last verify/snapshot/restore in ``system_markers`` (read by the health view).

    Best effort and additive: a database that predates migration 0036 simply gets no marker.
    """
    from sqlalchemy import text

    from backend.models import SystemMarkerRecord

    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with Session(engine) as db:
            try:
                db.execute(text("SELECT 1 FROM system_markers LIMIT 1"))
            except Exception:  # noqa: BLE001 - table absent (older schema): skip silently
                db.rollback()
                return
            row = db.get(SystemMarkerRecord, key)
            stamp = datetime.now(timezone.utc)
            if row is None:
                db.add(SystemMarkerRecord(key=key, value=value, updated_at=stamp))
            else:
                row.value = value
                row.updated_at = stamp
            db.commit()
    finally:
        engine.dispose()


def list_committed(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for year in sorted(p for p in root.iterdir() if p.is_dir() and p.name != storage_mod.INCOMING_DIR):
        for month in sorted(p for p in year.iterdir() if p.is_dir()):
            for item in sorted(p for p in month.iterdir() if p.is_file()):
                key = f"{year.name}/{month.name}/{item.name}"
                if storage_mod.KEY_PATTERN.fullmatch(key):
                    found[key] = item
    return found


def cmd_verify(args: argparse.Namespace) -> int:
    root = storage_root()
    rows = referenced_rows()
    files = list_committed(root)
    missing, mismatch, ok = [], [], 0
    for _resource_id, key, size, digest in rows:
        path = files.get(key)
        if path is None:
            missing.append(key)
            continue
        actual = path.stat().st_size
        if size is not None and actual != size:
            mismatch.append({"key": key, "db_size": size, "file_size": actual})
            continue
        if args.hash and digest and sha256_of(path) != digest:
            mismatch.append({"key": key, "reason": "sha256"})
            continue
        ok += 1
    referenced_keys = {key for _r, key, _s, _d in rows}
    orphans = sorted(k for k in files if k not in referenced_keys)
    incoming = root / storage_mod.INCOMING_DIR
    stale = sorted(p.name for p in incoming.iterdir() if p.is_file()) if incoming.is_dir() else []
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage_exists": root.is_dir(),
        "referenced": len(rows), "ok": ok, "missing": missing, "size_mismatch": mismatch,
        "orphans": orphans, "stale_parts": stale, "hash_checked": bool(args.hash),
        "note": "orphans/stale parts are listed only; deleting them is a manual, audited operator decision",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_marker:
        record_marker("storage_verify", {"ok": not (missing or mismatch), "referenced": len(rows), "missing": len(missing),
                                         "size_mismatch": len(mismatch), "orphans": len(orphans), "stale_parts": len(stale),
                                         "hash_checked": bool(args.hash)})
    return 1 if missing or mismatch else 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = storage_root()
    target = Path(args.target).expanduser()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"snapshot target {target} is not empty")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest: dict[str, object] = {"taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": {}}
    files = manifest["files"]
    assert isinstance(files, dict)
    for key, path in list_committed(root).items():
        destination = target / key
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        os.chmod(destination, 0o600)
        files[key] = {"size": destination.stat().st_size, "sha256": sha256_of(destination)}
    (target / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot": str(target), "files": len(files)}, ensure_ascii=False))
    if not args.no_marker:
        record_marker("storage_snapshot", {"ok": True, "files": len(files), "bytes": int(sum(int(meta["size"]) for meta in files.values()))})
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    root = storage_root()
    source = Path(args.source).expanduser()
    manifest_path = source / "MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit(f"{manifest_path} not found — not a snapshot made by this tool")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    restored, skipped, corrupt = [], [], []
    for key, meta in manifest["files"].items():
        if not storage_mod.KEY_PATTERN.fullmatch(key):
            corrupt.append(key)
            continue
        origin = source / key
        if not origin.is_file() or sha256_of(origin) != meta["sha256"]:
            corrupt.append(key)
            continue
        destination = root / key
        if destination.exists() and not args.force:
            skipped.append(key)
            continue
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = destination.with_suffix(".restore")
        shutil.copyfile(origin, temp)
        os.chmod(temp, 0o600)
        os.replace(temp, destination)
        restored.append(key)
    print(json.dumps({"restored": len(restored), "skipped_existing": skipped, "corrupt_in_snapshot": corrupt}, ensure_ascii=False, indent=2))
    if not args.no_marker:
        record_marker("storage_restore", {"ok": not corrupt, "restored": len(restored), "skipped_existing": len(skipped), "corrupt": len(corrupt)})
    return 1 if corrupt else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--hash", action="store_true", help="also recompute sha256 of every referenced file (slow)")
    verify.set_defaults(func=cmd_verify)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("target")
    snapshot.set_defaults(func=cmd_snapshot)
    restore = sub.add_parser("restore")
    restore.add_argument("source")
    restore.add_argument("--force", action="store_true", help="overwrite files that already exist in the store")
    restore.set_defaults(func=cmd_restore)
    for command in (verify, snapshot, restore):
        command.add_argument("--no-marker", action="store_true", help="do not record the run in system_markers")
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
