"""Owner-editable system settings with an explicit allowlist (panel «تنظیمات»).

Design rule (پنل مرجع ← پنل اجرایی, 1405/08/01): a key exists here only when a
server-side consumer actually reads it. Nothing is stored "for later"; a toggle
without a consumer stays a documented decision item in the panel, not a row.

Keys
----
``texts.reminder_head``
    Optional first line of the event reminder (B19). Placeholders ``{رویداد}``
    and ``{زمان}`` (``24 ساعت دیگر`` / ``۱ ساعت دیگر``) are substituted by
    :func:`backend.event_reminders.message_for`. Empty string → built-in text.
``events.reminders_default``
    ``{"h24": bool, "h1": bool}``; preset for the reminder switches of a *new*
    event in the panel wizard. Existing events keep their own ``reminders``.

Storage: ``system_settings`` (key, JSON value, updated_at, updated_by). No
secrets ever live here (those stay in the encrypted service-settings store).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SystemSettingRecord

MAX_TEXT: Final = 300


class SettingError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.message = message or code


def _short_text(raw: Any) -> str:
    if not isinstance(raw, str):
        raise SettingError("invalid_text", "متن باید رشته باشد.")
    value = " ".join(raw.replace("\r", " ").replace("\n", " ").split())
    if len(value) > MAX_TEXT:
        raise SettingError("text_too_long", f"حداکثر {MAX_TEXT} نویسه.")
    return value


def _reminder_defaults(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict) or set(raw) - {"h24", "h1"}:
        raise SettingError("invalid_reminders_default", "فقط کلیدهای h24 و h1 پذیرفته می‌شوند.")
    out = {}
    for slot in ("h24", "h1"):
        value = raw.get(slot, False)
        if not isinstance(value, bool):
            raise SettingError("invalid_reminders_default", "مقدار هر یادآور باید بولی باشد.")
        out[slot] = value
    return out


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: Any
    normalize: Callable[[Any], Any]
    consumer: str  # human-readable: which server path reads it (shown in the panel)


SPECS: Final = (
    SettingSpec(
        key="texts.reminder_head",
        default="",
        normalize=_short_text,
        consumer="سطر نخست پیام یادآور رویداد (۲۴ ساعت و ۱ ساعت قبل) که زمان‌بند سرور در صف اعلان می‌گذارد",
    ),
    SettingSpec(
        key="events.reminders_default",
        default={"h24": False, "h1": False},
        normalize=_reminder_defaults,
        consumer="پیش‌فرض کلیدهای یادآور هنگام ساخت رویداد تازه در پنل؛ رویدادهای موجود دست نمی‌خورند",
    ),
)
SPECS_BY_KEY: Final = {spec.key: spec for spec in SPECS}


def _rows(db: Session) -> dict[str, SystemSettingRecord]:
    return {row.key: row for row in db.scalars(select(SystemSettingRecord)).all()}


def get_value(db: Session, key: str) -> Any:
    spec = SPECS_BY_KEY[key]
    row = db.get(SystemSettingRecord, key)
    if row is None:
        return spec.default
    try:
        return spec.normalize(row.value.get("v") if isinstance(row.value, dict) else None)
    except SettingError:
        return spec.default


def payload(db: Session) -> dict[str, Any]:
    rows = _rows(db)
    items = []
    for spec in SPECS:
        row = rows.get(spec.key)
        items.append({
            "key": spec.key,
            "value": get_value(db, spec.key),
            "default": spec.default,
            "custom": row is not None,
            "consumer": spec.consumer,
            "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
            "updated_by": row.updated_by if row is not None else "",
        })
    return {"items": items}


def apply(db: Session, changes: dict[str, Any], *, actor: str, now: datetime | None = None) -> list[str]:
    """Validate and persist ``changes``; returns the keys that were written.

    Unknown keys are rejected as a whole (no partial writes). A value equal to the
    spec default removes the row so ``custom`` becomes false again.
    """
    if not isinstance(changes, dict) or not changes:
        raise SettingError("empty_changes", "تغییری فرستاده نشده است.")
    unknown = sorted(set(changes) - set(SPECS_BY_KEY))
    if unknown:
        raise SettingError("unknown_setting", "کلید ناشناخته: " + "، ".join(unknown))
    normalized = {key: SPECS_BY_KEY[key].normalize(value) for key, value in changes.items()}
    written: list[str] = []
    for key, value in normalized.items():
        spec = SPECS_BY_KEY[key]
        row = db.get(SystemSettingRecord, key)
        if value == spec.default:
            if row is not None:
                db.delete(row)
                written.append(key)
            continue
        if row is None:
            row = SystemSettingRecord(key=key, value={"v": value}, updated_by=actor[:120])
            db.add(row)
        else:
            row.value = {"v": value}
            row.updated_by = actor[:120]
            if now is not None:
                row.updated_at = now
        written.append(key)
    return written
