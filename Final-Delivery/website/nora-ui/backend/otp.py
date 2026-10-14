"""Member phone-OTP primitives and the existing Safir delivery contract.

This module never logs or returns an OTP. Delivery fails closed when the
server-only Safir settings are absent; there is no local/test-code path.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PHONE_PUNCTUATION = re.compile(r"[\s().-]")
_PHONE_LOCAL = re.compile(r"09[0-9]{9}\Z")


def normalize_iran_phone(value: object) -> str | None:
    """Normalize common Iranian mobile forms to 09xxxxxxxxx."""
    if not isinstance(value, str):
        return None
    raw = value.translate(_DIGITS).strip()
    if len(raw) > 32:
        return None
    compact = _PHONE_PUNCTUATION.sub("", raw)
    if compact.startswith("+98"):
        compact = "0" + compact[3:]
    elif compact.startswith("0098"):
        compact = "0" + compact[4:]
    elif compact.startswith("98"):
        compact = "0" + compact[2:]
    elif len(compact) == 10 and compact.startswith("9"):
        compact = "0" + compact
    return compact if _PHONE_LOCAL.fullmatch(compact) else None


def generate_otp_code() -> str:
    """Return a cryptographically random six-digit code, including leading zeroes."""
    return f"{secrets.randbelow(1_000_000):06d}"


def phone_digest(pepper: str, phone: str) -> str:
    return hmac.new(pepper.encode("utf-8"), ("phone:" + phone).encode("ascii"), hashlib.sha256).hexdigest()


def otp_digest(pepper: str, challenge_id: str, code: str) -> str:
    message = f"phone-otp:{challenge_id}:{code}".encode("ascii")
    return hmac.new(pepper.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _post_json(url: str, api_key: str, payload: dict[str, Any]) -> tuple[bool, int, dict[str, Any]]:
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"api-access-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            status = int(response.status)
            raw = response.read(16_384)
    except HTTPError as error:
        status = int(error.code)
        try:
            raw = error.read(16_384)
        except Exception:
            raw = b""
    except (URLError, TimeoutError, OSError, ValueError):
        return False, 0, {}
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    ok = status in (200, 201) and bool(body.get("message_id")) and not body.get("error_data")
    return ok, status, body


def send_safir_otp(
    *,
    api_key: str,
    bot_id: str,
    url: str,
    phone: str,
    code: str,
    include_request_id: bool = True,
) -> bool:
    """Send one OTP using the same Safir API contract as the existing bot.

    Only HTTPS to the configured Safir host is accepted. The request payload is
    never logged and the code is never returned to the browser.
    """
    if not api_key or not bot_id or not url:
        return False
    try:
        parsed = urlsplit(url)
        numeric_bot_id = int(bot_id)
    except (TypeError, ValueError):
        return False
    if (
        parsed.scheme != "https"
        or parsed.hostname != "safir.bale.ai"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or numeric_bot_id <= 0
        or not _PHONE_LOCAL.fullmatch(phone)
        or not re.fullmatch(r"[0-9]{6}", code)
    ):
        return False

    base: dict[str, Any] = {
        "bot_id": numeric_bot_id,
        "phone_number": "98" + phone[1:],
        "message_data": {"otp_message": {"otp": code}},
    }
    attempts: list[dict[str, Any]] = []
    if include_request_id:
        attempts.append({**base, "request_id": "nora" + uuid.uuid4().hex})
    attempts.append(base)
    for payload in attempts:
        ok, status, body = _post_json(url, api_key, payload)
        if ok:
            return True
        if status in (401, 403) or str(body.get("error_data", "")).lower() in {
            "unauthorized", "invalid key", "access denied"
        }:
            return False
    return False
