"""Password hashing and opaque-token helpers; no browser-held secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_KEY_BYTES = 32


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Create an encoded scrypt hash for owner or manager credentials."""
    raw = password.encode("utf-8")
    if not 12 <= len(raw) <= 1024:
        raise ValueError("password must contain 12 to 1024 UTF-8 bytes")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        raw,
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_KEY_BYTES,
        maxmem=128 * 1024 * 1024,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        n_value, r_value, p_value = int(n), int(r), int(p)
        # Keep stored hashes within reviewed resource bounds.
        if n_value != _SCRYPT_N or r_value != _SCRYPT_R or p_value != _SCRYPT_P:
            return False
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
        if len(salt) != 16 or len(expected) != _SCRYPT_KEY_BYTES:
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=len(expected),
            maxmem=128 * 1024 * 1024,
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError, UnicodeError, MemoryError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def throttle_digest(pepper: str, value: str) -> str:
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class BaleMiniAppIdentity:
    user_id: int
    auth_date: int
    replay_key: str


def verify_bale_mini_app_init_data(
    raw_init_data: str,
    bot_token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 600,
    max_future_seconds: int = 60,
) -> BaleMiniAppIdentity:
    """Verify Bale.WebApp.initData using Bale's documented HMAC-SHA-256 scheme.

    The exact raw URL-encoded string must be sent by the Mini App. Query values
    are decoded once, all fields except ``hash`` are sorted and joined with LF,
    and the comparison is constant-time. The returned replay key contains no
    user profile data and must be recorded by the caller before issuing a session.
    """
    if not isinstance(raw_init_data, str) or not raw_init_data or raw_init_data != raw_init_data.strip():
        raise ValueError("invalid_bale_init_data")
    try:
        raw_size = len(raw_init_data.encode("utf-8", errors="strict"))
    except UnicodeError:
        raise ValueError("invalid_bale_init_data") from None
    if raw_size > 8192 or re.search(r"%(?![0-9a-fA-F]{2})", raw_init_data):
        raise ValueError("invalid_bale_init_data")
    if not isinstance(bot_token, str) or not bot_token:
        raise ValueError("invalid_bale_init_data")
    if not 60 <= max_age_seconds <= 3600 or not 0 <= max_future_seconds <= 300:
        raise ValueError("invalid_bale_init_data")

    try:
        pairs = parse_qsl(
            raw_init_data,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=64,
        )
    except (ValueError, UnicodeError):
        raise ValueError("invalid_bale_init_data") from None
    if not pairs or any(not key for key, _ in pairs):
        raise ValueError("invalid_bale_init_data")
    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError("invalid_bale_init_data")
        fields[key] = value

    supplied_hash = fields.pop("hash", "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", supplied_hash):
        raise ValueError("invalid_bale_init_data")
    auth_date_text = fields.get("auth_date", "")
    user_text = fields.get("user", "")
    if not re.fullmatch(r"[0-9]{1,12}", auth_date_text) or not user_text:
        raise ValueError("invalid_bale_init_data")

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash.lower()):
        raise ValueError("invalid_bale_init_data")

    try:
        auth_date = int(auth_date_text)
        user = json.loads(user_text)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("invalid_bale_init_data") from None
    if not isinstance(user, dict):
        raise ValueError("invalid_bale_init_data")
    user_id = user.get("id")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("invalid_bale_init_data")

    current_time = int(time.time()) if now is None else int(now)
    if auth_date > current_time + max_future_seconds or current_time - auth_date > max_age_seconds:
        raise ValueError("invalid_bale_init_data")

    replay_key = hashlib.sha256(supplied_hash.lower().encode("ascii")).hexdigest()
    return BaleMiniAppIdentity(user_id=user_id, auth_date=auth_date, replay_key=replay_key)
