"""Public images uploaded from the managers' panel (event posters, article covers).

Design, deliberately small:

* The browser never chooses a path or a name. The server derives everything
  from the bytes: the real type is sniffed from magic bytes *and* the image is
  decoded with Pillow, so a renamed executable, SVG or HTML file is rejected
  regardless of extension or ``Content-Type`` header.
* Bytes live in the shared database (same mechanism as ``private_files``), so
  there is no writable directory under the web root and nothing executable can
  ever be served. ``site_content`` stores only the stable URL
  ``/api/public/media/{uuid}``.
* Identical bytes map to one record (``content_hash``), so re-uploads do not
  pile up copies.
* Nothing is deleted automatically. The panel can list uploads with their
  usage inside ``site_content`` and an authorized person may delete an unused
  one explicitly; a used image cannot be deleted while any record references it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import re
from typing import Any
import uuid

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import PublicMediaRecord, SiteContentRecord

SOURCE = "shared_server_database"
MAX_BYTES = 3 * 1024 * 1024
MAX_PIXELS = 24_000_000  # 6000×4000; guards against decompression bombs
MIN_SIDE = 16
URL_PREFIX = "/api/public/media/"
ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_NAME_STRIP = re.compile(r"[^A-Za-z0-9._-]+")


class MediaError(ValueError):
    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    width: int
    height: int


def sniff(content: bytes) -> str | None:
    """Magic-byte sniffing only; never trusts a declared type."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def inspect_image(content: bytes) -> ImageInfo:
    """Reject anything that is not a decodable raster image of an allowed type."""
    if not content:
        raise MediaError("empty_image")
    if len(content) > MAX_BYTES:
        raise MediaError("image_too_large", 413)
    sniffed = sniff(content)
    if sniffed not in ALLOWED:
        raise MediaError("unsupported_image_type", 415)
    try:
        with Image.open(io.BytesIO(content)) as probe:
            fmt = (probe.format or "").upper()
            width, height = probe.size
            if width * height > MAX_PIXELS:
                raise MediaError("image_dimensions_too_large")
            probe.verify()
    except MediaError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise MediaError("invalid_image") from None
    expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[sniffed]
    if fmt != expected:
        raise MediaError("invalid_image")
    if width < MIN_SIDE or height < MIN_SIDE:
        raise MediaError("image_too_small")
    return ImageInfo(sniffed, int(width), int(height))


def safe_name(declared: str, content_type: str) -> str:
    """Display-only name: ASCII, no path separators, extension from the real type."""
    base = str(declared or "").replace("\\", "/").rsplit("/", 1)[-1]
    raw_stem = base.rsplit(".", 1)[0] if "." in base.strip(".") else base
    stem = _NAME_STRIP.sub("_", raw_stem).strip("._")[:60].strip("._") or "image"
    return f"{stem}.{ALLOWED[content_type]}"


def url_for(media_id: str) -> str:
    return URL_PREFIX + media_id


def parse_id(value: str) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if _UUID.fullmatch(candidate) else None


def serialize(record: PublicMediaRecord, *, used_in: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": record.id,
        "url": url_for(record.id),
        "content_type": record.content_type,
        "size": record.content_size,
        "width": record.width,
        "height": record.height,
        "file_name": record.file_name,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if used_in is not None:
        item["used_in"] = used_in
        item["in_use"] = used_in > 0
    return item


def store(
    db: Session,
    content: bytes,
    *,
    declared_name: str,
    actor_kind: str,
    actor_id: str,
) -> tuple[PublicMediaRecord, bool]:
    """Validate and persist; returns (record, created). Identical bytes reuse the existing row."""
    info = inspect_image(content)
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(PublicMediaRecord).where(PublicMediaRecord.content_hash == digest))
    if existing is not None:
        return existing, False
    record = PublicMediaRecord(
        id=str(uuid.uuid4()),
        content_hash=digest,
        content_type=info.content_type,
        content_size=len(content),
        width=info.width,
        height=info.height,
        file_name=safe_name(declared_name, info.content_type),
        uploaded_by_kind=actor_kind[:16],
        uploaded_by_id=actor_id[:64],
        content=content,
    )
    db.add(record)
    db.flush()
    return record, True


def usage_index(db: Session) -> dict[str, int]:
    """How many times each media URL appears in the public site document."""
    row = db.get(SiteContentRecord, "public")
    if row is None or not isinstance(row.content, dict):
        return {}
    text = json.dumps(row.content, ensure_ascii=False)
    counts: dict[str, int] = {}
    for match in re.finditer(re.escape(URL_PREFIX) + r"([0-9a-f-]{36})", text):
        counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def list_records(db: Session, *, limit: int, offset: int) -> dict[str, Any]:
    total = int(db.scalar(select(func.count()).select_from(PublicMediaRecord)) or 0)
    rows = db.scalars(
        select(PublicMediaRecord)
        .order_by(PublicMediaRecord.created_at.desc(), PublicMediaRecord.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    usage = usage_index(db)
    items = [serialize(row, used_in=usage.get(row.id, 0)) for row in rows]
    return {
        "source": SOURCE,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "unused": sum(1 for row in rows if usage.get(row.id, 0) == 0),
        "max_bytes": MAX_BYTES,
    }
