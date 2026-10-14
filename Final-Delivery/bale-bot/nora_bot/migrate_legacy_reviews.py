"""Safely move pending legacy profile/receipt reviews into the shared API.

Default mode is a read-only dry run. Applying changes requires both --apply
and --yes, a current backup, and an authenticated server-side owner identity.
No workflow is approved or rejected by this command.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\Z")
_PROFILE_KEY = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_META_TABLE = "nora_legacy_migration_meta"
_MAX_PRIVATE_FILE = 8 * 1024 * 1024
_MAX_WORKFLOW_BYTES = 24 * 1024


class MigrationError(RuntimeError):
    """A safe, non-PII error suitable for the CLI summary."""


@dataclass(frozen=True)
class Candidate:
    kind: str
    row_id: int
    bale_user_id: str
    payload: dict[str, Any]
    attachment_path: Path | None = None
    attachment_file_id: str | None = None
    issue: str | None = None

    @property
    def ready(self) -> bool:
        return self.issue is None


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not re.fullmatch(r"[A-Za-z0-9_]+", table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _value(row: sqlite3.Row, key: str, default=None):
    return row[key] if key in row.keys() else default


def _valid_user_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    raw = str(value or "")
    return raw if _USER_ID.fullmatch(raw) else None


def _resolve_attachment_path(
    raw_path: Any,
    *,
    database_path: Path,
    allowed_roots: tuple[Path, ...],
) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, None
    roots = []
    for root in allowed_roots:
        try:
            roots.append(root.resolve())
        except (OSError, RuntimeError):
            continue
    if not roots:
        return None, "local_attachment_roots_not_configured"
    raw = Path(raw_path.strip())
    candidates = [raw] if raw.is_absolute() else [
        database_path.parent / raw,
        Path.cwd() / raw,
    ]
    found_outside_root = False
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if not resolved.is_file():
            continue
        if not any(resolved.is_relative_to(root) for root in roots):
            found_outside_root = True
            continue
        try:
            size = resolved.stat().st_size
        except OSError:
            return None, "local_attachment_unreadable"
        if size < 1 or size > _MAX_PRIVATE_FILE:
            return None, "local_attachment_size_invalid"
        return resolved, None
    if found_outside_root:
        return None, "local_attachment_outside_allowed_roots"
    return None, "local_attachment_missing"


def _profile_photo_path(
    conn: sqlite3.Connection,
    *,
    user_id: Any,
    bale_user_id: str,
    data: dict[str, Any],
    database_path: Path,
    allowed_roots: tuple[Path, ...],
) -> tuple[Path | None, str | None, str | None]:
    raw_path = data.pop("profile_photo", None)
    remote_id = data.pop("profile_photo_file_id", None)
    if raw_path in (None, "") and "users" in _tables(conn):
        user_columns = _columns(conn, "users")
        if "profile_photo" in user_columns:
            user = None
            if "bale_user_id" in user_columns:
                user = conn.execute(
                    "SELECT profile_photo FROM users WHERE bale_user_id=? LIMIT 1",
                    (bale_user_id,),
                ).fetchone()
            if user is None and user_id is not None and "id" in user_columns:
                user = conn.execute(
                    "SELECT profile_photo FROM users WHERE id=? LIMIT 1", (user_id,)
                ).fetchone()
            if user:
                raw_path = user[0]
    path, issue = _resolve_attachment_path(
        raw_path, database_path=database_path, allowed_roots=allowed_roots
    )
    if issue and remote_id:
        if not isinstance(remote_id, str):
            return None, "profile_attachment_reference_invalid", None
        return None, None, remote_id
    if issue:
        return None, issue, None
    if remote_id not in (None, "") and not isinstance(remote_id, str):
        return None, "profile_attachment_reference_invalid", None
    return path, None, remote_id


def _profile_candidate(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    owner_bale_user_id: str | None,
    database_path: Path,
    allowed_roots: tuple[Path, ...],
) -> Candidate:
    row_id = int(row["id"])
    user_id = _value(row, "user_id")
    bale_user_id = _valid_user_id(_value(row, "bale_user_id"))
    if "users" in _tables(conn) and user_id is not None:
        users_columns = _columns(conn, "users")
        if "bale_user_id" in users_columns:
            user = conn.execute(
                "SELECT bale_user_id FROM users WHERE id=?", (user_id,)
            ).fetchone()
            mapped_user_id = _valid_user_id(user[0] if user else None)
            if mapped_user_id and bale_user_id and mapped_user_id != bale_user_id:
                return Candidate("profile_review", row_id, "", {}, issue="profile_user_mapping_conflict")
            if mapped_user_id:
                bale_user_id = mapped_user_id
    if bale_user_id is None:
        return Candidate("profile_review", row_id, "", {}, issue="profile_user_id_invalid")
    if owner_bale_user_id and bale_user_id == owner_bale_user_id:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="owner_profile_skipped")
    try:
        payload = json.loads(_value(row, "profile_data") or "{}")
    except (TypeError, ValueError):
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_json_invalid")
    if not isinstance(payload, dict) or not payload:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_data_empty")

    user_id = _value(row, "user_id")
    photo_path, photo_issue, photo_file_id = _profile_photo_path(
        conn,
        user_id=user_id,
        bale_user_id=bale_user_id,
        data=payload,
        database_path=database_path,
        allowed_roots=allowed_roots,
    )
    if not payload:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_data_empty")
    for key, value in payload.items():
        if (not isinstance(key, str) or not _PROFILE_KEY.fullmatch(key)
                or key.startswith("_legacy_") or key in {"file_refs", "file_id", "photo_file_id"}
                or key.endswith("_file_id")
                or re.search(r"token|secret|authorization|api[_-]?key|password|credential", key, re.I)
                or not (value is None or isinstance(value, (str, int, float, bool)) )):
            return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_field_invalid")
        if isinstance(value, str) and len(value) > 2000:
            return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_field_too_large")
        if isinstance(value, float) and not math.isfinite(value):
            return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_field_invalid")
    if photo_issue:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue=photo_issue)
    if photo_file_id:
        if not photo_file_id.strip() or len(photo_file_id) > 512:
            return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_attachment_reference_invalid")
        photo_file_id = photo_file_id.strip()
    created_at = _value(row, "created_at")
    if created_at:
        payload["_legacy_created_at"] = str(created_at)[:80]
    if len(payload) + 2 + int(bool(photo_path or photo_file_id)) > 64:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_field_count_too_large")
    if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > _MAX_WORKFLOW_BYTES:
        return Candidate("profile_review", row_id, bale_user_id, {}, issue="profile_payload_too_large")
    return Candidate(
        "profile_review", row_id, bale_user_id, payload,
        attachment_path=photo_path, attachment_file_id=photo_file_id,
    )


def _receipt_candidate(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    database_path: Path,
    allowed_roots: tuple[Path, ...],
) -> Candidate:
    row_id = int(row["id"])
    bale_user_id = _valid_user_id(_value(row, "bale_user_id"))
    if bale_user_id is None:
        return Candidate("receipt_review", row_id, "", {}, issue="receipt_user_id_invalid")
    amount = _value(row, "amount")
    if isinstance(amount, bool):
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_amount_invalid")
    if isinstance(amount, float) and not amount.is_integer():
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_amount_invalid")
    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError):
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_amount_invalid")
    if amount < 0:
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_amount_invalid")

    payload: dict[str, Any] = {"amount": amount, "currency": "IRR"}
    field_map = {
        "event_id": "event_id",
        "registration_id": "registration_id",
        "form_response_id": "form_response_id",
        "transaction_id": "transaction_id",
        "ref_code": "ref_code",
    }
    for source_key, target_key in field_map.items():
        value = _value(row, source_key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_field_invalid")
            payload[target_key] = str(value) if source_key == "ref_code" else value

    event_id = _value(row, "event_id")
    if event_id is not None and "events" in _tables(conn) and "title" in _columns(conn, "events"):
        event = conn.execute("SELECT title FROM events WHERE id=?", (event_id,)).fetchone()
        if event and event[0]:
            payload["event_title"] = str(event[0])[:300]
    if "event_title" not in payload:
        payload["event_title"] = "رسید قدیمی"
    created_at = _value(row, "created_at")
    if created_at:
        payload["submitted_at"] = str(created_at)[:80]

    raw_path = _value(row, "photo_path")
    path, path_issue = _resolve_attachment_path(
        raw_path, database_path=database_path, allowed_roots=allowed_roots
    )
    remote_id = _value(row, "photo_file_id")
    if path_issue and remote_id:
        path = None
        path_issue = None
    if path_issue:
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue=path_issue)
    if path is None and isinstance(remote_id, str) and remote_id.strip() and len(remote_id) <= 512:
        remote_id = remote_id.strip()
    else:
        remote_id = None
    if path is None and remote_id is None:
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_attachment_missing")
    if len(payload) + 3 > 64:
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_field_count_too_large")
    if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > _MAX_WORKFLOW_BYTES:
        return Candidate("receipt_review", row_id, bale_user_id, {}, issue="receipt_payload_too_large")
    return Candidate(
        "receipt_review", row_id, bale_user_id, payload,
        attachment_path=path, attachment_file_id=remote_id,
    )


def _scan_candidates(
    conn: sqlite3.Connection,
    *,
    database_path: Path,
    owner_bale_user_id: str | None,
    allowed_roots: tuple[Path, ...],
    kinds: set[str],
) -> tuple[list[Candidate], dict[str, int]]:
    tables = _tables(conn)
    candidates: list[Candidate] = []
    totals = {"profile_review": 0, "receipt_review": 0, "already_linked": 0}
    targets = {
        "profile_review": "profile_submissions",
        "receipt_review": "payment_receipts",
    }
    for kind, table in targets.items():
        if kind not in kinds or table not in tables:
            continue
        columns = _columns(conn, table)
        if not {"id", "status", "bale_user_id"} <= columns:
            continue
        for row in conn.execute(f'SELECT * FROM "{table}" WHERE status=? ORDER BY id', ("pending",)):
            totals[kind] += 1
            if _value(row, "shared_task_id"):
                totals["already_linked"] += 1
                continue
            if kind == "profile_review":
                candidate = _profile_candidate(
                    conn,
                    row,
                    owner_bale_user_id=owner_bale_user_id,
                    database_path=database_path,
                    allowed_roots=allowed_roots,
                )
            else:
                candidate = _receipt_candidate(
                    conn, row, database_path=database_path, allowed_roots=allowed_roots
                )
            candidates.append(candidate)
    return candidates, totals


def _source_id(conn: sqlite3.Connection, *, create: bool) -> str | None:
    if create:
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{_META_TABLE}" '
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
    if _META_TABLE not in _tables(conn):
        return None
    row = conn.execute(
        f'SELECT value FROM "{_META_TABLE}" WHERE key=?', ("source_id",)
    ).fetchone()
    if row:
        value = str(row[0])
        if not _UUID.fullmatch(value):
            raise MigrationError("migration_source_id_invalid")
        return value
    if not create:
        return None
    value = str(uuid.uuid4())
    conn.execute(
        f'INSERT INTO "{_META_TABLE}" (key,value) VALUES (?,?)', ("source_id", value)
    )
    conn.commit()
    return value


def _ensure_apply_schema(conn: sqlite3.Connection, kinds: set[str]) -> None:
    tables = _tables(conn)
    expected = {
        "profile_review": "profile_submissions",
        "receipt_review": "payment_receipts",
    }
    if not any(kind in kinds and table in tables for kind, table in expected.items()):
        raise MigrationError("legacy_review_tables_not_found")
    required_columns = {
        "profile_review": {"id", "status", "bale_user_id", "profile_data"},
        "receipt_review": {"id", "status", "bale_user_id", "amount"},
    }
    for kind, table in expected.items():
        if kind not in kinds or table not in tables:
            continue
        columns = _columns(conn, table)
        missing = required_columns[kind] - columns
        if missing:
            raise MigrationError("legacy_review_schema_invalid")
    if ("receipt_review" in kinds and "payment_receipts" in tables
            and not ({"photo_path", "photo_file_id"} & _columns(conn, "payment_receipts"))):
        raise MigrationError("legacy_review_schema_invalid")
    for kind, table in (
        ("profile_review", "profile_submissions"),
        ("receipt_review", "payment_receipts"),
    ):
        if kind not in kinds or table not in tables:
            continue
        if "shared_task_id" not in _columns(conn, table):
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN shared_task_id TEXT')
    if "profile_review" in kinds and "profile_submissions" in tables:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_subs_shared_task "
            "ON profile_submissions(shared_task_id) WHERE shared_task_id IS NOT NULL"
        )
    if "receipt_review" in kinds and "payment_receipts" in tables:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_rcp_shared_task "
            "ON payment_receipts(shared_task_id) WHERE shared_task_id IS NOT NULL"
        )
    _source_id(conn, create=True)
    conn.commit()


def _backup_database(database_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    source = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
    destination = None
    target = None
    try:
        for _ in range(5):
            suffix = f"-{uuid.uuid4().hex[:8]}" if destination else ""
            candidate = backup_dir / f"nora-legacy-before-review-{stamp}{suffix}.sqlite"
            try:
                fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                destination = candidate
                continue
            os.close(fd)
            destination = candidate
            break
        else:
            raise MigrationError("backup_name_unavailable")
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
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        source.close()


def _migration_filename(candidate: Candidate, content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        extension = ".jpg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = ".png"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        extension = ".webp"
    elif content.startswith(b"%PDF-"):
        extension = ".pdf"
    else:
        extension = ".bin"
    prefix = "profile" if candidate.kind == "profile_review" else "receipt"
    return f"{prefix}-{candidate.row_id}{extension}"


def _read_attachment(
    candidate: Candidate,
    *,
    file_loader: Callable[[str], tuple[bytes, str]] | None,
) -> tuple[bytes, str] | None:
    if candidate.attachment_path is not None:
        try:
            content = candidate.attachment_path.read_bytes()
        except OSError:
            raise MigrationError("local_attachment_unreadable") from None
        if not content or len(content) > _MAX_PRIVATE_FILE:
            raise MigrationError("local_attachment_size_invalid")
        return content, _migration_filename(candidate, content)
    if candidate.attachment_file_id:
        if file_loader is None:
            from bale_api import download_file, get_file_info

            def file_loader(file_id: str) -> tuple[bytes, str]:
                info = get_file_info(file_id)
                if not info.get("ok"):
                    raise MigrationError("bale_attachment_unavailable")
                remote_path = (info.get("result") or {}).get("file_path")
                if not remote_path:
                    raise MigrationError("bale_attachment_unavailable")
                content = download_file(remote_path)
                if not content:
                    raise MigrationError("bale_attachment_unavailable")
                return content, Path(remote_path).name or "receipt.jpg"
        try:
            content, _name = file_loader(candidate.attachment_file_id)
        except MigrationError:
            raise
        except Exception:
            raise MigrationError("bale_attachment_unavailable") from None
        if not isinstance(content, bytes) or not content or len(content) > _MAX_PRIVATE_FILE:
            raise MigrationError("bale_attachment_size_invalid")
        return content, _migration_filename(candidate, content)
    return None


def _preflight_owner(api_client=None, owner_bale_user_id: str | None = None) -> None:
    if not owner_bale_user_id or not _USER_ID.fullmatch(owner_bale_user_id):
        raise MigrationError("owner_bale_user_id_required")
    if api_client is not None:
        return
    import shared_api

    shared_api._api_base()
    identity = shared_api.get_identity(owner_bale_user_id)
    if identity.role != "owner":
        raise MigrationError("server_owner_identity_required")


def run_migration(
    database_path: str | Path,
    *,
    apply: bool = False,
    owner_bale_user_id: str | int | None = None,
    kinds: set[str] | None = None,
    allowed_roots: tuple[str | Path, ...] = (),
    backup_dir: str | Path | None = None,
    api_client=None,
    file_loader: Callable[[str], tuple[bytes, str]] | None = None,
) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise MigrationError("database_file_not_found")
    selected = kinds or {"profile_review", "receipt_review"}
    if not selected or selected - {"profile_review", "receipt_review"}:
        raise MigrationError("invalid_migration_kind")
    owner_id = _valid_user_id(owner_bale_user_id)
    roots = [Path(root).expanduser() for root in allowed_roots]
    try:
        import config

        roots.extend([Path(config.FILES_DIR), Path(config.PROFILES_DIR)])
    except Exception:
        pass
    normalized_roots = tuple(roots)

    backup_path = None
    if apply:
        _preflight_owner(api_client, owner_id)
        backup_root = Path(backup_dir).expanduser() if backup_dir else path.parent / "migration-backups"
        backup_path = _backup_database(path, backup_root)
        conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)
    else:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if apply:
            _ensure_apply_schema(conn, selected)
        source_id = _source_id(conn, create=False)
        candidates, totals = _scan_candidates(
            conn,
            database_path=path,
            owner_bale_user_id=owner_id,
            allowed_roots=normalized_roots,
            kinds=selected,
        )
        summary: dict[str, Any] = {
            "mode": "apply" if apply else "dry-run",
            "pending_profiles": totals["profile_review"],
            "pending_receipts": totals["receipt_review"],
            "already_linked": totals["already_linked"],
            "ready": sum(item.ready for item in candidates),
            "skipped": sum(not item.ready for item in candidates),
            "issues": {},
            "migrated": 0,
            "failed": 0,
            "backup": backup_path.name if backup_path else None,
        }
        for candidate in candidates:
            if not candidate.ready:
                summary["issues"][candidate.issue] = summary["issues"].get(candidate.issue, 0) + 1
        if not apply:
            # Before server-side owner authorization, reveal neither per-kind
            # counts nor record/issue details. This remains a read-only audit.
            return {
                "mode": "dry-run",
                "pending_legacy_found": bool(candidates),
                "details_withheld": bool(candidates),
                "server_owner_authorization_required": bool(candidates),
                "migrated": 0,
                "failed": 0,
                "backup": None,
            }
        if api_client is None:
            import shared_api as api_client
        if not source_id:
            raise MigrationError("migration_source_id_unavailable")

        for candidate in candidates:
            if not candidate.ready:
                continue
            table = "profile_submissions" if candidate.kind == "profile_review" else "payment_receipts"
            short_kind = "profile" if candidate.kind == "profile_review" else "receipt"
            payload = dict(candidate.payload)
            payload["_legacy_source_id"] = source_id
            if candidate.kind == "profile_review":
                payload["_legacy_profile_submission_id"] = candidate.row_id
            else:
                payload["_legacy_receipt_id"] = candidate.row_id
            idempotency_key = f"legacy:{short_kind}:{source_id}:{candidate.row_id}"
            try:
                encoded_payload = json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                attachment_reserve = 64 if candidate.attachment_path or candidate.attachment_file_id else 0
                if (len(payload) + int(bool(attachment_reserve)) > 64
                        or len(encoded_payload) + attachment_reserve > _MAX_WORKFLOW_BYTES):
                    raise MigrationError("workflow_payload_too_large")
                attachment = _read_attachment(candidate, file_loader=file_loader)
                if attachment:
                    content, filename = attachment
                    file_id = api_client.upload_private_file(
                        candidate.bale_user_id,
                        content,
                        filename,
                        f"legacy-file:{short_kind}:{source_id}:{candidate.row_id}",
                    )
                    payload["file_refs"] = [file_id]
                result = api_client.submit_workflow(
                    candidate.bale_user_id,
                    candidate.kind,
                    payload,
                    idempotency_key,
                )
                task = result.get("task") if isinstance(result, dict) else None
                task_id = task.get("id") if isinstance(task, dict) else None
                if not isinstance(task_id, str) or not _UUID.fullmatch(task_id):
                    raise MigrationError("shared_workflow_id_missing")
                conn.execute(
                    f'UPDATE "{table}" SET shared_task_id=? '
                    "WHERE id=? AND status='pending' AND COALESCE(shared_task_id,'')=''",
                    (task_id, candidate.row_id),
                )
                linked = conn.execute(
                    f'SELECT shared_task_id FROM "{table}" WHERE id=?', (candidate.row_id,)
                ).fetchone()
                if not linked or linked[0] != task_id:
                    raise MigrationError("legacy_link_write_failed")
                conn.commit()
                summary["migrated"] += 1
            except Exception as exc:
                conn.rollback()
                code = getattr(exc, "code", None)
                issue = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,80}", code) else str(exc) if isinstance(exc, MigrationError) else "migration_item_failed"
                summary["issues"][issue] = summary["issues"].get(issue, 0) + 1
                summary["failed"] += 1
        return summary
    finally:
        conn.close()


def _default_roots(extra: list[str]) -> tuple[Path, ...]:
    roots = [Path(item) for item in extra]
    try:
        import config

        roots.extend([Path(config.FILES_DIR), Path(config.PROFILES_DIR)])
    except Exception:
        pass
    return tuple(roots)


def _print_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    print("گزارش مهاجرت صف قدیمی (بدون تصمیم‌گیری)")
    print(f"حالت: {summary['mode']}")
    if summary["mode"] == "dry-run":
        if summary["pending_legacy_found"]:
            print("هشدار: درخواست قدیمیِ pending شناسایی شد؛ تعداد و جزئیات تا تأیید مجوز سروری پنهان است.")
        else:
            print("در صف‌های بررسی‌شده درخواست pending انتقال‌نیافته‌ای یافت نشد.")
        print("هیچ رکورد، فایل یا سرویس خارجی تغییر نکرد.")
        return
    print(f"پروفایل‌های در انتظار: {summary['pending_profiles']}")
    print(f"فیش‌های در انتظار: {summary['pending_receipts']}")
    print(f"از قبل متصل به کارتابل: {summary['already_linked']}")
    print(f"آماده: {summary['ready']} · نیازمند بررسی: {summary['skipped']}")
    if summary["backup"]:
        print(f"پشتیبان: {summary['backup']}")
    print(f"منتقل‌شده: {summary['migrated']} · ناموفق: {summary['failed']}")
    if summary["issues"]:
        print("موارد نیازمند رسیدگی:")
        for code, count in sorted(summary["issues"].items()):
            print(f"  • {code}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="بازبینی یا انتقال کنترل‌شدهٔ صف‌های قدیمی؛ پیش‌فرض فقط‌خواندنی است."
    )
    parser.add_argument("--database", required=True, help="مسیر فایل SQLite قدیمی")
    parser.add_argument("--owner-id", help="شناسهٔ بلهٔ مالک برای حذف پروفایل مالک از انتقال")
    parser.add_argument("--kind", choices=("all", "profile", "receipt"), default="all")
    parser.add_argument("--attachment-root", action="append", default=[], help="ریشهٔ مجاز فایل پیوست؛ قابل تکرار")
    parser.add_argument("--backup-dir", help="مسیر پشتیبان خصوصی برای حالت --apply")
    parser.add_argument("--apply", action="store_true", help="ثبت درخواست‌ها در API و اتصال به رکورد SQLite")
    parser.add_argument("--yes", action="store_true", help="تأیید صریح برای --apply")
    parser.add_argument("--json", action="store_true", help="خروجی خلاصهٔ JSON بدون دادهٔ شخصی")
    args = parser.parse_args(argv)
    if args.yes and not args.apply:
        parser.error("--yes فقط همراه --apply مجاز است")
    if args.apply and not args.yes:
        parser.error("برای هر تغییری، هم --apply و هم --yes لازم است")
    try:
        import config

        configured_owner_id = str(config.SUPER_ADMIN_ID) if config.SUPER_ADMIN_ID else None
    except Exception:
        configured_owner_id = os.getenv("SUPER_ADMIN_ID")
    owner_id = args.owner_id or configured_owner_id
    kinds = {"profile_review", "receipt_review"}
    if args.kind == "profile":
        kinds = {"profile_review"}
    elif args.kind == "receipt":
        kinds = {"receipt_review"}
    try:
        summary = run_migration(
            args.database,
            apply=args.apply,
            owner_bale_user_id=owner_id,
            kinds=kinds,
            allowed_roots=_default_roots(args.attachment_root),
            backup_dir=args.backup_dir,
        )
    except Exception as exc:
        code = getattr(exc, "code", None)
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,80}", code):
            code = str(exc) if isinstance(exc, MigrationError) else "migration_preflight_or_io_error"
        print(f"❌ مهاجرت انجام نشد: {code}")
        return 2
    _print_summary(summary, as_json=args.json)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
