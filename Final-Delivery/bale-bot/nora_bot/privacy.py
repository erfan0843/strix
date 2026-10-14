"""Small, side-effect-free safeguards for operational messages and logs.

This is best-effort log redaction, not a substitute for rotating an exposed
credential or restricting log/backup access. It never contacts a provider.
"""
from __future__ import annotations

import os
import re
from urllib.parse import quote, quote_plus


_REDACTED = "[REDACTED]"
_BOT_TOKEN = re.compile(r"(?<![\d:])\d{5,20}(?::|%3[aA])[A-Za-z0-9_-]{20,128}(?![\w-])")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)
_SECRET_FIELD = re.compile(
    r"\b([\w-]*(?:token|secret|password|api[_-]?key|session(?:[_-]?key)?|csrf(?:[_-]?token)?))"
    r"([\"']?\s*[:=]\s*[\"']?)(?!\[REDACTED\])([^\s\"',;&}\]]+)",
    re.IGNORECASE,
)
_MOBILE = re.compile(r"(?<!\d)(?:\+98|0098|98|0)9\d{9}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def redact_log_text(value: object) -> str:
    text = str(value)
    # Exact known values also cover unusual token formats not matched by regex.
    for name, secret in os.environ.items():
        if secret and len(secret) >= 8 and name.upper().endswith(
            ("TOKEN", "SECRET", "PASSWORD", "KEY", "DATABASE_URL")
        ):
            for encoded in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(encoded, _REDACTED)
    text = _BOT_TOKEN.sub(_REDACTED, text)
    text = _BEARER.sub("Bearer " + _REDACTED, text)
    text = _SECRET_FIELD.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, text)
    text = _MOBILE.sub(_REDACTED, text)
    return _EMAIL.sub(_REDACTED, text)


def user_error_message(_error: BaseException | None = None) -> str:
    """Do not send exception internals, provider URLs, or secrets to a chat."""
    return "درخواست انجام نشد؛ دوباره تلاش کن."
