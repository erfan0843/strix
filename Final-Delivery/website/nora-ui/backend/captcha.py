"""Stateless image captcha for the phone login form.

The server issues a signed token (expiry + random nonce) and an SVG image of a
random 4-digit code. The code is never stored or sent in clear text: the token
carries only an HMAC over (nonce, expiry, code) keyed with the OTP pepper.
Verification recomputes the HMAC for the submitted answer. No database table is
needed; tokens expire after CAPTCHA_TTL_SECONDS.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

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


def _svg(code: str) -> str:
    rnd = secrets.SystemRandom()
    width, height = 180, 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="کد امنیتی">',
        f'<rect width="{width}" height="{height}" rx="10" fill="#EEF3FA"/>',
    ]
    for _ in range(6):
        parts.append(
            f'<line x1="{rnd.randint(0, width)}" y1="{rnd.randint(0, height)}" '
            f'x2="{rnd.randint(0, width)}" y2="{rnd.randint(0, height)}" '
            'stroke="#9AB3D1" stroke-width="1.2"/>'
        )
    for index, char in enumerate(code):
        x = 22 + index * 36
        y = 40 + rnd.randint(-4, 4)
        angle = rnd.randint(-14, 14)
        parts.append(
            f'<text x="{x}" y="{y}" font-size="30" font-family="monospace" font-weight="700" '
            f'fill="#0B2447" transform="rotate({angle} {x} {y})">{char}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def issue_captcha(pepper: str, now: float | None = None) -> dict[str, Any]:
    if not pepper:
        raise CaptchaError("captcha_not_configured")
    issued = time.time() if now is None else now
    expires = int(issued) + CAPTCHA_TTL_SECONDS
    code = "".join(str(secrets.randbelow(10)) for _ in range(CAPTCHA_DIGITS))
    nonce = secrets.token_urlsafe(12)
    body = _b64(json.dumps({"n": nonce, "e": expires}, separators=(",", ":")).encode("utf-8"))
    token = f"{body}.{_mac(pepper, nonce, expires, code)}"
    return {"token": token, "image": _svg(code), "expires_in": CAPTCHA_TTL_SECONDS}


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
