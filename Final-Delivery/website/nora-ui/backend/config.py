"""Server-only configuration for the Nora form API."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .seo import normalize_local_business, normalize_public_base_url


UI_ROOT = Path(__file__).resolve().parent.parent
_FORM_PAYMENT_BOT_TOKEN = re.compile(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}\Z")
_FORM_PAYMENT_WEBHOOK_PATH = "/api/payments/bale/webhook"


def _valid_form_payment_webhook_url(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(char.isspace() for char in value)
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        reserved_suffixes = {"test", "example", "invalid", "localhost", "local", "internal", "lan"}
        if (
            len(host) > 253
            or len(labels) < 2
            or labels[-1] in reserved_suffixes
            or not any(char.isalpha() for char in labels[-1])
            or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            )
        ):
            return False
    else:
        if not address.is_global:
            return False
    return bool(
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.rstrip("/") == _FORM_PAYMENT_WEBHOOK_PATH
        and (port is None or 1 <= port <= 65535)
    )


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _cookie_samesite_env(cookie_secure: bool) -> str:
    """NORA_COOKIE_SAMESITE ∈ {strict, lax, none}; پیش‌فرض و هر مقدار نامعتبر → strict.

    «none» بدون کوکی امن را مرورگرها رد می‌کنند؛ در آن حالت هم strict می‌ماند (fail-safe).
    """
    value = (os.getenv("NORA_COOKIE_SAMESITE") or "strict").strip().lower()
    if value not in {"strict", "lax", "none"}:
        return "strict"
    if value == "none" and not cookie_secure:
        return "strict"
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    owner_id: str
    owner_username: str
    owner_password_hash: str
    public_base_url: str = ""
    seo_business_name: str = ""
    seo_business_street_address: str = ""
    seo_business_locality: str = ""
    seo_business_postal_code: str = ""
    seo_business_country_code: str = ""
    seo_business_telephone: str = ""
    seo_business_description: str = ""
    session_ttl_seconds: int = 8 * 60 * 60
    cookie_secure: bool = True
    # SameSite کوکی‌های نشست/CSRF. پیش‌فرض strict. «none» فقط برای پیش‌نمایش داخل iframe
    # (مثل محیط آزمایشی) و فقط همراه cookie_secure معنا دارد؛ در تولید دست نزنید.
    cookie_samesite: str = "strict"
    cookie_name: str = "nora_session"
    csrf_cookie_name: str = "nora_csrf"
    account_cookie_name: str = "nora_account_session"
    account_csrf_cookie_name: str = "nora_account_csrf"
    bale_bot_token: str = field(default="", repr=False)
    bale_bot_username: str = ""
    bot_service_token: str = field(default="", repr=False)
    owner_bale_user_id: str = ""
    # A dedicated payment bot avoids sharing update polling/webhooks with the legacy bot.
    form_payment_bot_token: str = field(default="", repr=False)
    form_payment_provider_token: str = field(default="", repr=False)
    form_payment_webhook_secret: str = field(default="", repr=False)
    form_payment_webhook_url: str = ""
    form_payment_ttl_seconds: int = 30 * 60
    form_payment_timeout_seconds: int = 8
    form_payment_max_amount: int = 2_000_000_000
    bale_init_data_max_age_seconds: int = 600
    max_request_bytes: int = 64 * 1024
    max_fields_per_form: int = 30
    response_draft_ttl_seconds: int = 30 * 24 * 60 * 60
    response_draft_write_limit_per_minute: int = 120
    response_submit_limit_per_minute: int = 10
    cooperation_submit_limit_per_minute: int = 5
    # Existing Safir OTP delivery settings are shared with nora_bot; API keys stay server-only.
    safir_api_key: str = field(default="", repr=False)
    safir_bot_id: str = ""
    safir_url: str = "https://safir.bale.ai/api/v3/send_message"
    safir_send_request_id: bool = True
    otp_pepper: str = field(default="", repr=False)
    otp_ttl_seconds: int = 180
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 90
    # Data-management staging lives outside UI_ROOT so the static mount can never
    # serve an uploaded backup. Empty means "<nora-ui>/../var/nora-data-staging".
    data_staging_dir: str = ""
    data_upload_max_bytes: int = 256 * 1024 * 1024
    # Phase 9.4: private file storage outside the web root for event resources larger than the
    # in-database limit. Empty = not configured (uploads stay ≤ EVENT_RESOURCE_MAX_BYTES in the DB).
    private_storage_dir: str = ""
    private_storage_max_bytes: int = 512 * 1024 * 1024
    data_staging_retention_hours: int = 72
    legacy_audit_script: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_base_url", normalize_public_base_url(self.public_base_url))
        business = normalize_local_business(
            name=self.seo_business_name,
            street_address=self.seo_business_street_address,
            locality=self.seo_business_locality,
            postal_code=self.seo_business_postal_code,
            country_code=self.seo_business_country_code,
            telephone=self.seo_business_telephone,
            description=self.seo_business_description,
        )
        for field_name, key in (
            ("seo_business_name", "name"),
            ("seo_business_street_address", "street_address"),
            ("seo_business_locality", "locality"),
            ("seo_business_postal_code", "postal_code"),
            ("seo_business_country_code", "country_code"),
            ("seo_business_telephone", "telephone"),
            ("seo_business_description", "description"),
        ):
            object.__setattr__(self, field_name, business.get(key, "") if business else "")
        if not self.data_staging_dir:
            object.__setattr__(
                self,
                "data_staging_dir",
                str(UI_ROOT.parent / "var" / "nora-data-staging"),
            )

    @property
    def seo_local_business(self) -> dict[str, str] | None:
        return normalize_local_business(
            name=self.seo_business_name,
            street_address=self.seo_business_street_address,
            locality=self.seo_business_locality,
            postal_code=self.seo_business_postal_code,
            country_code=self.seo_business_country_code,
            telephone=self.seo_business_telephone,
            description=self.seo_business_description,
        )

    @property
    def form_bale_payments_ready(self) -> bool:
        secret = self.form_payment_webhook_secret
        provider_token = self.form_payment_provider_token
        return bool(
            _FORM_PAYMENT_BOT_TOKEN.fullmatch(self.form_payment_bot_token or "")
            and provider_token
            and len(provider_token) <= 512
            and all(33 <= ord(char) <= 126 for char in provider_token)
            and 32 <= len(secret) <= 256
            and all(33 <= ord(char) <= 126 for char in secret)
            and _valid_form_payment_webhook_url(self.form_payment_webhook_url)
            and isinstance(self.form_payment_timeout_seconds, int)
            and not isinstance(self.form_payment_timeout_seconds, bool)
            and 1 <= self.form_payment_timeout_seconds <= 8
        )

    @classmethod
    def from_env(cls) -> "Settings":
        ttl = int(os.getenv("NORA_SESSION_TTL_SECONDS", str(8 * 60 * 60)))
        if not 15 * 60 <= ttl <= 24 * 60 * 60:
            raise ValueError("NORA_SESSION_TTL_SECONDS must be between 900 and 86400")
        owner_id = os.getenv("NORA_OWNER_ID", "").strip()
        username = os.getenv("NORA_OWNER_USERNAME", "").strip()
        password_hash = os.getenv("NORA_OWNER_PASSWORD_HASH", "").strip()
        bale_bot_username = os.getenv("NORA_BALE_BOT_USERNAME", "").strip().removeprefix("@")
        if bale_bot_username and not re.fullmatch(r"[A-Za-z0-9_]{3,64}", bale_bot_username):
            raise ValueError("NORA_BALE_BOT_USERNAME must be a public Bale bot username")
        bot_service_token = os.getenv("NORA_BOT_SERVICE_TOKEN", "").strip()
        owner_bale_user_id = os.getenv("NORA_OWNER_BALE_USER_ID", "").strip()
        form_payment_bot_token = os.getenv("NORA_FORM_PAYMENT_BOT_TOKEN", "").strip()
        form_payment_provider_token = os.getenv("NORA_FORM_PAYMENT_PROVIDER_TOKEN", "").strip()
        form_payment_webhook_secret = os.getenv("NORA_FORM_PAYMENT_WEBHOOK_SECRET", "").strip()
        form_payment_webhook_url = os.getenv("NORA_FORM_PAYMENT_WEBHOOK_URL", "").strip()
        if form_payment_bot_token and not _FORM_PAYMENT_BOT_TOKEN.fullmatch(form_payment_bot_token):
            raise ValueError("NORA_FORM_PAYMENT_BOT_TOKEN has an invalid Bot API token format")
        if form_payment_provider_token and (
            len(form_payment_provider_token) > 512
            or not all(33 <= ord(char) <= 126 for char in form_payment_provider_token)
        ):
            raise ValueError(
                "NORA_FORM_PAYMENT_PROVIDER_TOKEN must be printable ASCII without spaces"
            )
        if form_payment_webhook_secret and (
            not 32 <= len(form_payment_webhook_secret) <= 256
            or not all(33 <= ord(char) <= 126 for char in form_payment_webhook_secret)
        ):
            raise ValueError(
                "NORA_FORM_PAYMENT_WEBHOOK_SECRET must be 32-256 printable ASCII characters"
            )
        if form_payment_webhook_url and not _valid_form_payment_webhook_url(
            form_payment_webhook_url
        ):
            raise ValueError(
                "NORA_FORM_PAYMENT_WEBHOOK_URL must be HTTPS and end in "
                "/api/payments/bale/webhook"
            )
        if bot_service_token and len(bot_service_token) < 32:
            raise ValueError("NORA_BOT_SERVICE_TOKEN must contain at least 32 characters")
        if owner_bale_user_id and not re.fullmatch(r"[1-9][0-9]{0,19}", owner_bale_user_id):
            raise ValueError("NORA_OWNER_BALE_USER_ID must be a positive decimal Bale user ID")
        response_draft_ttl = _bounded_int_env(
            "NORA_RESPONSE_DRAFT_TTL_SECONDS", 30 * 24 * 60 * 60, 60, 365 * 24 * 60 * 60
        )
        draft_write_limit = _bounded_int_env("NORA_RESPONSE_DRAFT_WRITE_LIMIT_PER_MINUTE", 120, 1, 10000)
        submit_limit = _bounded_int_env("NORA_RESPONSE_SUBMIT_LIMIT_PER_MINUTE", 10, 1, 1000)
        cooperation_limit = _bounded_int_env("NORA_COOPERATION_SUBMIT_LIMIT_PER_MINUTE", 5, 1, 100)
        # MiB in the environment (1 MiB … 8 GiB); the production value must follow the real disk,
        # reverse-proxy body limit and backup window — see deployment/PRIVATE-STORAGE-OPERATIONS.fa.md.
        private_storage_max_mib = _bounded_int_env("NORA_PRIVATE_STORAGE_MAX_MIB", 512, 1, 8192)
        form_payment_ttl = _bounded_int_env("NORA_FORM_PAYMENT_TTL_SECONDS", 1800, 60, 24 * 60 * 60)
        form_payment_timeout = _bounded_int_env("NORA_FORM_PAYMENT_TIMEOUT_SECONDS", 8, 1, 8)
        form_payment_max_amount = _bounded_int_env(
            "NORA_FORM_PAYMENT_MAX_AMOUNT", 2_000_000_000, 1, 2_000_000_000
        )
        bale_init_data_max_age = _bounded_int_env(
            "NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", 600, 60, 3600
        )
        safir_api_key = os.getenv("SAFIR_API_KEY", "").strip()
        otp_pepper = os.getenv("NORA_OTP_PEPPER", "").strip()
        if otp_pepper and len(otp_pepper) < 32:
            raise ValueError("NORA_OTP_PEPPER must contain at least 32 characters")
        if not otp_pepper:
            # Keep existing deployments usable; set a dedicated stable pepper in production.
            otp_pepper = safir_api_key
        safir_bot_id = os.getenv("SAFIR_BOT_ID", "").strip()
        if safir_bot_id and not re.fullmatch(r"[1-9][0-9]{0,17}", safir_bot_id):
            raise ValueError("SAFIR_BOT_ID must be a positive decimal bot ID")
        safir_url = os.getenv("SAFIR_URL", "https://safir.bale.ai/api/v3/send_message").strip()
        if safir_url and not re.fullmatch(
            r"https://safir[.]bale[.]ai(?:/[^\s]*)?", safir_url, flags=re.I
        ):
            raise ValueError("SAFIR_URL must use the Safir HTTPS endpoint")
        otp_ttl_minutes = _bounded_int_env("OTP_TTL_MINUTES", 3, 1, 15)
        otp_max_attempts = _bounded_int_env("OTP_MAX_ATTEMPTS", 5, 1, 10)
        otp_resend_seconds = _bounded_int_env("OTP_RESEND_SECONDS", 90, 30, 600)
        return cls(
            database_url=os.getenv("NORA_DATABASE_URL", "").strip() or None,
            owner_id=owner_id,
            owner_username=username,
            owner_password_hash=password_hash,
            public_base_url=os.getenv("NORA_PUBLIC_BASE_URL", "").strip(),
            seo_business_name=os.getenv("NORA_SEO_BUSINESS_NAME", "").strip(),
            seo_business_street_address=os.getenv("NORA_SEO_BUSINESS_STREET_ADDRESS", "").strip(),
            seo_business_locality=os.getenv("NORA_SEO_BUSINESS_LOCALITY", "").strip(),
            seo_business_postal_code=os.getenv("NORA_SEO_BUSINESS_POSTAL_CODE", "").strip(),
            seo_business_country_code=os.getenv("NORA_SEO_BUSINESS_COUNTRY_CODE", "").strip(),
            seo_business_telephone=os.getenv("NORA_SEO_BUSINESS_TELEPHONE", "").strip(),
            seo_business_description=os.getenv("NORA_SEO_BUSINESS_DESCRIPTION", "").strip(),
            session_ttl_seconds=ttl,
            cookie_secure=_bool_env("NORA_COOKIE_SECURE", True),
            cookie_samesite=_cookie_samesite_env(_bool_env("NORA_COOKIE_SECURE", True)),
            bale_bot_token=os.getenv("NORA_BALE_BOT_TOKEN", "").strip(),
            bale_bot_username=bale_bot_username,
            bot_service_token=bot_service_token,
            owner_bale_user_id=owner_bale_user_id,
            form_payment_bot_token=form_payment_bot_token,
            form_payment_provider_token=form_payment_provider_token,
            form_payment_webhook_secret=form_payment_webhook_secret,
            form_payment_webhook_url=form_payment_webhook_url,
            form_payment_ttl_seconds=form_payment_ttl,
            form_payment_timeout_seconds=form_payment_timeout,
            form_payment_max_amount=form_payment_max_amount,
            bale_init_data_max_age_seconds=bale_init_data_max_age,
            response_draft_ttl_seconds=response_draft_ttl,
            response_draft_write_limit_per_minute=draft_write_limit,
            response_submit_limit_per_minute=submit_limit,
            cooperation_submit_limit_per_minute=cooperation_limit,
            private_storage_dir=os.getenv("NORA_PRIVATE_STORAGE_DIR", "").strip(),
            private_storage_max_bytes=private_storage_max_mib * 1024 * 1024,
            safir_api_key=safir_api_key,
            safir_bot_id=safir_bot_id,
            safir_url=safir_url or "https://safir.bale.ai/api/v3/send_message",
            safir_send_request_id=_bool_env("SAFIR_SEND_REQUEST_ID", True),
            otp_pepper=otp_pepper,
            otp_ttl_seconds=otp_ttl_minutes * 60,
            otp_max_attempts=otp_max_attempts,
            otp_resend_seconds=otp_resend_seconds,
            data_staging_dir=os.getenv("NORA_DATA_STAGING_DIR", "").strip(),
            data_upload_max_bytes=_bounded_int_env(
                "NORA_DATA_UPLOAD_MAX_BYTES", 256 * 1024 * 1024, 1024 * 1024, 4 * 1024 * 1024 * 1024
            ),
            data_staging_retention_hours=_bounded_int_env(
                "NORA_DATA_STAGING_RETENTION_HOURS", 72, 1, 24 * 90
            ),
            legacy_audit_script=os.getenv("NORA_LEGACY_AUDIT_SCRIPT", "").strip(),
        )
