"""Public form publication and server-side response validation helpers.

The public API accepts answers only for explicitly published forms. It is
independent of owner/profile identity: anonymous drafts are guarded by a
server-issued, HttpOnly capability cookie, while all field rules are checked
again here before anything is committed.
"""

from __future__ import annotations

import math
import re
import secrets
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .financials import (
    PaymentConfigurationError,
    calculate_payment_amount,
    normalize_financial_config,
    normalize_payment_methods,
    payment_configuration_issues,
    public_payment_configuration,
)
from .form_quality import OfflineQualityError, analyze_offline_answer
from .models import FormFieldRecord, FormRecord
from .schemas import (
    DIGIT_TRANSLATION,
    PayloadError,
    _normalize_ticketing_setting,
    _valid_condition_temporal,
)


UPLOAD_FIELD_TYPES = {"image", "file", "voice", "sign"}
UNSUPPORTED_FIELD_TYPES = UPLOAD_FIELD_TYPES | {"price", "coupon"}
SUPPORTED_PUBLIC_FIELD_TYPES = {
    "text", "area", "number", "amount", "mobile", "nid", "email", "fullname",
    "date", "time", "datetime", "slot", "choice", "multi", "dropdown", "select",
    "yesno", "imgchoice", "rating", "scale", "bars", "province", "address", "gender",
    "edu", "job", "uni", "marital", "terms", "location",
}
MAX_ANSWER_LENGTH = 4000
MAX_PUBLIC_OPTIONS = 100
MAX_PUBLIC_CAPACITY = 100_000
MAX_PUBLIC_COMPANIONS = 9


class AnswerValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("Public form answers are invalid")
        self.errors = errors


def _valid_count_setting(value: Any) -> bool:
    if value is None or value == "" or value is False:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 <= value <= MAX_PUBLIC_CAPACITY
    if isinstance(value, str) and re.fullmatch(r"\d{1,6}", value.strip()):
        return int(value.strip()) <= MAX_PUBLIC_CAPACITY
    return False


def _count_setting(value: Any, *, fallback: int = 0, ceiling: int = MAX_PUBLIC_CAPACITY) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return max(0, min(ceiling, parsed))


def _has_money_configuration(settings: dict[str, Any]) -> bool:
    financial_items = settings.get("fin")
    if isinstance(financial_items, list) and any(isinstance(item, dict) and item.get("l") for item in financial_items):
        return True
    groups = settings.get("groups")
    if isinstance(groups, list) and groups:
        return True
    coupon = settings.get("coupon")
    if isinstance(coupon, dict) and str(coupon.get("code", "")).strip():
        return True
    return bool(settings.get("sync", {}).get("money")) if isinstance(settings.get("sync"), dict) else False


def public_payment_card(settings: dict[str, Any]) -> dict[str, str] | None:
    """Return only the selected, public card destination saved with a form."""
    raw = settings.get("paymentCard")
    if not isinstance(raw, dict):
        return None
    number_value = raw.get("number")
    if not isinstance(number_value, str):
        return None
    number = re.sub(r"\D", "", number_value.translate(DIGIT_TRANSLATION))
    if len(number) != 16:
        return None
    checksum = 0
    for offset, char in enumerate(reversed(number)):
        digit = int(char)
        if offset % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    if checksum % 10:
        return None

    def clean_text(key: str) -> str:
        value = raw.get(key, "")
        if not isinstance(value, str):
            return ""
        value = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
        return value[:80]

    return {"number": number, "bank": clean_text("bank"), "holder": clean_text("holder")}


def public_payment_methods(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Expose only display copy for custom methods; never publish connection data."""
    raw_methods = settings.get("methods")
    if not isinstance(raw_methods, list):
        return []
    public_methods: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_methods[:8]):
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        method_id = raw_id.strip()[:48] if isinstance(raw_id, str) else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", method_id):
            method_id = f"custom-{index + 1}"
        if method_id in seen_ids:
            continue
        seen_ids.add(method_id)

        def clean_text(value: Any, limit: int) -> str:
            if not isinstance(value, str):
                return ""
            safe = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
            return " ".join(safe.split())[:limit]

        name = clean_text(item.get("name", item.get("label", "")), 80)
        if not name:
            continue
        description = clean_text(item.get("description", item.get("details", "")), 400)
        method_type = "gateway" if item.get("type", item.get("kind")) == "gateway" else "other"
        public_methods.append({
            "id": method_id,
            "name": name,
            "description": description,
            "type": method_type,
        })
    return public_methods


def _assigned_ticket_type(
    settings: dict[str, Any], model: str, status: str
) -> dict[str, str] | None:
    """Choose one immutable type for an accepted registration, never for a waitlist."""
    if status != "accepted" or "ticketing" not in settings:
        return None
    try:
        ticketing = _normalize_ticketing_setting(settings["ticketing"], model)
    except PayloadError:
        return None
    ticket_types = ticketing["types"]
    selected = secrets.choice(ticket_types) if ticketing["mode"] == "random" else ticket_types[0]
    return {"id": selected["id"], "name": selected["name"]}


def publication_issues(form: FormRecord, *, bale_ready: bool = False) -> list[dict[str, str]]:
    """Return invalid or unavailable settings that must be fixed before public release."""
    issues: list[dict[str, str]] = []
    settings = form.settings if isinstance(form.settings, dict) else {}
    if "ticketing" in settings:
        try:
            _normalize_ticketing_setting(settings["ticketing"], form.model)
        except PayloadError as error:
            issues.append({
                "code": error.code,
                "message": "تنظیم مدل‌های بلیت معتبر نیست؛ آن را در فرم‌ساز بازبینی کنید.",
            })
    receipt_review_required = settings.get("receiptReviewRequired", False)
    if not isinstance(receipt_review_required, bool):
        issues.append({
            "code": "invalid_receipt_review_setting",
            "message": "تنظیم دریافت فیش معتبر نیست؛ آن را در فرم‌ساز خاموش یا روشن کنید.",
        })
    elif receipt_review_required and form.model != "registration":
        issues.append({
            "code": "receipt_review_requires_registration",
            "message": "بررسی فیش فقط برای فرم ثبت‌نام قابل فعال‌کردن است.",
        })
    if receipt_review_required is True and form.model == "registration" and public_payment_card(settings) is None:
        issues.append({
            "code": "payment_card_required",
            "message": "برای دریافت فیش کارت‌به‌کارت، یک کارت فعال از روش‌های پرداخت سامانه انتخاب کنید.",
        })
    nora_pay_enabled = settings.get("noraPayEnabled", False)
    if not isinstance(nora_pay_enabled, bool):
        issues.append({
            "code": "invalid_nora_pay_setting",
            "message": "تنظیم نورا پی معتبر نیست؛ آن را در فرم‌ساز بازبینی یا خاموش کنید.",
        })
    elif nora_pay_enabled:
        issues.append({
            "code": "nora_pay_not_connected",
            "message": "کیف پول نورا پی هنوز به دفترکل و پرداخت سروری امن وصل نیست؛ فرم را تا راه‌اندازی این زیرساخت با نورا پی منتشر نکنید.",
        })
    fields = list(form.fields or [])
    if not fields:
        issues.append({"code": "empty_form", "message": "فرم دست‌کم به یک پرسش نیاز دارد."})
    if form.model == "order":
        issues.append({"code": "payment_required", "message": "فرم سفارش تا اتصال واقعی پرداخت قابل انتشار نیست."})

    limit = str(settings.get("limit", "none") or "none").strip().lower()
    if limit not in {"", "none"}:
        issues.append({
            "code": "external_limit_not_connected",
            "message": "محدودیت رویداد، حضور یا کد دعوت به سرویس احراز وصل نیست؛ محدودیت را روی «بدون محدودیت» بگذارید.",
        })
    if str(settings.get("start", "") or "").strip() or str(settings.get("ends", settings.get("end", "")) or "").strip():
        issues.append({
            "code": "schedule_not_connected",
            "message": "بازهٔ زمانی هنوز در سرور اجرا نمی‌شود؛ تاریخ شروع و پایان را پاک کنید.",
        })
    guests_on = settings.get("guestsOn", False)
    if not isinstance(guests_on, bool):
        issues.append({
            "code": "invalid_companion_setting",
            "message": "تنظیم همراهان معتبر نیست؛ آن را در فرم‌ساز بازبینی کنید.",
        })
    elif guests_on:
        companion_mode = settings.get("compFields")
        max_per = _count_setting(settings.get("maxPer"), fallback=1, ceiling=MAX_PUBLIC_COMPANIONS + 1)
        if companion_mode != "name-mobile-answers":
            issues.append({
                "code": "companion_answers_required",
                "message": "برای ثبت سروری، «پاسخ جداگانه برای هر پرسش» را برای همراهان انتخاب کنید.",
            })
        else:
            labels = [re.sub(r"[\u200c\u064b-\u065f]", " ", str(field.label or "")) for field in fields]
            labels = [" ".join(label.split()) for label in labels]
            has_name = any(
                str(field.field_type or "").strip().lower() == "fullname"
                or label in {"نام", "نام کامل", "نام و نام خانوادگی"}
                for field, label in zip(fields, labels)
            )
            has_mobile = any(
                str(field.field_type or "").strip().lower() == "mobile"
                or re.search(r"(?:موبایل|تلفن|شماره\s*(?:تماس|همراه))", label, re.IGNORECASE)
                for field, label in zip(fields, labels)
            )
            if not has_name or not has_mobile:
                issues.append({
                    "code": "companion_identity_questions_required",
                    "message": "برای افزودن همراه، فرم باید سؤال نام و شمارهٔ همراه داشته باشد.",
                })
        if max_per < 2 or max_per > MAX_PUBLIC_COMPANIONS + 1:
            issues.append({
                "code": "invalid_companion_limit",
                "message": "تعداد کل افراد باید بین ۲ تا ۱۰ نفر باشد.",
            })
    payment_messages = {
        "payment_method_required": "برای فرم مبلغ‌دار، کارت‌به‌کارت یا کیف پول بله را در تنظیم روش‌های پرداخت انتخاب کنید.",
        "payment_amount_required": "برای روش پرداخت انتخاب‌شده، دست‌کم یک مبلغ مثبت تعریف کنید.",
        "card_transfer_receipt_required": "کارت‌به‌کارت فقط همراه بارگذاری فیش و بازبینی دستی فعال می‌شود.",
        "card_transfer_not_selected": "دریافت فیش را خاموش کنید یا کارت‌به‌کارت را به روش‌های فعال فرم اضافه کنید.",
        "bale_payment_not_configured": "پرداخت بله تا پیکربندی امن bot اختصاصی، provider token و webhook روی سرور قابل انتشار نیست.",
        "invalid_payment_methods": "روش‌های پرداخت فرم معتبر نیستند؛ فقط کارت‌به‌کارت و کیف پول بله پشتیبانی می‌شوند.",
        "invalid_financial_items": "فهرست مبلغ‌ها معتبر نیست؛ مبالغ را در فرم‌ساز بازبینی کنید.",
        "invalid_financial_item": "یکی از مبالغ یا توضیحات مالی معتبر نیست.",
        "invalid_financial_groups": "گروه‌های انتخاب مالی معتبر نیستند.",
        "invalid_financial_group": "یکی از گروه‌های انتخاب مالی معتبر نیست.",
        "financial_item_in_multiple_groups": "هر مورد مالی فقط می‌تواند در یک گروه انتخاب باشد.",
        "financial_group_mismatch": "گروه یک مورد مالی با گروه‌های فرم‌ساز هم‌خوان نیست.",
        "invalid_coupon": "کد تخفیف معتبر نیست.",
    }
    for code in payment_configuration_issues(settings, bale_ready=bale_ready):
        if code == "invalid_receipt_review_setting" and any(
            item.get("code") == code for item in issues
        ):
            continue
        issues.append({"code": code, "message": payment_messages.get(
            code, "تنظیم‌های مالی معتبر نیستند؛ فرم‌ساز را بازبینی کنید."
        )})
    if str(settings.get("introMedia", "") or "").strip():
        issues.append({
            "code": "media_not_connected",
            "message": "بارگذاری رسانهٔ توضیحات هنوز فعال نیست؛ رسانه را بردارید و توضیح متنی بنویسید.",
        })
    if not _valid_count_setting(settings.get("cap", 0)):
        issues.append({"code": "invalid_capacity", "message": "ظرفیت فرم معتبر نیست."})
    if not _valid_count_setting(settings.get("wait", 0)):
        issues.append({"code": "invalid_waitlist", "message": "ظرفیت صف انتظار معتبر نیست."})
    cap = _count_setting(settings.get("cap", 0), fallback=0)
    wait = _count_setting(settings.get("wait", 0), fallback=0)
    if wait > 0 and cap <= 0:
        issues.append({"code": "waitlist_requires_capacity", "message": "برای فعال‌کردن صف انتظار، ابتدا ظرفیت اصلی را مشخص کنید."})

    for field in fields:
        field_type = str(field.field_type or "").strip().lower()
        config = field.config if isinstance(field.config, dict) else {}
        if field_type not in SUPPORTED_PUBLIC_FIELD_TYPES:
            issues.append({
                "code": "field_type_not_supported",
                "field_id": field.field_key,
                "message": f"نوع پرسش «{field.label}» هنوز در پاسخ‌گیری سروری پشتیبانی نمی‌شود.",
            })
        if field_type in UNSUPPORTED_FIELD_TYPES:
            issues.append({
                "code": "file_or_financial_field_not_connected",
                "field_id": field.field_key,
                "message": f"پیوست یا ورودی مالیِ «{field.label}» هنوز به سرور وصل نیست.",
            })
        for flag in ("req", "required", "verify", "prof", "col", "scoreOn"):
            if config.get(flag) is not None and not isinstance(config.get(flag), bool):
                issues.append({
                    "code": "invalid_field_configuration",
                    "field_id": field.field_key,
                    "message": f"تنظیم «{field.label}» مقدار درست/نادرست ندارد؛ فرم را در فرم‌ساز اصلاح کنید.",
                })
                break
        if config.get("verify") is True:
            issues.append({
                "code": "verification_not_connected",
                "field_id": field.field_key,
                "message": f"تأیید مالکیت یا هویت برای «{field.label}» وصل نیست؛ درخواست تأیید را بردارید.",
            })
        if field_type in {"number", "amount", "rating", "scale", "bars"}:
            try:
                minimum = _localized_decimal(config["min"]) if config.get("min") not in (None, "") else None
                maximum = _localized_decimal(config["max"]) if config.get("max") not in (None, "") else None
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValueError("minimum_exceeds_maximum")
                if field_type == "amount" and minimum is not None and minimum < 0:
                    raise ValueError("amount_range")
                if field_type == "rating" and (
                    minimum is not None and not Decimal(1) <= minimum <= Decimal(5)
                    or maximum is not None and not Decimal(1) <= maximum <= Decimal(5)
                ):
                    raise ValueError("rating_range")
            except (ValueError, TypeError, OverflowError):
                issues.append({
                    "code": "invalid_numeric_range",
                    "field_id": field.field_key,
                    "message": f"بازهٔ عددی پرسش «{field.label}» معتبر نیست.",
                })
        if str(config.get("media", "none") or "none").lower() not in {"", "none"}:
            issues.append({
                "code": "media_not_connected",
                "field_id": field.field_key,
                "message": f"رسانهٔ پرسش «{field.label}» روی سرور وجود ندارد؛ رسانه را بردارید.",
            })
    # Keep the response bounded and avoid sending duplicate explanations.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.get("code", ""), issue.get("field_id", ""))
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique


def _option_labels(config: dict[str, Any], field_type: str) -> list[str]:
    raw = config.get("opts", config.get("options", []))
    labels: list[str] = []
    if isinstance(raw, list):
        for item in raw[:MAX_PUBLIC_OPTIONS]:
            label = item.get("l") if isinstance(item, dict) else item
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())
    if labels:
        return labels
    return {
        "gender": ["زن", "مرد", "ترجیح می‌دهم نگویم"],
        "marital": ["مجرد", "متأهل", "ترجیح می‌دهم نگویم"],
        "yesno": ["بله", "خیر"],
    }.get(field_type, [])


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or isinstance(value, list) and not value


def _text_value(value: Any, field: FormFieldRecord, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError("متن این پاسخ معتبر نیست.")
    value = value.strip()
    if len(value) > max_length or len(value) > MAX_ANSWER_LENGTH:
        raise ValueError(f"پاسخ «{field.label}» از سقف مجاز طولانی‌تر است.")
    if any(ord(char) == 0 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError(f"پاسخ «{field.label}» نویسهٔ پشتیبانی‌نشده دارد.")
    return value


def _localized_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("مقدار باید عدد معتبر باشد.")
    raw = str(value).translate(DIGIT_TRANSLATION).replace("٫", ".").replace("٬", "").replace(",", "").strip()
    if len(raw) > 100 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", raw):
        raise ValueError("مقدار باید عدد معتبر باشد.")
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        raise ValueError("مقدار باید عدد معتبر باشد.") from None
    if not parsed.is_finite() or abs(parsed) > Decimal("1000000000000"):
        raise ValueError("مقدار عددی خارج از بازهٔ مجاز است.")
    return parsed


def _temporal_parts(field_type: str, value: str) -> tuple[int, ...] | None:
    normalized = value.translate(DIGIT_TRANSLATION).strip()
    if not _valid_condition_temporal(normalized, field_type):
        return None
    numbers = [int(part) for part in re.findall(r"\d+", normalized)]
    return tuple(numbers)


def _condition_rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    rules = config.get("conditions")
    if isinstance(rules, list) and rules:
        return rules[:10]
    field = config.get("condField", config.get("cond_field", ""))
    if field:
        return [{
            "field": field,
            "op": config.get("condOp", config.get("cond_op", "eq")),
            "value": config.get("condVal", config.get("cond_val", "")),
        }]
    return []


def _matches_condition(
    rule: dict[str, Any],
    fields_by_key: dict[str, FormFieldRecord],
    values: dict[str, Any],
    visibility: dict[str, bool],
) -> bool:
    source_id = str(rule.get("field", rule.get("fieldId", rule.get("condField", ""))))
    source = fields_by_key.get(source_id)
    if source is None or not visibility.get(source_id, False):
        return False
    source_value = values.get(source_id)
    source_type = str(source.field_type or "").strip().lower()
    operator = str(rule.get("op", rule.get("operator", "eq")))
    rhs = str(rule.get("value", "") or "").strip()
    if isinstance(source_value, list):
        empty = not source_value
    else:
        empty = source_value is None or str(source_value).strip() == ""
    if operator == "empty":
        return empty
    if operator == "nempty":
        return not empty
    if empty or not rhs:
        return False
    if source_type == "multi":
        includes = rhs in (source_value if isinstance(source_value, list) else [])
        return includes if operator == "contains" else not includes if operator == "ncontains" else False
    left = str(source_value).strip()
    if source_type in {"number", "amount", "price", "rating", "scale", "bars"}:
        try:
            a, b = _localized_decimal(left), _localized_decimal(rhs)
        except ValueError:
            return False
        return {
            "eq": a == b, "ne": a != b, "gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b,
        }.get(operator, False)
    if source_type in {"date", "time", "datetime", "slot"}:
        temporal_left, temporal_right = _temporal_parts(source_type, left), _temporal_parts(source_type, rhs)
        if temporal_left is None or temporal_right is None or len(temporal_left) != len(temporal_right):
            return False
        return {
            "eq": temporal_left == temporal_right, "ne": temporal_left != temporal_right, "gt": temporal_left > temporal_right, "gte": temporal_left >= temporal_right, "lt": temporal_left < temporal_right, "lte": temporal_left <= temporal_right,
        }.get(operator, False)
    text_left, text_right = left.casefold(), rhs.casefold()
    return {
        "eq": text_left == text_right,
        "ne": text_left != text_right,
        "contains": text_right in text_left,
        "ncontains": text_right not in text_left,
        "starts": text_left.startswith(text_right),
        "nstarts": not text_left.startswith(text_right),
        "ends": text_left.endswith(text_right),
        "nends": not text_left.endswith(text_right),
    }.get(operator, False)


def _check_answer_quality(value: Any, field: FormFieldRecord, *, partial: bool) -> None:
    if partial:
        return
    finding = next((
        item for item in analyze_offline_answer(
            str(field.field_type or ""), str(field.label or ""), str(field.field_key or ""), value
        ) if item.severity == "error"
    ), None)
    if finding is not None:
        raise OfflineQualityError(finding)


def _field_value(value: Any, field: FormFieldRecord, *, partial: bool = False) -> Any:
    field_type = str(field.field_type or "").strip().lower()
    config = field.config if isinstance(field.config, dict) else {}
    if field_type not in SUPPORTED_PUBLIC_FIELD_TYPES:
        raise ValueError("نوع این پاسخ روی سرور پشتیبانی نمی‌شود.")

    if field_type == "multi":
        if isinstance(value, str):
            parts = [part.strip() for part in re.split(r"[,،]", value) if part.strip()]
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            parts = [item.strip() for item in value if item.strip()]
        else:
            raise ValueError("انتخاب‌های این پاسخ معتبر نیستند.")
        if len(parts) > MAX_PUBLIC_OPTIONS or len(parts) != len(set(parts)):
            raise ValueError("انتخاب‌های تکراری یا بیش از حد مجازند.")
        options = _option_labels(config, field_type)
        if not options or any(item not in options for item in parts):
            raise ValueError("یکی از گزینه‌های انتخاب‌شده در فرم وجود ندارد.")
        minimum, maximum = config.get("minSelect"), config.get("maxSelect")
        if not partial and minimum not in (None, "") and len(parts) < int(minimum):
            raise ValueError(f"برای «{field.label}» دست‌کم {minimum} گزینه لازم است.")
        if maximum not in (None, "") and len(parts) > int(maximum):
            raise ValueError(f"برای «{field.label}» حداکثر {maximum} گزینه مجاز است.")
        _check_answer_quality(parts, field, partial=partial)
        return parts

    if field_type in {"number", "amount", "rating", "scale", "bars"}:
        decimal = _localized_decimal(value)
        minimum = config.get("min")
        maximum = config.get("max")
        if field_type == "amount" and minimum in (None, ""):
            minimum = 0
        if field_type == "rating":
            minimum = 1 if minimum in (None, "") else minimum
            maximum = 5 if maximum in (None, "") else maximum
        if field_type in {"scale", "bars"}:
            minimum = 0 if minimum in (None, "") else minimum
            maximum = 10 if maximum in (None, "") else maximum
        try:
            if minimum not in (None, "") and decimal < _localized_decimal(minimum):
                raise ValueError(f"حداقل مقدار «{field.label}» رعایت نشده است.")
            if maximum not in (None, "") and decimal > _localized_decimal(maximum):
                raise ValueError(f"حداکثر مقدار «{field.label}» رعایت نشده است.")
        except ValueError as error:
            if str(error).startswith(("حداقل مقدار", "حداکثر مقدار")):
                raise
            raise ValueError("بازهٔ عددی این پرسش معتبر نیست.") from None
        answer = str(value).strip()
        _check_answer_quality(answer, field, partial=partial)
        return answer

    if field_type in {"choice", "dropdown", "select", "yesno", "imgchoice", "gender", "marital"}:
        answer = _text_value(value, field, max_length=MAX_ANSWER_LENGTH)
        options = _option_labels(config, field_type)
        if not options or answer not in options:
            raise ValueError("یکی از گزینه‌های فرم را انتخاب کنید.")
        _check_answer_quality(answer, field, partial=partial)
        return answer

    if field_type == "terms":
        answer = _text_value(value, field, max_length=32)
        if answer not in {"پذیرفتم", "1", "true", "on"}:
            raise ValueError("برای ادامه، پذیرش این مورد لازم است.")
        _check_answer_quality(answer, field, partial=partial)
        return "پذیرفتم"

    limits = {
        "text": 1000, "area": 3000, "address": 1000, "location": 180,
        "fullname": 120, "mobile": 20, "nid": 10, "email": 254,
        "date": 32, "time": 16, "slot": 16, "datetime": 48,
        "province": 160, "edu": 200, "job": 200, "uni": 200,
    }
    answer = _text_value(value, field, max_length=limits.get(field_type, MAX_ANSWER_LENGTH))
    if field_type in {"date", "time", "datetime", "slot"} and not _valid_condition_temporal(answer, field_type):
        raise ValueError("تاریخ یا زمان کامل و معتبر نیست.")
    if field_type == "mobile":
        raw = answer.translate(DIGIT_TRANSLATION)
        if len(raw) > 20 or not re.fullmatch(r"\+?[0-9\s().-]+", raw):
            raise ValueError("شمارهٔ همراه را با قالب معتبر و بدون نویسهٔ دیگر وارد کنید.")
        number = re.sub(r"[\s().-]", "", raw).removeprefix("+")
        if number.startswith("0098") and len(number) == 14:
            number = "0" + number[4:]
        elif number.startswith("98") and len(number) == 12:
            number = "0" + number[2:]
        elif len(number) == 10 and number.startswith("9"):
            number = "0" + number
        if partial and not re.fullmatch(r"09\d{9}", number):
            return answer
        if not re.fullmatch(r"09\d{9}", number):
            raise ValueError("شمارهٔ همراه ایران را با ۰۹، +۹۸ یا ۰۰۹۸ کامل وارد کنید.")
    if field_type == "nid" and not re.fullmatch(r"\d{10}", answer.translate(DIGIT_TRANSLATION)):
        raise ValueError("کد ملی باید ده رقم باشد؛ هویت یا مالکیت آن تأیید نمی‌شود.")
    if field_type == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", answer):
        raise ValueError("قالب ایمیل کامل نیست.")
    _check_answer_quality(answer, field, partial=partial)
    return answer


def _validate_answers_with_visibility(
    fields: Iterable[FormFieldRecord], raw_answers: Any, *, partial: bool
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(raw_answers, dict):
        raise AnswerValidationError([{"code": "answers_object_required", "message": "پاسخ‌ها باید یک شیء معتبر باشند."}])
    fields = list(fields)
    fields_by_key = {field.field_key: field for field in fields}
    unknown = set(raw_answers) - set(fields_by_key)
    if unknown:
        raise AnswerValidationError([{"code": "unknown_answer_field", "message": "فرم تغییر کرده است؛ صفحه را تازه کنید."}])

    normalized: dict[str, Any] = {}
    visible: dict[str, bool] = {}
    visible_keys: list[str] = []
    errors: list[dict[str, str]] = []
    for field in fields:
        key = field.field_key
        config = field.config if isinstance(field.config, dict) else {}
        rules = _condition_rules(config)
        is_visible = True
        if rules:
            results = [_matches_condition(rule, fields_by_key, normalized, visible)
                       for rule in rules if isinstance(rule, dict)]
            logic = config.get("conditionLogic", config.get("condLogic", "all"))
            is_visible = bool(results) and (any(results) if logic == "any" else all(results))
        visible[key] = is_visible
        if not is_visible:
            continue
        visible_keys.append(key)

        has_value = key in raw_answers
        value = raw_answers.get(key)
        required = config.get("req") is True or config.get("required") is True
        blank = not has_value or _is_blank(value) or isinstance(value, str) and not value.strip()
        if blank:
            if required and not partial:
                errors.append({
                    "field_id": key,
                    "code": "required",
                    "message": f"«{field.label}» اجباری است.",
                })
            continue
        try:
            normalized[key] = _field_value(value, field, partial=partial)
        except OfflineQualityError as error:
            errors.append({
                "field_id": key,
                "code": error.code,
                "message": str(error)[:240],
            })
        except (ValueError, TypeError, OverflowError) as error:
            errors.append({
                "field_id": key,
                "code": "invalid_value",
                "message": str(error)[:240],
            })
    if errors:
        raise AnswerValidationError(errors[:30])
    return normalized, visible_keys


def validate_answers(
    fields: Iterable[FormFieldRecord], raw_answers: Any, *, partial: bool
) -> dict[str, Any]:
    """Normalize answers using the same ordered visibility rules as publication."""
    return _validate_answers_with_visibility(fields, raw_answers, partial=partial)[0]


def _canonical_companion_mobile(value: str) -> str:
    raw = value.translate(DIGIT_TRANSLATION)
    number = re.sub(r"[\s().-]", "", raw).removeprefix("+")
    if number.startswith("0098") and len(number) == 14:
        number = "0" + number[4:]
    elif number.startswith("98") and len(number) == 12:
        number = "0" + number[2:]
    elif len(number) == 10 and number.startswith("9"):
        number = "0" + number
    return number


def validate_companions(
    fields: Iterable[FormFieldRecord],
    raw_companions: Any,
    settings: dict[str, Any],
    *,
    partial: bool,
) -> list[dict[str, Any]]:
    """Validate companion identity and run each companion through the form rules."""
    if raw_companions is None:
        raw_companions = []
    if not isinstance(raw_companions, list):
        raise AnswerValidationError([{
            "code": "companions_array_required",
            "message": "فهرست همراهان معتبر نیست.",
        }])
    enabled = settings.get("guestsOn") is True
    if not enabled:
        if raw_companions:
            raise AnswerValidationError([{
                "code": "companions_not_enabled",
                "message": "افزودن همراه برای این فرم فعال نیست.",
            }])
        return []
    if settings.get("compFields") != "name-mobile-answers":
        raise AnswerValidationError([{
            "code": "companion_answers_required",
            "message": "پاسخ جداگانهٔ همراهان برای این فرم فعال نیست.",
        }])
    max_per = _count_setting(settings.get("maxPer"), fallback=1, ceiling=MAX_PUBLIC_COMPANIONS + 1)
    max_companions = max(0, min(MAX_PUBLIC_COMPANIONS, max_per - 1))
    errors: list[dict[str, Any]] = []
    if len(raw_companions) > max_companions:
        errors.append({
            "code": "companion_limit_exceeded",
            "message": f"حداکثر {max_companions} همراه برای این فرم پذیرفته می‌شود.",
        })
    mobile_field = FormFieldRecord(
        field_key="companion_mobile", position=0, field_type="mobile", label="موبایل همراه", config={}
    )
    used_mobiles: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_companions[:MAX_PUBLIC_COMPANIONS]):
        if not isinstance(raw, dict) or set(raw) - {"name", "mobile", "answers"}:
            errors.append({
                "code": "invalid_companion",
                "companion_index": index,
                "message": "اطلاعات همراه معتبر نیست.",
            })
            continue
        try:
            raw_name = raw.get("name", "") if partial else raw.get("name")
            if partial and raw_name is None:
                raw_name = ""
            name = _text_value(raw_name, FormFieldRecord(
                field_key="companion_name", position=0, field_type="fullname", label="نام همراه", config={}
            ), max_length=120)
            name = " ".join(name.split())
            if not partial:
                blocking_finding = next((
                    finding for finding in analyze_offline_answer(
                        "fullname", "نام همراه", "companion_name", name
                    ) if finding.severity == "error"
                ), None)
                if blocking_finding is not None:
                    raise OfflineQualityError(blocking_finding)
                if len(name) < 3:
                    raise ValueError("نام همراه را کامل بنویسید.")
            raw_mobile = raw.get("mobile", "") if partial else raw.get("mobile")
            if partial and raw_mobile is None:
                raw_mobile = ""
            mobile = "" if partial and raw_mobile == "" else _field_value(raw_mobile, mobile_field, partial=partial)
            canonical_mobile = _canonical_companion_mobile(mobile)
            if not partial and canonical_mobile in used_mobiles:
                raise ValueError("این شمارهٔ همراه برای همراه دیگری هم ثبت شده است.")
            if not partial:
                used_mobiles.add(canonical_mobile)
            mobile = canonical_mobile if re.fullmatch(r"09\d{9}", canonical_mobile) else mobile
        except (ValueError, TypeError, OverflowError) as error:
            errors.append({
                "code": error.code if isinstance(error, OfflineQualityError) else "invalid_companion_identity",
                "companion_index": index,
                "message": str(error)[:240],
            })
            continue
        raw_answers = raw.get("answers", {})
        try:
            answers = validate_answers(fields, raw_answers, partial=partial)
        except AnswerValidationError as error:
            errors.extend({**issue, "companion_index": index} for issue in error.errors)
            continue
        normalized.append({"name": name, "mobile": mobile, "answers": answers})
    if errors:
        raise AnswerValidationError(errors[:30])
    return normalized


def visible_field_ids(fields: Iterable[FormFieldRecord], raw_answers: Any) -> list[str]:
    """Return the server-evaluated visible field keys for a saved partial draft."""
    return _validate_answers_with_visibility(fields, raw_answers, partial=True)[1]


def public_form_data(
    form: FormRecord,
    *,
    accepted_count: int = 0,
    waitlisted_count: int = 0,
    bale_ready: bool = False,
) -> dict[str, Any]:
    """Return only configuration needed by the public response page."""
    settings = form.settings if isinstance(form.settings, dict) else {}
    try:
        payment_config = public_payment_configuration(settings, bale_ready=bale_ready)
    except PaymentConfigurationError:
        payment_config = {"fin": [], "groups": [], "coupon": {"code": "", "off": 0, "all": False}, "enabledPaymentMethods": [], "receiptUploadRequired": False}
    public_settings: dict[str, Any] = {
        "display": settings.get("display") if settings.get("display") in {"all", "one"} else "one",
        "dir": settings.get("dir") if settings.get("dir") in {"rtl", "ltr"} else "rtl",
        "after": settings.get("after") if settings.get("after") in {"edit", "view"} else "view",
        "profilePrefill": False,
        "onePerPerson": False,
        "limit": "none",
        "guestsOn": settings.get("guestsOn") is True,
        "maxPer": _count_setting(settings.get("maxPer"), fallback=1, ceiling=MAX_PUBLIC_COMPANIONS + 1),
        "compFields": settings.get("compFields") if settings.get("guestsOn") is True and settings.get("compFields") == "name-mobile-answers" else "",
        "cap": _count_setting(settings.get("cap", 0)),
        "wait": _count_setting(settings.get("wait", 0)) if _count_setting(settings.get("cap", 0)) else 0,
        "taken": accepted_count,
        "waitTaken": waitlisted_count,
        "notify": {"on": False},
        "methods": public_payment_methods(settings),
        "fin": payment_config["fin"],
        "groups": payment_config["groups"],
        "coupon": payment_config["coupon"],
        "enabledPaymentMethods": payment_config["enabledPaymentMethods"],
        "receiptUploadRequired": payment_config["receiptUploadRequired"],
    }
    if payment_config["receiptUploadRequired"]:
        card = public_payment_card(settings)
        if card is not None:
            public_settings["paymentCard"] = card
        raw_instructions = settings.get("paymentInstructions")
        if isinstance(raw_instructions, str):
            instructions = raw_instructions.replace("\r\n", "\n").replace("\r", "\n")
            instructions = "".join(
                char for char in instructions if char in "\n\t" or ord(char) >= 32 and ord(char) != 127
            )
            instructions = "\n".join(line.rstrip() for line in instructions.split("\n")).strip()[:500]
            if instructions:
                public_settings["paymentInstructions"] = instructions
    for key, limit in (("intro", 1500), ("endText", 1500)):
        value = settings.get(key)
        if isinstance(value, str):
            public_settings[key] = value[:limit]
    raw_links = settings.get("links")
    if isinstance(raw_links, list):
        public_settings["links"] = [
            {"t": str(item.get("t", ""))[:120], "u": str(item.get("u", ""))[:2048],
             "i": str(item.get("i", "i-link"))[:48]}
            for item in raw_links[:10]
            if isinstance(item, dict) and isinstance(item.get("t", ""), str) and isinstance(item.get("u", ""), str)
        ]
    public_field_keys = {
        "req", "required", "help", "placeholder", "opts", "options", "min", "max",
        "minSelect", "maxSelect", "conditions", "conditionLogic", "condField", "condOp",
        "condVal", "weight", "scoreOn", "scoreType", "col", "prof",
    }
    fields = []
    for field in form.fields:
        config = field.config if isinstance(field.config, dict) else {}
        public_config = {key: config[key] for key in public_field_keys if key in config}
        public_config.pop("required", None)
        public_config["req"] = config.get("req") is True or config.get("required") is True
        for option_key in ("opts", "options"):
            options = public_config.get(option_key)
            if isinstance(options, list):
                public_config[option_key] = [
                    ({"l": str(item.get("l", ""))[:120], **({"score": item["score"]} if isinstance(item.get("score"), (int, float)) and not isinstance(item.get("score"), bool) else {})}
                     if isinstance(item, dict) else str(item)[:120])
                    for item in options[:MAX_PUBLIC_OPTIONS]
                ]
        conditions = public_config.get("conditions")
        if isinstance(conditions, list):
            public_config["conditions"] = [
                {"field": str(rule.get("field", ""))[:80], "op": str(rule.get("op", ""))[:16],
                 "value": str(rule.get("value", ""))[:120]}
                for rule in conditions[:10] if isinstance(rule, dict)
            ]
        fields.append({"id": field.field_key, "t": field.field_type, "l": field.label, **public_config})
    return {
        "id": form.id,
        "name": form.title,
        "model": form.model,
        "need": form.need,
        "slug": form.slug or "",
        "fields": fields,
        "settings": public_settings,
        **public_settings,
        "status": form.status,
        "version": form.version,
    }


def response_snapshot(
    form: FormRecord,
    *,
    event: dict[str, str] | None = None,
    status: str = "accepted",
    payment: dict[str, Any] | None = None,
    ticket_type: dict[str, str] | None = None,
    assign_ticket_type: bool = True,
) -> dict[str, Any]:
    settings = form.settings if isinstance(form.settings, dict) else {}
    snapshot: dict[str, Any] = {
        "id": form.id,
        "name": form.title,
        "model": form.model,
        "need": form.need,
        "version": form.version,
        "receipt_review_required": settings.get("receiptReviewRequired") is True
        and not (isinstance(payment, dict) and payment.get("method") == "bale_wallet"),
        "fields": [
            {"id": field.field_key, "type": field.field_type, "label": field.label}
            for field in form.fields
        ],
    }
    if isinstance(payment, dict):
        snapshot["payment"] = {
            key: value
            for key, value in payment.items()
            if key in {
                "method", "status", "amount", "currency", "party_count", "items", "subtotal",
                "discount_percent", "discount_amount", "coupon_applied",
            }
        }
    if assign_ticket_type:
        ticket_type = _assigned_ticket_type(settings, form.model, status)
    if ticket_type is not None:
        snapshot["ticket_type"] = ticket_type
    if event:
        snapshot["event"] = {
            key: value
            for key, value in event.items()
            if key in {"title", "date", "time"} and isinstance(value, str)
        }
    return snapshot
