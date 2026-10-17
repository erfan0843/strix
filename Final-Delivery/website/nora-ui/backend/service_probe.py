"""Side-effect-free probes for service credentials.

Only probes that cannot move money, send messages or mutate remote state are
allowed here. That is why the SMS key and the payment webhook secret have no
probe at all: the honest answer is "configured, not verified" rather than a
green badge produced by a form being filled in.

``getMe`` is a read-only Bot API call: it proves the token belongs to a live bot
without sending anything to users.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

BALE_API_BASE = "https://tapi.bale.ai"
PROBE_TIMEOUT_SECONDS = 6


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, D102
        return None


def probe_bale_bot(token: str) -> tuple[bool, str]:
    """Call Bot API ``getMe``. Returns (ok, safe_code); never the token or body."""
    if not token:
        return False, "not_configured"
    request = urllib.request.Request(
        f"{BALE_API_BASE}/bot{token}/getMe",
        headers={"Accept": "application/json", "User-Agent": "nora-settings-probe"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(64 * 1024).decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404):
            return False, "bot_token_rejected"
        return False, "bot_api_unavailable"
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, "bot_api_unreachable"
    except (ValueError, UnicodeError):
        return False, "bot_api_invalid_response"
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        description = str(payload.get("description", "")) if isinstance(payload, dict) else ""
        if "unauthorized" in description.lower():
            return False, "bot_token_rejected"
        return False, "bot_api_rejected"
    result = payload.get("result")
    if not isinstance(result, dict) or not result.get("id"):
        return False, "bot_api_invalid_response"
    return True, "bot_api_ok"
