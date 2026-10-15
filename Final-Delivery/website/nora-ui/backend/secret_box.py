"""Encrypt owner-entered provider secrets before they reach the database.

The encryption key is read from NORA_SETTINGS_ENCRYPTION_KEY (a Fernet key).
Without that key, saving secrets from the admin panel is refused (fail closed).
Secrets are never returned in full; callers only receive a short hint.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


KEY_ENV = "NORA_SETTINGS_ENCRYPTION_KEY"


class SecretBoxError(RuntimeError):
    """A safe, non-secret error code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fernet() -> Fernet:
    raw = os.getenv(KEY_ENV, "").strip()
    if not raw:
        raise SecretBoxError("settings_encryption_not_configured")
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise SecretBoxError("settings_encryption_key_invalid") from None


def encryption_configured() -> bool:
    try:
        _fernet()
    except SecretBoxError:
        return False
    return True


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise SecretBoxError("settings_secret_unreadable") from None


def secret_hint(value: str) -> str:
    """Return a non-reversible display hint such as '…abcd'."""
    tail = value[-4:] if len(value) >= 8 else ""
    return f"…{tail}" if tail else "…"
