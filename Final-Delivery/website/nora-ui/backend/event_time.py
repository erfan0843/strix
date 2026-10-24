"""Shared event-time logic: Tehran-referenced Jalali input, UTC storage, and the
registration state that every surface (public API, form gate, bot) must agree on.

No database access here; callers pass the already-projected event dict and the
facts they know (server ``now``, whether a published registration form is
linked, whether that form's capacity is full).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

REFERENCE_TZ = ZoneInfo("Asia/Tehran")

REG_MODES = ("auto", "closed", "full")
LIFECYCLES = ("scheduled", "cancelled", "postponed")
# Order matters: the first matching rule wins (see ``registration_state``).
REGISTRATION_STATES = ("cancelled", "ended", "closed", "full", "not_started", "none", "open")
CLOSED_STATES = frozenset({"cancelled", "ended", "closed", "full", "not_started"})

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LOCAL_INPUT = re.compile(r"^(1[3-4]\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:[ T](\d{1,2}):(\d{2}))?$")

# ── Jalali ↔ Gregorian (same algorithm as nora-ui/ui.js and events-page.js) ──
_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178)


def _div(a: int, b: int) -> int:
    return int(a / b)


def _mod(a: int, b: int) -> int:
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> tuple[int, int, int]:
    gy = jy + 621
    leap_j, jp, jm, jump = -14, _BREAKS[0], 0, 0
    for index in range(1, len(_BREAKS)):
        jm = _BREAKS[index]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, march, gy


def _g2d(gy: int, gm: int, gd: int) -> int:
    d = _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4) + _div(153 * _mod(gm + 9, 12) + 2, 5) + gd - 34840408
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn: int) -> tuple[int, int, int]:
    j = 4 * jdn + 139361631
    j = j + _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _j2d(jy: int, jm: int, jd: int) -> int:
    _, march, gy = _jal_cal(jy)
    return _g2d(gy, 3, march) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1


def _d2j(jdn: int) -> tuple[int, int, int]:
    gy, _, _ = _d2g(jdn)
    jy = gy - 621
    leap, march, _ = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), _mod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + _div(k, 30), _mod(k, 30) + 1


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    return _d2g(_j2d(jy, jm, jd))


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    return _d2j(_g2d(gy, gm, gd))


def jalali_days_in_month(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if _jal_cal(jy)[0] == 0 else 29


# ── Parsing / formatting ──

def parse_utc(value: Any) -> datetime | None:
    """ISO-8601 with an explicit offset (or ``Z``) → aware UTC datetime; else ``None``."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_event_datetime(value: Any) -> str:
    """Accept either an aware ISO-8601 string or a Jalali ``YYYY/MM/DD[ HH:MM]`` typed in
    the reference time zone (Asia/Tehran); return the canonical UTC ISO string or ``""``.
    Raises ``ValueError("invalid_datetime")`` for non-empty invalid input."""
    if value is None:
        return ""
    text = str(value).strip().translate(_PERSIAN_DIGITS).replace("-", "/").replace(".", "/")
    if not text:
        return ""
    iso = parse_utc(str(value).strip())
    if iso is not None:
        return to_iso(iso)
    match = _LOCAL_INPUT.fullmatch(text)
    if not match:
        raise ValueError("invalid_datetime")
    jy, jm, jd = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if jd > jalali_days_in_month(jy, jm):
        raise ValueError("invalid_datetime")
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    if hour > 23 or minute > 59:
        raise ValueError("invalid_datetime")
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    local = datetime(gy, gm, gd, hour, minute, tzinfo=REFERENCE_TZ)
    return to_iso(local.astimezone(timezone.utc))


def to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def to_local_input(value: Any) -> str:
    """UTC ISO string → ``YYYY/MM/DD HH:MM`` Jalali in the reference zone (panel fill-back)."""
    parsed = parse_utc(value)
    if parsed is None:
        return ""
    local = parsed.astimezone(REFERENCE_TZ)
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d} {local.hour:02d}:{local.minute:02d}"


# ── Registration state (single source of truth) ──

def registration_state(
    event: dict[str, Any],
    *,
    now: datetime,
    has_form: bool,
    form_full: bool = False,
) -> dict[str, Any]:
    """Compute the registration status of a published event.

    Publication status is *not* an input: the caller only passes events that are
    already public. Rules, first match wins:
    cancelled → ended → closed → full → not_started → none → open.
    """
    now_utc = now.astimezone(timezone.utc)
    lifecycle = str(event.get("lifecycle") or "scheduled")
    reg_mode = str(event.get("regMode") or "auto")
    starts = parse_utc(event.get("startsAt"))
    ends = parse_utc(event.get("endsAt"))
    opens = parse_utc(event.get("regOpensAt"))
    closes = parse_utc(event.get("regClosesAt"))
    state = "open"
    reason = ""
    if lifecycle == "cancelled":
        state, reason = "cancelled", "lifecycle"
    elif event.get("past") is True or (ends is not None and ends <= now_utc):
        state, reason = "ended", "past" if event.get("past") is True else "time"
    elif reg_mode == "closed":
        state, reason = "closed", "manual"
    elif closes is not None and closes <= now_utc:
        state, reason = "closed", "deadline"
    elif closes is None and starts is not None and starts <= now_utc:
        # No explicit deadline: once the event has started, registration is not open.
        state, reason = "closed", "started"
    elif reg_mode == "full" or form_full:
        state, reason = "full", "manual" if reg_mode == "full" else "capacity"
    elif opens is not None and opens > now_utc:
        state, reason = "not_started", "schedule"
    elif not has_form:
        state, reason = "none", "no_form"
    if lifecycle == "postponed" and state in {"open", "not_started", "none"}:
        # A postponed event keeps its registration state but must never look "live".
        reason = "postponed"
    return {
        "state": state,
        "reason": reason,
        "lifecycle": lifecycle if lifecycle in LIFECYCLES else "scheduled",
        "opensAt": to_iso(opens) if opens else "",
        "closesAt": to_iso(closes) if closes else "",
        "startsAt": to_iso(starts) if starts else "",
        "endsAt": to_iso(ends) if ends else "",
        # Countdown targets are derived here so no surface re-implements the rule.
        "countdownTo": (
            to_iso(closes) if state == "open" and closes
            else to_iso(opens) if state == "not_started" and opens
            else ""
        ),
        "startsIn": to_iso(starts) if starts and starts > now_utc and state not in {"cancelled"} else "",
    }


def is_registration_blocked(state: str) -> bool:
    return state in CLOSED_STATES


def clamp_future(value: datetime, *, horizon_days: int = 3660) -> bool:
    """Reject absurd dates (10+ years out) that are almost certainly typos."""
    return value <= datetime.now(timezone.utc) + timedelta(days=horizon_days)
