"""Stateless image captcha for the phone login form.

The server issues a signed token (expiry + random nonce) and a rasterised PNG
image (base64 data URI) of a random 4-digit code. The code is never stored or
sent in clear text: the token carries only an HMAC over (nonce, expiry, code)
keyed with the OTP pepper, and the digits exist only as pixels, never as text or
markup the client could read back. Verification recomputes the HMAC for the
submitted answer. No database table is needed; tokens expire after
CAPTCHA_TTL_SECONDS and the caller consumes the nonce once it verifies.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import io
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CAPTCHA_TTL_SECONDS = 180
CAPTCHA_DIGITS = 4


class CaptchaError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(pepper: str, nonce: str, expires: int, code: str) -> str:
    message = f"captcha|{nonce}|{expires}|{code}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), message, hashlib.sha256).hexdigest()


CAPTCHA_WIDTH = 180
CAPTCHA_HEIGHT = 60
CAPTCHA_IMAGE_PREFIX = "data:image/png;base64,"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except (OSError, TypeError):  # pragma: no cover - only without FreeType support
        return ImageFont.load_default()


def _png(code: str) -> str:
    """Draw the code as pixels only: no text layer, no markup, light distortion."""
    rnd = secrets.SystemRandom()
    width, height = CAPTCHA_WIDTH, CAPTCHA_HEIGHT
    image = Image.new("RGB", (width, height), (238, 243, 250))
    draw = ImageDraw.Draw(image)
    for _ in range(6):
        draw.line(
            [(rnd.randint(0, width), rnd.randint(0, height)), (rnd.randint(0, width), rnd.randint(0, height))],
            fill=(154, 179, 209),
            width=1,
        )
    font = _font(34)
    cell = width // len(code)
    for index, char in enumerate(code):
        glyph = Image.new("RGBA", (cell, height), (0, 0, 0, 0))
        glyph_draw = ImageDraw.Draw(glyph)
        glyph_draw.text((cell // 2, height // 2), char, font=font, fill=(11, 36, 71), anchor="mm")
        glyph = glyph.rotate(rnd.randint(-22, 22), resample=Image.Resampling.BICUBIC, expand=False)
        x = index * cell + rnd.randint(-4, 4)
        y = rnd.randint(-5, 5)
        image.paste(glyph, (x, y), glyph)
    for _ in range(90):
        draw.point((rnd.randint(0, width - 1), rnd.randint(0, height - 1)), fill=(120, 140, 170))
    for _ in range(2):
        draw.arc(
            [rnd.randint(-40, 40), rnd.randint(-30, 10), rnd.randint(width - 40, width + 40), rnd.randint(height - 10, height + 30)],
            start=rnd.randint(0, 180),
            end=rnd.randint(180, 360),
            fill=(90, 120, 160),
            width=1,
        )
    image = image.filter(ImageFilter.SMOOTH)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return CAPTCHA_IMAGE_PREFIX + base64.b64encode(buffer.getvalue()).decode("ascii")


def captcha_nonce(token: Any) -> str | None:
    """Return the token's random nonce (for one-time consumption) without validating it."""
    if not isinstance(token, str) or len(token) > 512:
        return None
    try:
        body_text, _mac_text = token.split(".", 1)
        data = json.loads(_unb64(body_text).decode("utf-8"))
        nonce = str(data["n"])
    except (ValueError, KeyError, TypeError):
        return None
    return nonce if 0 < len(nonce) <= 64 else None


def issue_captcha(pepper: str, now: float | None = None) -> dict[str, Any]:
    if not pepper:
        raise CaptchaError("captcha_not_configured")
    issued = time.time() if now is None else now
    expires = int(issued) + CAPTCHA_TTL_SECONDS
    code = "".join(str(secrets.randbelow(10)) for _ in range(CAPTCHA_DIGITS))
    nonce = secrets.token_urlsafe(12)
    body = _b64(json.dumps({"n": nonce, "e": expires}, separators=(",", ":")).encode("utf-8"))
    token = f"{body}.{_mac(pepper, nonce, expires, code)}"
    return {"token": token, "image": _png(code), "expires_in": CAPTCHA_TTL_SECONDS}


def verify_captcha(pepper: str, token: Any, answer: Any, now: float | None = None) -> bool:
    if not pepper or not isinstance(token, str) or not isinstance(answer, str):
        return False
    if len(token) > 512 or not answer.isascii() or len(answer) != CAPTCHA_DIGITS or not answer.isdigit():
        return False
    try:
        body_text, mac = token.split(".", 1)
        data = json.loads(_unb64(body_text).decode("utf-8"))
        nonce, expires = str(data["n"]), int(data["e"])
    except (ValueError, KeyError, TypeError):
        return False
    current = time.time() if now is None else now
    if current > expires or len(nonce) > 64:
        return False
    expected = _mac(pepper, nonce, expires, answer)
    return hmac.compare_digest(expected, mac)
