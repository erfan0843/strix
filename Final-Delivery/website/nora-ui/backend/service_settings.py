"""Central registry of Nora's service connections and their encrypted credentials.

Why this module exists
----------------------
Before it, every credential lived in an environment variable read at process
start: the owner could not rotate a key from the panel and could not see where a
value came from. Here the three service families are described once
(Bale/mini-app, SMS/OTP, payment) and the rules for storing, masking and
reporting them live in one place instead of being duplicated in endpoints and in
the browser.

Security contract
-----------------
* Secrets are encrypted with ``secret_box`` (Fernet, key from
  ``NORA_SETTINGS_ENCRYPTION_KEY``) before they touch the database. Without that
  key every write is refused; nothing is stored in plain text.
* No function here returns a stored secret. Callers only receive a short hint
  (``…abcd``), a source (``database`` / ``environment`` / ``none``) and the time
  of the last change.
* Values are never logged or embedded in error messages.
* Only credentials the web process itself consumes and can verify are editable.
  Coupled values that only make sense together with the bot process
  (``NORA_BOT_SERVICE_TOKEN``), privilege-bearing values
  (``NORA_OWNER_BALE_USER_ID``) and immutable derivation material
  (``NORA_OTP_PEPPER``) are displayed read-only with an explanation, because
  changing them from here would break a running component or escalate access.
* Rotating the Safir key is refused unless ``NORA_OTP_PEPPER`` is set
  independently: otherwise the pepper was derived from the old key at start-up
  and the next restart would silently invalidate every phone identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Final

from sqlalchemy.orm import Session

from .config import Settings
from .models import PaymentSecretRecord, ServiceCheckRecord
from .secret_box import (
    SecretBoxError,
    decrypt_secret,
    encrypt_secret,
    encryption_configured,
    secret_hint,
)

# Same Bot API token shape the existing payment code already enforces.
BOT_TOKEN_RE: Final = re.compile(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}\Z")
PRINTABLE_RE: Final = re.compile(r"[!-~]{1,512}\Z")
WEBHOOK_SECRET_RE: Final = re.compile(r"[!-~]{32,256}\Z")
SAFIR_KEY_RE: Final = re.compile(r"[!-~]{8,512}\Z")

# Environment names whose effective value lives on a Settings attribute. Used
# only for prerequisites and display; the Settings object is the source of
# truth, so a test that builds Settings directly behaves like production.
_ENV_TO_ATTRIBUTE: Final = {
    "NORA_OTP_PEPPER": "otp_pepper",
}


@dataclass(frozen=True)
class SecretSpec:
    """One credential the owner may manage, with the rule that validates it."""

    storage_id: str
    attribute: str
    env_name: str
    label: str
    help_text: str
    pattern: re.Pattern[str]
    invalid_code: str
    editable: bool = True
    requires_env: tuple[str, ...] = ()
    acknowledge_restart: bool = False
    probe: str = "none"


@dataclass(frozen=True)
class ReadonlySpec:
    """A value the panel only displays, together with its real source."""

    env_name: str
    attribute: str
    label: str
    note: str
    kind: str = "text"  # text | masked | minutes | seconds


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    title: str
    icon: str
    summary: str
    secrets: tuple[SecretSpec, ...]
    readonly: tuple[ReadonlySpec, ...]


SERVICES: Final = (
    ServiceSpec(
        key="bale",
        title="بله و مینی‌اپ",
        icon="i-send",
        summary="توکن ربات، اعتبارسنجی امضای مینی‌اپ و وضعیت دامنه",
        secrets=(
            SecretSpec(
                storage_id="bale_bot",
                attribute="bale_bot_token",
                env_name="NORA_BALE_BOT_TOKEN",
                label="توکن ربات اصلی",
                help_text=(
                    "همین توکن، امضای initData مینی‌اپ را اعتبارسنجی می‌کند. "
                    "پس از تعویض، ربات هم باید با همان مقدار راه‌اندازی شود."
                ),
                pattern=BOT_TOKEN_RE,
                invalid_code="invalid_bale_bot_token",
                acknowledge_restart=True,
                probe="bale_get_me",
            ),
        ),
        readonly=(
            ReadonlySpec("NORA_BALE_BOT_USERNAME", "bale_bot_username", "نام کاربری عمومی ربات", "برای ساخت نشانی مینی‌اپ و پیوند عمیق"),
            ReadonlySpec("NORA_OWNER_BALE_USER_ID", "owner_bale_user_id", "شناسه بله مالک", "نقش مالک از همین مقدار سمت سرور تعیین می‌شود"),
            ReadonlySpec("NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", "bale_init_data_max_age_seconds", "حداکثر عمر امضای مینی‌اپ", "پنجرهٔ پذیرش initData؛ پیش‌فرض ۶۰۰ ثانیه", "seconds"),
            ReadonlySpec("NORA_PUBLIC_BASE_URL", "public_base_url", "نشانی عمومی سامانه", "دامنهٔ HTTPS وب و مینی‌اپ"),
            ReadonlySpec("NORA_BOT_SERVICE_TOKEN", "bot_service_token", "توکن سرویس ربات ↔ سرور", "همین مقدار در ربات هم تنظیم می‌شود؛ چرخش باید هم‌زمان در هر دو طرف باشد", "masked"),
        ),
    ),
    ServiceSpec(
        key="sms",
        title="پیامک و رمز یک‌بارمصرف",
        icon="i-bell",
        summary="کلید سرویس سفیر و پارامترهای ارسال کد",
        secrets=(
            SecretSpec(
                storage_id="safir_api_key",
                attribute="safir_api_key",
                env_name="SAFIR_API_KEY",
                label="کلید دسترسی سفیر",
                help_text=(
                    "برای ارسال پیامک رمز یک‌بارمصرف. تعویض کلید فقط وقتی مجاز است که "
                    "NORA_OTP_PEPPER جداگانه تنظیم شده باشد؛ وگرنه هویت‌های شماره‌ای "
                    "پس از راه‌اندازی مجدد باطل می‌شوند."
                ),
                pattern=SAFIR_KEY_RE,
                invalid_code="invalid_safir_api_key",
                requires_env=("NORA_OTP_PEPPER",),
            ),
        ),
        readonly=(
            ReadonlySpec("SAFIR_BOT_ID", "safir_bot_id", "شناسه ربات سرویس", "شناسهٔ عددی ربات ارسال کد"),
            ReadonlySpec("SAFIR_URL", "safir_url", "نشانی سرویس سفیر", "فقط دامنهٔ safir.bale.ai پذیرفته می‌شود"),
            ReadonlySpec("OTP_TTL_MINUTES", "otp_ttl_seconds", "اعتبار کد", "دقیقه؛ بین ۱ و ۱۵", "minutes"),
            ReadonlySpec("OTP_MAX_ATTEMPTS", "otp_max_attempts", "حداکثر تلاش", "بین ۱ و ۱۰"),
            ReadonlySpec("OTP_RESEND_SECONDS", "otp_resend_seconds", "فاصلهٔ ارسال دوباره", "ثانیه؛ بین ۳۰ و ۶۰۰", "seconds"),
            ReadonlySpec("NORA_OTP_PEPPER", "otp_pepper", "فلفل هش هویت", "ثابت و مستقل از کلید؛ تعویض آن همهٔ هویت‌های شماره‌ای را باطل می‌کند", "masked"),
        ),
    ),
    ServiceSpec(
        key="payment",
        title="پرداخت و کیف پول",
        icon="i-wallet",
        summary="توکن کیف پول بله، توکن ارائه‌دهنده و راز وب‌هوک",
        secrets=(
            SecretSpec(
                storage_id="bale_wallet",
                attribute="form_payment_bot_token",
                env_name="NORA_FORM_PAYMENT_BOT_TOKEN",
                label="توکن کیف پول بله",
                help_text="همان شناسه‌ای که پرداخت‌های فرم با آن ساخته می‌شود.",
                pattern=BOT_TOKEN_RE,
                invalid_code="invalid_bale_wallet_key_format",
                probe="bale_get_me",
            ),
            SecretSpec(
                storage_id="payment_provider",
                attribute="form_payment_provider_token",
                env_name="NORA_FORM_PAYMENT_PROVIDER_TOKEN",
                label="توکن ارائه‌دهندهٔ پرداخت",
                help_text="فقط اگر ارائه‌دهنده توکن جدا بدهد؛ خالی‌بودن یعنی از توکن کیف پول استفاده شود.",
                pattern=PRINTABLE_RE,
                invalid_code="invalid_form_payment_provider_token",
            ),
            SecretSpec(
                storage_id="payment_webhook",
                attribute="form_payment_webhook_secret",
                env_name="NORA_FORM_PAYMENT_WEBHOOK_SECRET",
                label="راز وب‌هوک پرداخت",
                help_text="۳۲ تا ۲۵۶ نویسهٔ چاپی؛ برای تأیید درخواست‌های بازگشتی ارائه‌دهنده.",
                pattern=WEBHOOK_SECRET_RE,
                invalid_code="invalid_form_payment_webhook_secret",
            ),
        ),
        readonly=(
            ReadonlySpec("NORA_FORM_PAYMENT_WEBHOOK_URL", "form_payment_webhook_url", "نشانی وب‌هوک", "باید HTTPS و به مسیر پرداخت ختم شود"),
            ReadonlySpec("NORA_FORM_PAYMENT_TTL_SECONDS", "form_payment_ttl_seconds", "مهلت پرداخت", "ثانیه؛ بین ۶۰ و ۸۶۴۰۰", "seconds"),
            ReadonlySpec("NORA_FORM_PAYMENT_MAX_AMOUNT", "form_payment_max_amount", "سقف مبلغ", "ریال؛ حداکثر ۲٬۰۰۰٬۰۰۰٬۰۰۰"),
        ),
    ),
)

SECRETS_BY_ID: Final = {secret.storage_id: secret for service in SERVICES for secret in service.secrets}
SERVICES_BY_KEY: Final = {service.key: service for service in SERVICES}


def service_of_secret(storage_id: str) -> ServiceSpec | None:
    for service in SERVICES:
        if any(secret.storage_id == storage_id for secret in service.secrets):
            return service
    return None


def encryption_ready() -> bool:
    return encryption_configured()


def _cfg_has(cfg: Settings, attribute: str) -> bool:
    value = getattr(cfg, attribute, "")
    return bool(str(value).strip()) if value is not None else False


def _record(db: Session, storage_id: str) -> PaymentSecretRecord | None:
    return db.get(PaymentSecretRecord, storage_id)


def stored_at(db: Session, storage_id: str) -> str | None:
    record = _record(db, storage_id)
    if record is None or record.updated_at is None:
        return None
    moment = record.updated_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def _stored_value(db: Session, storage_id: str) -> str | None:
    record = _record(db, storage_id)
    if record is None:
        return None
    try:
        return decrypt_secret(record.ciphertext)
    except SecretBoxError:
        return None


def effective_settings(db: Session, cfg: Settings) -> Settings:
    """Return settings whose web-consumed secrets come from the encrypted store.

    Environment values stay the fallback. A record that cannot be decrypted is
    ignored (the environment value is used) instead of failing the request, so a
    rotated encryption key never takes the whole site down.
    """
    updates: dict[str, Any] = {}
    for storage_id, secret in SECRETS_BY_ID.items():
        if not secret.editable:
            continue
        value = _stored_value(db, storage_id)
        if value:
            updates[secret.attribute] = value
    if not updates:
        return cfg
    return replace(cfg, **updates)


def _check_state(db: Session, storage_id: str) -> ServiceCheckRecord | None:
    return db.get(ServiceCheckRecord, storage_id)


def _check_payload(db: Session, storage_id: str) -> dict[str, object]:
    record = _check_state(db, storage_id)
    if record is None:
        return {"checked": False, "ok": None, "code": "", "checked_at": None}
    checked_at = record.checked_at
    if checked_at is not None and checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return {
        "checked": True,
        "ok": bool(record.ok),
        "code": record.code,
        "checked_at": checked_at.astimezone(timezone.utc).isoformat() if checked_at else None,
    }


def _required_attributes(secret: SecretSpec) -> list[tuple[str, str]]:
    return [(name, _ENV_TO_ATTRIBUTE.get(name, name)) for name in secret.requires_env]


def _field_status(db: Session, secret: SecretSpec, cfg: Settings) -> dict[str, object]:
    record = _record(db, secret.storage_id)
    env_set = _cfg_has(cfg, secret.attribute)
    missing_env = [name for name, attribute in _required_attributes(secret) if not _cfg_has(cfg, attribute)]
    service = service_of_secret(secret.storage_id)
    return {
        "key": secret.storage_id,
        "service": service.key if service else "",
        "label": secret.label,
        "help": secret.help_text,
        "env_name": secret.env_name,
        "editable": secret.editable,
        "acknowledge_restart": secret.acknowledge_restart,
        "probe": secret.probe,
        "configured": record is not None or env_set,
        "source": "database" if record is not None else ("environment" if env_set else "none"),
        "hint": record.hint if record is not None else "",
        "updated_at": stored_at(db, secret.storage_id),
        "encryption_ready": encryption_ready(),
        "blocked_by": missing_env,
        "check": _check_payload(db, secret.storage_id),
    }


def _service_state(fields: list[dict[str, object]]) -> str:
    """unconfigured | configured | verified | failed — derived, never optimistic."""
    configured = [field for field in fields if field["configured"]]
    if not configured:
        return "unconfigured"
    checks: list[dict[str, object]] = []
    for field in configured:
        check = field.get("check")
        if isinstance(check, dict):
            checks.append(check)
    if any(check["checked"] and check["ok"] is False for check in checks):
        return "failed"
    if checks and all(check["checked"] and check["ok"] for check in checks):
        return "verified"
    return "configured"


def status_payload(db: Session, cfg: Settings) -> dict[str, object]:
    """Describe every service without ever returning a secret value."""
    services = []
    for service in SERVICES:
        fields = [_field_status(db, secret, cfg) for secret in service.secrets]
        readonly = []
        for item in service.readonly:
            raw = getattr(cfg, item.attribute, "")
            configured = _cfg_has(cfg, item.attribute)
            if item.kind == "masked":
                shown = "••••" if configured else ""
            elif item.kind == "minutes" and configured:
                shown = str(int(raw) // 60)
            else:
                shown = str(raw) if configured else ""
            readonly.append(
                {
                    "env_name": item.env_name,
                    "label": item.label,
                    "note": item.note,
                    "value": shown,
                    "configured": configured,
                }
            )
        services.append(
            {
                "key": service.key,
                "title": service.title,
                "icon": service.icon,
                "summary": service.summary,
                "state": _service_state(fields),
                "fields": fields,
                "readonly": readonly,
            }
        )
    return {
        "encryption_ready": encryption_ready(),
        "public_base_url": cfg.public_base_url,
        "services": services,
    }


def validate_secret(db: Session, secret: SecretSpec, value: str, cfg: Settings | None = None) -> None:
    """Raise ValueError with a safe code when the value may not be stored."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("empty_secret_value")
    if not secret.editable:
        raise ValueError("secret_is_read_only")
    if not secret.pattern.fullmatch(cleaned):
        raise ValueError(secret.invalid_code)
    if cfg is not None:
        missing = [name for name, attribute in _required_attributes(secret) if not _cfg_has(cfg, attribute)]
        if missing:
            raise ValueError("otp_pepper_required")


def set_secret(
    db: Session, secret: SecretSpec, value: str, cfg: Settings | None = None
) -> PaymentSecretRecord:
    """Encrypt and store (or rotate) one credential. Never returns the value."""
    validate_secret(db, secret, value, cfg)
    if not encryption_ready():
        raise ValueError("settings_encryption_not_configured")
    cleaned = value.strip()
    ciphertext = encrypt_secret(cleaned)
    record = _record(db, secret.storage_id)
    if record is None:
        record = PaymentSecretRecord(
            id=secret.storage_id, ciphertext=ciphertext, hint=secret_hint(cleaned)
        )
        db.add(record)
    else:
        record.ciphertext = ciphertext
        record.hint = secret_hint(cleaned)
    # A new value invalidates the previous connection test.
    check = _check_state(db, secret.storage_id)
    if check is not None:
        db.delete(check)
    db.commit()
    return record


def clear_secret(db: Session, secret: SecretSpec) -> bool:
    """Delete the stored override so the environment value applies again."""
    record = _record(db, secret.storage_id)
    removed = record is not None
    if record is not None:
        db.delete(record)
    check = _check_state(db, secret.storage_id)
    if check is not None:
        db.delete(check)
    if removed or check is not None:
        db.commit()
    return removed


def record_check(db: Session, storage_id: str, ok: bool, code: str) -> dict[str, object]:
    """Persist the outcome of a real connection test."""
    record = _check_state(db, storage_id)
    now = datetime.now(timezone.utc)
    if record is None:
        record = ServiceCheckRecord(storage_id=storage_id, ok=ok, code=code, checked_at=now)
        db.add(record)
    else:
        record.ok = ok
        record.code = code
        record.checked_at = now
    db.commit()
    return _check_payload(db, storage_id)
