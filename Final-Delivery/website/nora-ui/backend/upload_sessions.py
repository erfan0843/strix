"""Phase 9.5 §5.2 — limited, internal resumable upload protocol for event file resources.

Why not tus: a tus server would add a dependency and a second body-handling path that cannot be
exercised behind the real proxy here. This protocol is deliberately small, runs on the existing
``LocalPrivateStorage`` and the existing admin auth (session cookie + CSRF + same-origin + role),
and every rule below is covered by real HTTP tests. The single-request ``PUT …/file`` stays.

Protocol (all under ``/api/admin/events/{event}/resources/{resource}/upload-sessions``):

1. ``POST`` ``{"size", "sha256"?, "file_name"}`` → ``201`` session (``id``, ``offset`` 0, ``chunk_bytes``,
   ``expires_at``). An actor's own still-open session for the same resource is returned instead
   (``200``, ``resumed: true``) so a reload resumes rather than starting over.
2. ``GET /{id}`` → current ``offset`` (disk size, cross-checked with the row) — the resume point.
3. ``PATCH /{id}`` raw body, headers ``Upload-Offset`` (must equal the current offset) and
   ``Upload-Checksum: sha256 <hex>`` of this body. Out-of-order, duplicate or stale offsets → ``409``
   with the real offset; body larger than ``MAX_CHUNK_BYTES`` → ``413``; checksum mismatch → the
   bytes are truncated away again and ``400``. Chunks are appended with ``fsync``.
4. ``POST /{id}/complete`` ``{"sha256"?}`` → size must equal ``expected_size``, a whole-file sha256 is
   mandatory (from step 1 or here), the first bytes are sniffed like the single-request path, then
   the part is moved atomically under a fresh key and the resource row switches to it. A second
   caller meets ``409 upload_completing`` / ``410`` — never two finals.
5. ``DELETE /{id}`` aborts and removes the part.

Limits (documented, enforced): expected size ≤ storage cap, chunk ≤ 8 MiB (advertised 4 MiB —
below the proxy body cap in ``deployment/Caddyfile``), ≤ 4096 chunks per session, session TTL
24 h; expired sessions are closed and their parts removed on the next session start or by the
maintenance CLI, never a committed file.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import storage as storage_mod
from .models import EventResourceRecord, UploadSessionRecord

SESSION_TTL = timedelta(hours=24)
CHUNK_BYTES = 4 * 1024 * 1024
MAX_CHUNK_BYTES = 8 * 1024 * 1024
MAX_CHUNKS = 4096
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CHECKSUM_HEADER = re.compile(r"^sha256\s+([0-9a-fA-F]{64})$")


class UploadSessionError(Exception):
    def __init__(self, code: str, status: int = 409, **extra: Any) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def iso(value: datetime | None) -> str | None:
    value = _utc(value)
    return value.isoformat() if value else None


def normalize_sha256(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str) or not SHA256_PATTERN.fullmatch(raw.lower()):
        raise UploadSessionError("invalid_sha256", 422)
    return raw.lower()


def parse_checksum_header(raw: str | None) -> str:
    match = CHECKSUM_HEADER.match((raw or "").strip())
    if not match:
        raise UploadSessionError("chunk_checksum_required", 400)
    return match.group(1).lower()


def view(session: UploadSessionRecord, *, offset: int | None = None, resumed: bool = False) -> dict[str, Any]:
    return {
        "id": session.id,
        "resource_id": session.resource_id,
        "status": session.status,
        "offset": session.received_bytes if offset is None else offset,
        "expected_size": session.expected_size,
        "chunk_bytes": CHUNK_BYTES,
        "max_chunk_bytes": MAX_CHUNK_BYTES,
        "chunk_count": session.chunk_count,
        "expires_at": iso(session.expires_at),
        "resumed": resumed,
        "error_code": session.error_code or "",
        "storage_key_set": bool(session.storage_key),
    }


def expire_stale(db: Session, store: storage_mod.LocalPrivateStorage | None, now: datetime) -> int:
    """Close open/completing sessions past their TTL and drop their parts. Committed files are never touched."""
    rows = db.scalars(
        select(UploadSessionRecord).where(
            UploadSessionRecord.status.in_(("open", "completing")), UploadSessionRecord.expires_at <= now,
        )
    ).all()
    for row in rows:
        row.status = "expired"
        row.error_code = "expired"
        row.updated_at = now
        if store is not None:
            store.discard_part(row.part_id)
    if rows:
        db.flush()
    return len(rows)


def start(
    db: Session, store: storage_mod.LocalPrivateStorage, *, record: EventResourceRecord, event_id: str,
    actor: tuple[str, str], size: Any, sha256: Any, file_name: str, now: datetime,
) -> tuple[UploadSessionRecord, bool]:
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise UploadSessionError("invalid_size", 422)
    if size > store.max_bytes:
        raise UploadSessionError("file_too_large", 413, max_bytes=store.max_bytes)
    digest = normalize_sha256(sha256)
    existing = db.scalar(
        select(UploadSessionRecord).where(
            UploadSessionRecord.resource_id == record.id, UploadSessionRecord.status == "open",
        ).order_by(UploadSessionRecord.created_at.desc())
    )
    if existing is not None:
        if (existing.owner_kind, existing.owner_id) != actor:
            raise UploadSessionError("upload_session_open_by_other", 409)
        if existing.expected_size == size and (digest is None or existing.expected_sha256 in (None, digest)):
            if digest and not existing.expected_sha256:
                existing.expected_sha256 = digest
            on_disk = store.part_size(existing.part_id)
            if on_disk is not None and on_disk == existing.received_bytes:
                return existing, True
        # A different file (or a part the disk lost): close the old session, start fresh.
        existing.status = "aborted"
        existing.error_code = "superseded"
        existing.updated_at = now
        store.discard_part(existing.part_id)
    session = UploadSessionRecord(
        id=str(uuid.uuid4()), resource_id=record.id, event_id=event_id, owner_kind=actor[0], owner_id=actor[1],
        part_id=store.begin_part(), declared_name=file_name[:160], expected_size=size, expected_sha256=digest,
        received_bytes=0, chunk_count=0, status="open", expires_at=now + SESSION_TTL,
    )
    db.add(session)
    db.flush()
    return session, False


def load_open(
    db: Session, store: storage_mod.LocalPrivateStorage, *, session_id: str, record: EventResourceRecord,
    actor: tuple[str, str], now: datetime, for_update: bool = False,
) -> UploadSessionRecord:
    query = select(UploadSessionRecord).where(UploadSessionRecord.id == session_id, UploadSessionRecord.resource_id == record.id)
    if for_update:
        query = query.with_for_update()
    session = db.scalar(query)
    if session is None or (session.owner_kind, session.owner_id) != actor:
        raise UploadSessionError("upload_session_not_found", 404)
    if session.status in ("open", "completing") and _utc(session.expires_at) <= now:  # type: ignore[operator]
        session.status = "expired"
        session.error_code = "expired"
        session.updated_at = now
        store.discard_part(session.part_id)
        db.flush()
    return session


def current_offset(store: storage_mod.LocalPrivateStorage, session: UploadSessionRecord) -> int:
    """Disk is the truth; a row/disk disagreement fails the session instead of guessing."""
    on_disk = store.part_size(session.part_id)
    if on_disk is None:
        raise UploadSessionError("upload_session_lost", 410)
    if on_disk != session.received_bytes:
        raise UploadSessionError("upload_session_inconsistent", 410, offset_on_disk=on_disk, offset_recorded=session.received_bytes)
    return on_disk


def append(
    store: storage_mod.LocalPrivateStorage, session: UploadSessionRecord, *, offset: int, body: bytes,
    checksum: str, now: datetime,
) -> int:
    if session.status != "open":
        raise UploadSessionError("upload_session_" + session.status, 410 if session.status in ("expired", "aborted", "failed") else 409)
    if not body:
        raise UploadSessionError("empty_chunk", 400)
    if len(body) > MAX_CHUNK_BYTES:
        raise UploadSessionError("chunk_too_large", 413, max_chunk_bytes=MAX_CHUNK_BYTES)
    on_disk = current_offset(store, session)
    if offset != on_disk:
        raise UploadSessionError("offset_mismatch", 409, offset=on_disk)
    if on_disk + len(body) > session.expected_size:
        raise UploadSessionError("chunk_exceeds_expected_size", 413, offset=on_disk, expected_size=session.expected_size)
    if session.chunk_count + 1 > MAX_CHUNKS:
        raise UploadSessionError("too_many_chunks", 413, max_chunks=MAX_CHUNKS)
    if hashlib.sha256(body).hexdigest() != checksum:
        raise UploadSessionError("chunk_checksum_mismatch", 400, offset=on_disk)
    new_size, _digest = store.append_part(session.part_id, on_disk, iter((body,)), limit=min(session.expected_size, store.max_bytes))
    session.received_bytes = new_size
    session.chunk_count += 1
    session.updated_at = now
    return new_size


def begin_complete(
    store: storage_mod.LocalPrivateStorage, session: UploadSessionRecord, *, sha256: Any, now: datetime,
) -> str:
    """Validate and lock the session (``completing``); returns the sha256 the file must match."""
    if session.status == "completing":
        raise UploadSessionError("upload_completing", 409)
    if session.status != "open":
        raise UploadSessionError("upload_session_" + session.status, 410)
    digest = normalize_sha256(sha256) or session.expected_sha256
    if not digest:
        raise UploadSessionError("sha256_required", 422)
    if session.expected_sha256 and digest != session.expected_sha256:
        raise UploadSessionError("sha256_conflict", 422)
    on_disk = current_offset(store, session)
    if on_disk != session.expected_size:
        raise UploadSessionError("upload_incomplete", 409, offset=on_disk, expected_size=session.expected_size)
    session.expected_sha256 = digest
    session.status = "completing"
    session.updated_at = now
    return digest


def fail(store: storage_mod.LocalPrivateStorage, session: UploadSessionRecord, *, code: str, now: datetime) -> None:
    session.status = "failed"
    session.error_code = code[:40]
    session.updated_at = now
    store.discard_part(session.part_id)


__all__ = [
    "CHUNK_BYTES",
    "MAX_CHUNKS",
    "MAX_CHUNK_BYTES",
    "SESSION_TTL",
    "UploadSessionError",
    "append",
    "begin_complete",
    "current_offset",
    "expire_stale",
    "fail",
    "load_open",
    "normalize_sha256",
    "parse_checksum_header",
    "start",
    "view",
]
