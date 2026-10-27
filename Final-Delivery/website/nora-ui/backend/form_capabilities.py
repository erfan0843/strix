"""Public, secret-free capability contract for the web form builder.

This is deliberately narrower than the legacy bot's field catalogue: a type is
advertised here only according to the current FastAPI public-response path.
"""

from __future__ import annotations

from typing import Any

from .responses import SUPPORTED_PUBLIC_FIELD_TYPES, UNSUPPORTED_FIELD_TYPES
from .schemas import MODELS


MODEL_ORDER = (
    "registration",
    "questionnaire",
    "survey",
    "contest",
    "exam",
    "attendance",
    "datacollect",
    "order",
    "election",
)
MODEL_LABELS = {
    "registration": "ثبت‌نام",
    "questionnaire": "پرسشنامه",
    "survey": "نظرسنجی",
    "contest": "مسابقه",
    "exam": "آزمون",
    "attendance": "حضور و غیاب",
    "datacollect": "ثبت اطلاعات",
    "order": "سفارش",
    "election": "رأی‌گیری",
}

FIELD_LIMITATIONS = {
    "amount": "فقط پاسخ عددی است؛ پرداخت یا محاسبهٔ صورتحساب نیست.",
    "coupon": "کد تخفیف به‌عنوان پرسش مستقل پشتیبانی نمی‌شود؛ کد تخفیف مالی تنظیم جداگانه‌ای است.",
    "email": "قالب پایه بررسی می‌شود؛ مالکیت نشانی تأیید نمی‌شود.",
    "imgchoice": "گزینه‌ها متنی‌اند؛ تصویر به گزینه وصل نیست.",
    "location": "متن آزاد است؛ GPS یا نقشه فعال نیست.",
    "mobile": "قالب شماره بررسی می‌شود؛ پیامک یا مالکیت شماره تأیید نمی‌شود.",
    "nid": "قالب/طول بررسی می‌شود؛ هویت یا رقم کنترل کد ملی تأیید نمی‌شود.",
    "price": "قیمت‌گذاری مستقل پشتیبانی نمی‌شود؛ مبلغ فرم باید از بخش مالی مجاز بیاید.",
    "slot": "پاسخ ساعت ثبت می‌شود؛ رزرو یا قفل ظرفیت زمانی نیست.",
    "terms": "پاسخ ثبت می‌شود؛ امضای دیجیتال یا پذیرش حقوقیِ مستقل ایجاد نمی‌کند.",
    "time": "پاسخ ساعت ثبت می‌شود؛ نوبت یا ظرفیت زمانی رزرو نمی‌شود.",
    "datetime": "تاریخ و ساعت به‌صورت پاسخ ثبت می‌شود؛ زمان‌بندی انتشار فرم نیست.",
    "uni": "نام به‌صورت متن ذخیره می‌شود؛ فهرست پیشنهادی محلی است و اعتبارسنجی بیرونی ندارد.",
    "job": "نام شغل به‌صورت پاسخ ذخیره می‌شود؛ دسته‌بندی آن گزارش سروری نمی‌سازد.",
}
UNSUPPORTED_FIELD_REASONS = {
    "image": "بارگذاری فایل عمومی به API پاسخ فرم وصل نیست.",
    "file": "بارگذاری فایل عمومی به API پاسخ فرم وصل نیست.",
    "voice": "ضبط یا بارگذاری صدای عمومی به API پاسخ فرم وصل نیست.",
    "sign": "رسم/بارگذاری امضای عمومی به API پاسخ فرم وصل نیست.",
    "price": FIELD_LIMITATIONS["price"],
    "coupon": FIELD_LIMITATIONS["coupon"],
}


def public_form_capabilities(*, api_configured: bool, bale_wallet_ready: bool) -> dict[str, Any]:
    """Return the read-only contract the UI may safely describe to its user."""
    models: list[dict[str, Any]] = []
    for key in MODEL_ORDER:
        if key not in MODELS:
            continue
        blocked = key == "order"
        generic = key not in {"registration", "order"}
        models.append({
            "id": key,
            "label": MODEL_LABELS[key],
            "status": "unavailable" if blocked else "limited" if generic else "server",
            "publishable": not blocked,
            "scope": "blocked" if blocked else "generic_response" if generic else "registration_workflow",
            "reason": (
                "ثبت سفارش بدون گردش پرداخت و سفارش پشتیبانی‌شده در سرور قابل انتشار نیست."
                if blocked else
                "پاسخ عمومی سروری پشتیبانی می‌شود؛ رفتار تخصصی این مدل (مانند نمره‌دهی، رأی یکتا، حضور یا رتبه‌بندی) فعال نیست."
                if generic else
                "پاسخ‌گیری سروری؛ ظرفیت و صف انتظار، همراهانِ معتبر و بلیت ثبت‌نام با شروط همان فرم پشتیبانی می‌شوند."
            ),
        })

    field_types: dict[str, dict[str, str]] = {}
    known_types = sorted(SUPPORTED_PUBLIC_FIELD_TYPES | UNSUPPORTED_FIELD_TYPES)
    for field_type in known_types:
        unsupported = field_type in UNSUPPORTED_FIELD_TYPES or field_type not in SUPPORTED_PUBLIC_FIELD_TYPES
        limitation = FIELD_LIMITATIONS.get(field_type, "")
        reason = UNSUPPORTED_FIELD_REASONS.get(field_type, "") if unsupported else limitation
        field_types[field_type] = {
            "status": "unavailable" if unsupported else "limited" if limitation else "server",
            "reason": reason,
        }

    return {
        "version": 1,
        "source": "same_application_fastapi",
        "api_configured": bool(api_configured),
        "models": models,
        "field_types": field_types,
        "settings": {
            "capacity": {"status": "server", "reason": "ظرفیت در سرور برای هر نفر اعمال می‌شود."},
            "waitlist": {"status": "server", "reason": "صف انتظار سروری است؛ ارتقای خودکار به پذیرش انجام نمی‌شود."},
            "companions": {
                "status": "conditional",
                "models": ["registration"],
                "reason": "فقط برای ثبت‌نام، ۲ تا ۱۰ نفر، نام و موبایل، و پاسخ جداگانهٔ همراهان.",
            },
            "ticketing": {
                "status": "conditional",
                "models": ["registration"],
                "reason": "مدل بلیت پس از پذیرش پاسخ ثبت‌نام در سرور تعیین می‌شود؛ صف انتظار بلیت نمی‌گیرد.",
            },
            "survey_scoring": {
                "status": "unavailable",
                "models": ["survey"],
                "reason": "وزن پرسش و امتیاز گزینه‌ها در سرور محاسبه یا ذخیره نمی‌شود؛ امتیاز فقط در پیش‌نمایش محلی فرم‌ساز دیده می‌شود.",
            },
            "conditional_visibility": {
                "status": "server",
                "max_rules_per_field": 10,
                "requires_earlier_field": True,
                "reason": "شرط‌های یک/همه از پرسش‌های قبلی با عملگر سازگار با نوع پاسخ؛ سرور مقدار شرط و گزینه‌ها را دوباره اعتبارسنجی می‌کند.",
            },
            "card_transfer": {
                "status": "conditional",
                "models": ["registration"],
                "reason": "فقط کارت معتبر، رسید و بازبینی دستی مالک/نقش مجاز.",
            },
            "bale_wallet": {
                "status": "server" if bale_wallet_ready else "unavailable",
                "ready": bool(bale_wallet_ready),
                "reason": "صورتحساب و تأیید سروری؛ فقط با پیکربندی امن backend." if bale_wallet_ready
                else "روی این میزبان برای فرم‌ها آماده نیست؛ کلید یا توکن در مرورگر درخواست نمی‌شود.",
            },
            "discount_code": {
                "status": "conditional",
                "reason": "کد تخفیف فقط در تنظیمات مالی فرم و همراه مسیر مبلغ/پرداخت پشتیبانی‌شده است؛ نه به‌عنوان نوع پرسش مستقل.",
            },
            "schedule": {"status": "unavailable", "reason": "زمان شروع/پایان هنوز انتشار سروری را محدود نمی‌کند؛ برای انتشار باید خالی باشد."},
            "event_attendance_invite_limits": {
                "status": "unavailable",
                "reason": "محدودیت رویداد، حضور یا کد دعوت به احراز سروری وصل نیست.",
            },
            "one_response_per_person": {
                "status": "unavailable",
                "reason": "هویت عمومی پاسخ‌دهنده احراز نمی‌شود؛ این گزینه تضمین یک پاسخ برای هر شخص نیست.",
            },
            "uploads_and_field_media": {
                "status": "unavailable",
                "reason": "پیوست، رسانهٔ سؤال و بارگذاری عمومی فرم در مسیر انتشار فعال نیست.",
            },
            "phone_or_identity_verification": {
                "status": "unavailable",
                "reason": "فیلد موبایل/کد ملی به‌تنهایی پیامک یا احراز هویت نیست.",
            },
            "profile_prefill": {
                "status": "unavailable",
                "reason": "فرم عمومی ناشناس است و از پروفایل واقعی خودکار پر نمی‌شود.",
            },
            "response_list": {"status": "server", "page_size_max": 100},
            "per_form_analytics": {
                "status": "limited",
                "reason": "فهرست و شمار پاسخ سروری موجود است؛ تحلیل‌های پیشرفتهٔ قیف/هر پرسش هنوز نیست.",
            },
            "exports": {
                "status": "conditional",
                "reason": (
                    "خروجی CSV پاسخ‌ها از همین سرور ساخته می‌شود (مجوز fm_export؛ ستون‌های مالی فقط با مجوز مالی). "
                    "پرسشی که «ستون در خروجی CSV» آن خاموش است در فایل نمی‌آید ولی در فهرست پاسخ‌ها می‌ماند."
                ),
                "respects_field_col": True,
            },
            "publish_permission": {
                "status": "owner_only",
                "reason": "ذخیرهٔ پیش‌نویس می‌تواند با مجوز ساخت انجام شود؛ انتشار و توقف فقط با نشست مالک است.",
            },
        },
        "notes": [
            "پیش‌نمایش محلی درخواست ثبت پاسخ، پرداخت یا انتشار ایجاد نمی‌کند.",
            "این قرارداد توصیفی است؛ سرور هنگام ذخیره، پاسخ و انتشار قواعد را دوباره اعتبارسنجی می‌کند.",
        ],
    }
