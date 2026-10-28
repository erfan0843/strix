"""Phase 9.4: private file storage outside the web root, behind a small interface.

Today the only backend is a local directory (``NORA_PRIVATE_STORAGE_DIR``). Object storage / CDN
adapters are deliberately absent: there is no environment to run them against, and a connector that
cannot be exercised would only pretend. Everything a future adapter must honour is in
:class:`PrivateStorage`.

Guarantees of :class:`LocalPrivateStorage`:

* **Keys are server-made** (``YYYY/MM/<uuid4 hex>``); no user-supplied name ever becomes a path.
  :meth:`resolve` rejects anything that is not a key and anything that escapes the root.
* **Atomic writes**: bytes stream into ``<root>/.incoming/<uuid>.part`` (hashed on the way), are
  ``fsync``-ed, then ``os.replace``-d to the final key. A failed/aborted upload leaves no final file.
* **No byte in process memory beyond one chunk** on either direction; reads are chunked and support
  ranges through :meth:`open_range`.
* **The directory may not live under the static web root** (checked once at start-up).
* Deletion is explicit (callers audit it); nothing here ever deletes on its own.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol

KEY_PATTERN = re.compile(r"^\d{4}/\d{2}/[0-9a-f]{32}$")
PART_PATTERN = re.compile(r"^[0-9a-f]{32}$")
CHUNK_BYTES = 256 * 1024
INCOMING_DIR = ".incoming"


class StorageError(Exception):
    """``code`` is stable and safe to surface; ``detail`` never contains a filesystem path."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    sha256: str


@dataclass(frozen=True)
class StorageStatus:
    """Operational view for the panel / health: never leaks the physical path."""

    configured: bool
    backend: str
    max_bytes: int
    free_bytes: int | None = None
    writable: bool | None = None


class PrivateStorage(Protocol):
    max_bytes: int

    def begin(self) -> "PendingUpload": ...
    def exists(self, key: str) -> bool: ...
    def size(self, key: str) -> int | None: ...
    def open_range(self, key: str, start: int, end: int) -> Iterator[bytes]: ...
    def delete(self, key: str) -> bool: ...
    def status(self) -> StorageStatus: ...
    def list_keys(self) -> Iterator[str]: ...


class PendingUpload:
    """A staged upload: feed chunks, then ``commit`` (atomic) or ``abort`` (no trace left)."""

    def __init__(self, storage: "LocalPrivateStorage") -> None:
        self._storage = storage
        self._incoming = storage.root / INCOMING_DIR
        self._incoming.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._part = self._incoming / f"{uuid.uuid4().hex}.part"
        self._fh: BinaryIO | None = open(self._part, "xb")  # noqa: SIM115 - explicit lifecycle
        os.chmod(self._part, 0o600)
        self._hash = hashlib.sha256()
        self.size = 0
        self.head = b""

    def write(self, chunk: bytes) -> None:
        if self._fh is None:
            raise StorageError("upload_closed")
        if not chunk:
            return
        if self.size + len(chunk) > self._storage.max_bytes:
            raise StorageError("file_too_large")
        if len(self.head) < 8192:
            self.head += chunk[: 8192 - len(self.head)]
        self._fh.write(chunk)
        self._hash.update(chunk)
        self.size += len(chunk)

    def commit(self) -> StoredObject:
        if self._fh is None:
            raise StorageError("upload_closed")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._fh.close()
        self._fh = None
        key = self._storage.new_key()
        final = self._storage.resolve(key)
        final.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(self._part, final)  # atomic on the same filesystem
        try:
            dir_fd = os.open(final.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # directory fsync is best-effort (not available on every filesystem)
        return StoredObject(key=key, size=self.size, sha256=self._hash.hexdigest())

    def abort(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None
        try:
            self._part.unlink()
        except FileNotFoundError:
            pass


class LocalPrivateStorage:
    """Files under one private directory; see the module docstring for the guarantees."""

    backend = "local_disk"

    def __init__(self, root: str | os.PathLike[str], *, max_bytes: int, forbidden_parents: tuple[Path, ...] = ()) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = int(max_bytes)
        for parent in forbidden_parents:
            parent = parent.resolve()
            if self.root == parent or parent in self.root.parents:
                raise StorageError("storage_inside_webroot", "private storage must not be under the static web root")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not os.access(self.root, os.W_OK | os.X_OK):
            raise StorageError("storage_not_writable")

    # ── keys ──
    @staticmethod
    def new_key() -> str:
        now = datetime.now(timezone.utc)
        return f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}"

    def resolve(self, key: str) -> Path:
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise StorageError("invalid_storage_key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise StorageError("invalid_storage_key")
        return path

    # ── interface ──
    def begin(self) -> PendingUpload:
        return PendingUpload(self)

    def exists(self, key: str) -> bool:
        try:
            return self.resolve(key).is_file()
        except StorageError:
            return False

    def size(self, key: str) -> int | None:
        try:
            info = self.resolve(key).stat()
        except (StorageError, FileNotFoundError):
            return None
        return info.st_size if stat.S_ISREG(info.st_mode) else None

    def open_range(self, key: str, start: int, end: int) -> Iterator[bytes]:
        """Yield bytes ``[start, end]`` inclusive in bounded chunks (the caller validated the range)."""
        path = self.resolve(key)
        remaining = end - start + 1
        with open(path, "rb") as fh:
            fh.seek(start)
            while remaining > 0:
                chunk = fh.read(min(CHUNK_BYTES, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def delete(self, key: str) -> bool:
        try:
            self.resolve(key).unlink()
        except (StorageError, FileNotFoundError):
            return False
        return True

    def list_keys(self) -> Iterator[str]:
        for year in sorted(p for p in self.root.iterdir() if p.is_dir() and p.name != INCOMING_DIR):
            for month in sorted(p for p in year.iterdir() if p.is_dir()):
                for item in sorted(p for p in month.iterdir() if p.is_file()):
                    key = f"{year.name}/{month.name}/{item.name}"
                    if KEY_PATTERN.fullmatch(key):
                        yield key

    # ── resumable (phase 9.5): a ``.part`` that survives across requests ──
    def begin_part(self) -> str:
        """Create an empty staged part and return its server-made id (32 hex chars)."""
        incoming = self.root / INCOMING_DIR
        incoming.mkdir(mode=0o700, parents=True, exist_ok=True)
        part_id = uuid.uuid4().hex
        path = incoming / f"{part_id}.part"
        with open(path, "xb"):
            pass
        os.chmod(path, 0o600)
        return part_id

    def part_path(self, part_id: str) -> Path:
        if not isinstance(part_id, str) or not PART_PATTERN.fullmatch(part_id):
            raise StorageError("invalid_part_id")
        return self.root / INCOMING_DIR / f"{part_id}.part"

    def part_size(self, part_id: str) -> int | None:
        try:
            info = self.part_path(part_id).stat()
        except (StorageError, FileNotFoundError):
            return None
        return info.st_size if stat.S_ISREG(info.st_mode) else None

    def append_part(self, part_id: str, offset: int, chunks: Iterator[bytes], *, limit: int) -> tuple[int, str]:
        """Append ``chunks`` at ``offset`` (which must equal the current size — the disk is the truth).

        Returns ``(new_size, sha256_of_this_chunk)``. Never writes past ``limit``; on overflow the
        bytes written so far stay (the session is failed by the caller, which also discards the part).
        """
        path = self.part_path(part_id)
        try:
            current = path.stat().st_size
        except FileNotFoundError:
            raise StorageError("part_missing") from None
        if current != offset:
            raise StorageError("offset_mismatch", str(current))
        digest = hashlib.sha256()
        written = 0
        with open(path, "r+b") as fh:
            fh.seek(current)
            for chunk in chunks:
                if not chunk:
                    continue
                if current + written + len(chunk) > limit:
                    raise StorageError("file_too_large")
                fh.write(chunk)
                digest.update(chunk)
                written += len(chunk)
            fh.flush()
            os.fsync(fh.fileno())
        return current + written, digest.hexdigest()

    def part_head(self, part_id: str, length: int = 8192) -> bytes:
        with open(self.part_path(part_id), "rb") as fh:
            return fh.read(length)

    def part_sha256(self, part_id: str) -> str:
        digest = hashlib.sha256()
        with open(self.part_path(part_id), "rb") as fh:
            for piece in iter(lambda: fh.read(CHUNK_BYTES), b""):
                digest.update(piece)
        return digest.hexdigest()

    def commit_part(self, part_id: str, *, expected_size: int, sha256: str) -> StoredObject:
        """Atomic move of a fully received part to a fresh key (same guarantees as ``PendingUpload.commit``)."""
        path = self.part_path(part_id)
        size = self.part_size(part_id)
        if size is None:
            raise StorageError("part_missing")
        if size != expected_size:
            raise StorageError("size_mismatch", str(size))
        key = self.new_key()
        final = self.resolve(key)
        final.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(path, final)
        try:
            dir_fd = os.open(final.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
        return StoredObject(key=key, size=size, sha256=sha256)

    def discard_part(self, part_id: str) -> bool:
        try:
            self.part_path(part_id).unlink()
        except (StorageError, FileNotFoundError):
            return False
        return True

    def incoming_parts(self) -> list[tuple[str, int, float]]:
        """``(part_id, size, mtime)`` for every staged part — for the health view (never deleted here)."""
        incoming = self.root / INCOMING_DIR
        if not incoming.is_dir():
            return []
        found: list[tuple[str, int, float]] = []
        for item in sorted(incoming.iterdir()):
            if item.suffix != ".part" or not PART_PATTERN.fullmatch(item.stem):
                continue
            try:
                info = item.stat()
            except FileNotFoundError:
                continue
            found.append((item.stem, info.st_size, info.st_mtime))
        return found

    def stale_parts(self, *, older_than_seconds: int) -> list[Path]:
        """Leftover ``.part`` files (crashed uploads); listed only — removal is an operator decision."""
        incoming = self.root / INCOMING_DIR
        if not incoming.is_dir():
            return []
        cutoff = datetime.now(timezone.utc).timestamp() - older_than_seconds
        return [p for p in incoming.iterdir() if p.suffix == ".part" and p.stat().st_mtime < cutoff]

    def status(self) -> StorageStatus:
        try:
            usage = os.statvfs(self.root)
            free = usage.f_bavail * usage.f_frsize
        except OSError:
            free = None
        return StorageStatus(
            configured=True, backend=self.backend, max_bytes=self.max_bytes, free_bytes=free,
            writable=os.access(self.root, os.W_OK | os.X_OK),
        )


def unconfigured_status(*, inline_max_bytes: int) -> StorageStatus:
    return StorageStatus(configured=False, backend="database", max_bytes=inline_max_bytes)


__all__ = [
    "CHUNK_BYTES",
    "KEY_PATTERN",
    "PART_PATTERN",
    "LocalPrivateStorage",
    "PendingUpload",
    "PrivateStorage",
    "StorageError",
    "StorageStatus",
    "StoredObject",
    "unconfigured_status",
]
