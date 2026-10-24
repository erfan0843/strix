"""Private staging for uploaded SQLite backups, inspected strictly read-only.

Hard rules enforced here (and tested):
* The staging directory is outside the static UI root and is never mounted.
* A file is accepted only if it starts with the SQLite header, passes
  ``PRAGMA quick_check`` and is readable in ``mode=ro`` + ``query_only``.
* Nothing in this module writes to the uploaded file. The audit step re-hashes
  the file before and after and records whether it changed.
* Names are never used as paths: every upload gets a generated id and its
  display name is sanitised (no directories, no control characters).
* Metadata and reports never contain row values, phone numbers or names — only
  counts, states and checksums.
* Retention and quota are explicit: expired uploads are purged on the next
  listing, and a new upload is refused when the staging quota is full.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SQLITE_HEADER = b"SQLite format 3\x00"
STATE_RECEIVED = "received"
STATE_INSPECTED = "inspected"
STATE_INVALID = "invalid"
STATE_AUDITED = "audited"
STATE_AUDIT_FAILED = "audit_failed"
AUDIT_TIMEOUT_SECONDS = 180
QUOTA_FACTOR = 8  # staging quota = 8x the single-upload ceiling


class StagingError(RuntimeError):
    """A safe error code; never carries file content or paths."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class UploadLimits:
    max_bytes: int
    retention_hours: int
    # 0 means "derive from the single-upload ceiling"; a non-zero value lets a
    # deployment (or a test) cap the whole staging area explicitly.
    quota_bytes: int = 0

    def quota(self) -> int:
        return self.quota_bytes or self.max_bytes * QUOTA_FACTOR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def safe_display_name(raw: str) -> str:
    """Keep a human-readable name without any path or control characters."""
    base = str(raw or "").replace("\\", "/").split("/")[-1]
    cleaned = "".join(char for char in base if char.isprintable() and char not in '\\"<>')
    cleaned = cleaned.strip()[:120]
    if not cleaned:
        return "backup.db"
    if not cleaned.lower().endswith((".db", ".sqlite", ".sqlite3", ".db3", ".bak")):
        cleaned = cleaned[:110] + ".db"
    return cleaned


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StagingStore:
    def __init__(self, root: str | Path, limits: UploadLimits):
        self.root = Path(root)
        self.limits = limits

    # ── layout ────────────────────────────────────────────────────────────
    @property
    def uploads_dir(self) -> Path:
        return self.root / "uploads"

    def _dir(self, upload_id: str) -> Path:
        if not upload_id or not upload_id.isalnum() or len(upload_id) > 40:
            raise StagingError("invalid_upload_id")
        path = self.uploads_dir / upload_id
        resolved = path.resolve()
        if self.uploads_dir.resolve() not in resolved.parents:
            raise StagingError("invalid_upload_id")
        return path

    def _meta_path(self, upload_id: str) -> Path:
        return self._dir(upload_id) / "meta.json"

    def _read_meta(self, upload_id: str) -> dict[str, Any]:
        path = self._meta_path(upload_id)
        if not path.is_file():
            raise StagingError("upload_not_found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise StagingError("upload_metadata_unreadable") from None
        if not isinstance(data, dict):
            raise StagingError("upload_metadata_unreadable")
        return data

    def _write_meta(self, upload_id: str, meta: dict[str, Any]) -> None:
        target = self._meta_path(upload_id)
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, target)

    def ensure_root(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # ── quota & retention ────────────────────────────────────────────────
    def _used_bytes(self) -> int:
        total = 0
        if not self.uploads_dir.is_dir():
            return 0
        for entry in self.uploads_dir.iterdir():
            if entry.is_dir():
                for item in entry.rglob("*"):
                    if item.is_file():
                        total += item.stat().st_size
        return total

    def usage_bytes(self) -> int:
        """Total bytes currently held in staging (never the path itself)."""
        return self._used_bytes()

    def purge_expired(self) -> int:
        """Delete uploads past retention; returns how many were removed."""
        removed = 0
        if not self.uploads_dir.is_dir():
            return 0
        now = _now()
        for entry in list(self.uploads_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "meta.json"
            expired = False
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    expires = datetime.fromisoformat(str(meta.get("expires_at")))
                    expired = expires <= now
                except (OSError, ValueError, TypeError):
                    expired = True
            else:
                # An orphan directory without metadata is stale by definition.
                stat = entry.stat()
                expired = (_now() - datetime.fromtimestamp(stat.st_mtime, timezone.utc)) > timedelta(
                    hours=self.limits.retention_hours
                )
            if expired:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        return removed

    # ── inspection ───────────────────────────────────────────────────────
    @staticmethod
    def inspect_sqlite(path: Path) -> dict[str, Any]:
        """Read-only structural check. Raises StagingError on anything suspicious."""
        if path.is_symlink() or not path.is_file():
            raise StagingError("invalid_backup_file")
        if path.stat().st_size < len(SQLITE_HEADER):
            raise StagingError("backup_not_sqlite")
        with path.open("rb") as handle:
            if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                raise StagingError("backup_not_sqlite")
        uri = f"file:{path}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error:
            raise StagingError("backup_not_sqlite") from None
        try:
            connection.execute("PRAGMA query_only=ON")
            check_rows = [row[0] for row in connection.execute("PRAGMA quick_check")]
            if check_rows != ["ok"]:
                raise StagingError("backup_integrity_check_failed")
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        except sqlite3.DatabaseError:
            raise StagingError("backup_integrity_check_failed") from None
        finally:
            connection.close()
        # The audit tool's own gate: a database without ``users`` is not a Nora
        # legacy backup at all, so it is rejected instead of being audited.
        if "users" not in tables:
            raise StagingError("backup_not_legacy_database")
        return {
            "table_count": len(tables),
            "tables_sample": sorted(tables)[:40],
            "user_version": int(user_version or 0),
            "size_bytes": int(page_count or 0) * int(page_size or 0),
            "integrity": "ok",
        }

    # ── upload ───────────────────────────────────────────────────────────
    def create_upload(self, chunks: Iterable[bytes], declared_name: str) -> dict[str, Any]:
        """Stream an upload into staging; never trusts the declared name or type."""
        self.ensure_root()
        self.purge_expired()
        used = self._used_bytes()
        if used >= self.limits.quota():
            raise StagingError("staging_quota_exceeded")

        upload_id = uuid.uuid4().hex
        target_dir = self.uploads_dir / upload_id
        temp_dir = self.root / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp_file = temp_dir / f"{upload_id}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with temp_file.open("wb") as handle:
                for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.limits.max_bytes:
                        raise StagingError("backup_too_large")
                    if used + size > self.limits.quota():
                        raise StagingError("staging_quota_exceeded")
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise StagingError("empty_backup_file")
            with temp_file.open("rb") as handle:
                if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                    raise StagingError("backup_not_sqlite")
            structure = self.inspect_sqlite(temp_file)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

        target_dir.mkdir(mode=0o700)
        source = target_dir / "source.db"
        os.replace(temp_file, source)
        os.chmod(source, 0o600)
        created = _now()
        meta = {
            "id": upload_id,
            "display_name": safe_display_name(declared_name),
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "created_at": _iso(created),
            "expires_at": _iso(created + timedelta(hours=self.limits.retention_hours)),
            "state": STATE_INSPECTED,
            "structure": structure,
            "audit": None,
            "audit_error": "",
        }
        self._write_meta(upload_id, meta)
        return meta

    # ── listing / deletion ───────────────────────────────────────────────
    def list_uploads(self) -> list[dict[str, Any]]:
        self.ensure_root()
        self.purge_expired()
        items: list[dict[str, Any]] = []
        for entry in self.uploads_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                meta = self._read_meta(entry.name)
            except StagingError:
                continue
            items.append(self._public_meta(meta))
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return items

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        meta = self._read_meta(upload_id)
        return self._public_meta(meta)

    def get_meta(self, upload_id: str) -> dict[str, Any]:
        return self._read_meta(upload_id)

    def delete_upload(self, upload_id: str) -> bool:
        directory = self._dir(upload_id)
        if not directory.is_dir():
            return False
        shutil.rmtree(directory, ignore_errors=True)
        return True

    @staticmethod
    def _public_meta(meta: dict[str, Any]) -> dict[str, Any]:
        """Strip anything internal (paths never exist here in the first place)."""
        return {
            "id": meta.get("id"),
            "display_name": meta.get("display_name"),
            "size_bytes": meta.get("size_bytes"),
            "sha256": meta.get("sha256"),
            "created_at": meta.get("created_at"),
            "expires_at": meta.get("expires_at"),
            "state": meta.get("state"),
            "structure": meta.get("structure") or {},
            "audit": meta.get("audit"),
            "audit_error": meta.get("audit_error") or "",
        }

    # ── audit (delegates to the existing bot tool) ───────────────────────
    def run_audit(self, upload_id: str, audit_script: Path) -> dict[str, Any]:
        meta = self._read_meta(upload_id)
        source = self._dir(upload_id) / "source.db"
        if not source.is_file():
            raise StagingError("upload_source_missing")
        if not audit_script.is_file():
            raise StagingError("audit_tool_not_available")
        before = sha256_file(source)
        try:
            completed = subprocess.run(  # noqa: S603 - fixed script path, no shell
                [sys.executable, str(audit_script), "--database", str(source), "--json"],
                capture_output=True,
                text=True,
                timeout=AUDIT_TIMEOUT_SECONDS,
                cwd=str(audit_script.parent),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": str(audit_script.parent),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            meta["state"] = STATE_AUDIT_FAILED
            meta["audit_error"] = "audit_run_failed"
            self._write_meta(upload_id, meta)
            return meta
        after = sha256_file(source)
        unchanged = before == after
        if completed.returncode != 0:
            meta["state"] = STATE_AUDIT_FAILED
            meta["audit_error"] = "audit_tool_error"
            meta["audit"] = {
                "unchanged": unchanged,
                "checksum_before": before,
                "checksum_after": after,
            }
            self._write_meta(upload_id, meta)
            return meta
        try:
            report = json.loads(completed.stdout)
            if not isinstance(report, dict):
                raise ValueError("not an object")
        except ValueError:
            meta["state"] = STATE_AUDIT_FAILED
            meta["audit_error"] = "audit_report_unreadable"
            self._write_meta(upload_id, meta)
            return meta
        meta["state"] = STATE_AUDITED if unchanged else STATE_AUDIT_FAILED
        meta["audit_error"] = "" if unchanged else "audit_changed_the_file"
        meta["audit"] = {
            "report": report,
            "unchanged": unchanged,
            "checksum_before": before,
            "checksum_after": after,
            "ran_at": _iso(_now()),
        }
        self._write_meta(upload_id, meta)
        return meta


def default_audit_script() -> Path:
    """Locate the existing bot audit tool relative to this backend package."""
    for base in Path(__file__).resolve().parents:
        candidate = base / "bale-bot" / "nora_bot" / "legacy_data_audit.py"
        if candidate.is_file():
            return candidate
    return Path(__file__).resolve().parents[3] / "bale-bot" / "nora_bot" / "legacy_data_audit.py"
