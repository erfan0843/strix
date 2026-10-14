"""Small, fail-closed Bale Bot API client used only by shared form payments."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit


if TYPE_CHECKING:
    from .config import Settings


_TOKEN = re.compile(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}\Z")
_ALLOWED_INVOICE_HOSTS = {"ble.ir", "bale.ai"}


class BalePaymentAPIError(RuntimeError):
    """A provider error with a safe, non-secret diagnostic code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    try:
        parsed_url = urlsplit(url)
        port = parsed_url.port
    except ValueError:
        raise BalePaymentAPIError("bale_api_url_invalid") from None
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "tapi.bale.ai"
        or parsed_url.username is not None
        or parsed_url.password is not None
        or port not in (None, 443)
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise BalePaymentAPIError("bale_api_url_invalid")
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    # Never follow a provider redirect: the request contains a bot credential.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise BalePaymentAPIError("bale_api_http_error")
            raw = response.read(128 * 1024 + 1)
    except urllib.error.HTTPError:
        raise BalePaymentAPIError("bale_api_http_error") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BalePaymentAPIError("bale_api_unreachable") from None
    if len(raw) > 128 * 1024:
        raise BalePaymentAPIError("bale_api_response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BalePaymentAPIError("bale_api_invalid_response") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise BalePaymentAPIError("bale_api_request_rejected")
    return result


def call_bale_payment_api(
    settings: Settings, method: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Call an allowlisted Bot API method without exposing secrets to callers."""
    if method not in {
        "createInvoiceLink",
        "answerPreCheckoutQuery",
        "getWebhookInfo",
        "setWebhook",
        "inquireTransaction",
    }:
        raise BalePaymentAPIError("bale_api_method_not_allowed")
    token = settings.form_payment_bot_token
    if not _TOKEN.fullmatch(token):
        raise BalePaymentAPIError("bale_payment_not_configured")
    timeout = settings.form_payment_timeout_seconds
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 8:
        raise BalePaymentAPIError("bale_payment_timeout_invalid")
    url = f"https://tapi.bale.ai/bot{token}/{method}"
    return _post_json(url, payload, timeout)


def validated_invoice_url(value: Any) -> str:
    """Allow only HTTPS Bale invoice links; reject arbitrary provider URLs."""
    if not isinstance(value, str) or len(value) > 2048:
        raise BalePaymentAPIError("bale_invoice_url_invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise BalePaymentAPIError("bale_invoice_url_invalid") from None
    host = (parsed.hostname or "").lower()
    allowed_host = host in _ALLOWED_INVOICE_HOSTS or any(
        host.endswith("." + suffix) for suffix in _ALLOWED_INVOICE_HOSTS
    )
    if (
        parsed.scheme != "https"
        or not allowed_host
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or not parsed.path
        or parsed.fragment
    ):
        raise BalePaymentAPIError("bale_invoice_url_invalid")
    return value
