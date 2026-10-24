"""Server-side validation of external video sources (phase 9.1 §3).

A recorded session may be delivered from exactly three kinds of source:

* ``file``    – a private Nora file served by the access-checked download endpoint;
* ``youtube`` – a YouTube video rendered through the official player;
* ``aparat``  – an Aparat video rendered through Aparat's official embed frame.

For the two external kinds the organiser pastes a URL or a bare id; this module turns
it into a **validated video id** plus the **official canonical and embed URLs**.  Only
the id survives validation – never the pasted text, never HTML, never an ``<iframe>``.
Anything that is not a well-formed public URL on an allow-listed host (``javascript:``,
``data:``, IP literals, userinfo, unknown hosts, arbitrary paths) is rejected with a
stable error code, so the stored value can only ever be one of two URL shapes.

What this module deliberately does **not** do:

* It performs no outbound request.  Whether a video exists, is public, allows embedding
  or is age/region restricted is decided by the platform at playback time; the page
  shows that state honestly (loading / playing / "not embeddable" + fallback link).
* It provides no protection of the content.  An external embed is public hosting by a
  third party; the video id is visible to anyone who can watch, and the platform – not
  Nora – controls downloads.  Paid content that must stay private belongs in ``file``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

EMBED_KINDS: tuple[str, ...] = ("youtube", "aparat")

YOUTUBE_ID_RE = re.compile(r"\A[A-Za-z0-9_-]{11}\Z")
APARAT_ID_RE = re.compile(r"\A[A-Za-z0-9]{3,24}\Z")

YOUTUBE_HOSTS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be", "www.youtu.be",
})
APARAT_HOSTS = frozenset({"aparat.com", "www.aparat.com"})

# Official players only; the page's frame allow-list (and any future CSP ``frame-src``)
# must contain exactly these origins.
YOUTUBE_EMBED_ORIGIN = "https://www.youtube-nocookie.com"  # privacy-enhanced mode
YOUTUBE_WATCH_ORIGIN = "https://www.youtube.com"
APARAT_ORIGIN = "https://www.aparat.com"
FRAME_ORIGINS: tuple[str, ...] = (YOUTUBE_EMBED_ORIGIN, YOUTUBE_WATCH_ORIGIN, APARAT_ORIGIN)

MAX_INPUT_CHARS = 2048
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f\s]")


class VideoSourceError(ValueError):
    """``code`` is the stable API error code (always a 422 for the caller)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VideoSource:
    provider: str
    video_id: str

    @property
    def watch_url(self) -> str:
        if self.provider == "youtube":
            return f"{YOUTUBE_WATCH_ORIGIN}/watch?v={self.video_id}"
        return f"{APARAT_ORIGIN}/v/{self.video_id}"

    @property
    def embed_url(self) -> str:
        if self.provider == "youtube":
            # rel=0 keeps suggestions to the same channel; modestbranding is ignored by newer
            # players but harmless.  No autoplay: the page never starts playback by itself.
            return f"{YOUTUBE_EMBED_ORIGIN}/embed/{self.video_id}?rel=0&modestbranding=1&playsinline=1"
        return f"{APARAT_ORIGIN}/video/video/embed/videohash/{self.video_id}/vt/frame"

    @property
    def frame_origin(self) -> str:
        return YOUTUBE_EMBED_ORIGIN if self.provider == "youtube" else APARAT_ORIGIN

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "video_id": self.video_id,
            "watch_url": self.watch_url,
            "embed_url": self.embed_url,
            "frame_origin": self.frame_origin,
        }


def _clean(raw: Any) -> str:
    if raw is None:
        raise VideoSourceError("video_source_required")
    if not isinstance(raw, str):
        raise VideoSourceError("invalid_video_source")
    text = raw.strip()
    if not text:
        raise VideoSourceError("video_source_required")
    if "<" in text or ">" in text or '"' in text or "'" in text:
        # Pasted <iframe …> / HTML snippets are never accepted – only a URL or an id.
        raise VideoSourceError("html_not_allowed")
    if len(text) > MAX_INPUT_CHARS or _CONTROL_RE.search(text):
        raise VideoSourceError("invalid_video_source")
    return text


def _split_url(text: str) -> tuple[str, str, str] | None:
    """Return (host, path, query) for an http(s) URL on any host, else None for a bare id."""
    if "://" not in text and not text.startswith("//"):
        if ":" in text or "/" in text or "?" in text or "#" in text:
            # Looks like a URL with an unsupported scheme (javascript:, data:, ftp:, …).
            raise VideoSourceError("unsupported_video_host")
        return None
    parts = urlsplit(text if "://" in text else "https:" + text)
    if parts.scheme not in {"https", "http"}:
        raise VideoSourceError("unsupported_video_host")
    if parts.username is not None or parts.password is not None or parts.port is not None:
        raise VideoSourceError("unsupported_video_host")
    host = (parts.hostname or "").lower()
    if not host or re.fullmatch(r"[0-9.]+|\[.*\]|[0-9a-f:]+", host):
        raise VideoSourceError("unsupported_video_host")
    return host, parts.path or "/", parts.query or ""


def _youtube_id(text: str) -> str:
    split = _split_url(text)
    if split is None:
        if YOUTUBE_ID_RE.match(text):
            return text
        raise VideoSourceError("invalid_video_id")
    host, path, query = split
    if host not in YOUTUBE_HOSTS:
        raise VideoSourceError("unsupported_video_host")
    candidate = ""
    if host.endswith("youtu.be"):
        candidate = path.strip("/").split("/")[0]
    else:
        values = parse_qs(query).get("v")
        if values:
            candidate = values[0]
        else:
            match = re.match(r"^/(?:embed|shorts|live|v|e)/([^/?#]+)", path)
            candidate = match.group(1) if match else ""
    if not YOUTUBE_ID_RE.match(candidate):
        raise VideoSourceError("invalid_video_id")
    return candidate


def _aparat_id(text: str) -> str:
    split = _split_url(text)
    if split is None:
        if APARAT_ID_RE.match(text):
            return text
        raise VideoSourceError("invalid_video_id")
    host, path, _query = split
    if host not in APARAT_HOSTS:
        raise VideoSourceError("unsupported_video_host")
    match = re.match(r"^/(?:v|embed|video/video/embed/videohash)/([^/?#]+)", path)
    candidate = match.group(1) if match else ""
    if not APARAT_ID_RE.match(candidate):
        raise VideoSourceError("invalid_video_id")
    return candidate


def parse(provider: Any, raw: Any) -> VideoSource:
    """Validate ``raw`` (URL or bare id) for ``provider`` and return the canonical source."""
    kind = str(provider or "").strip().lower()
    if kind not in EMBED_KINDS:
        raise VideoSourceError("unsupported_video_provider")
    text = _clean(raw)
    video_id = _youtube_id(text) if kind == "youtube" else _aparat_id(text)
    return VideoSource(provider=kind, video_id=video_id)


def from_stored(kind: str, stored_url: str) -> VideoSource | None:
    """Rebuild the source from the canonical URL kept in ``event_resources.link_url``.

    Returns ``None`` when the stored value is not one of our own canonical shapes, so a
    tampered row can never produce an embed.
    """
    if kind not in EMBED_KINDS or not stored_url:
        return None
    try:
        source = parse(kind, stored_url)
    except VideoSourceError:
        return None
    return source if source.watch_url == stored_url else None
