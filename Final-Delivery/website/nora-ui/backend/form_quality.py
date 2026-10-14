"""Offline, deterministic quality checks for Nora public-form answers.

These checks intentionally use only the submitted value and form metadata. They
never call an AI provider, network endpoint, identity service, or university API.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_EN_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(_FA_DIGITS + _AR_DIGITS, _EN_DIGITS * 2)
_NAME_EXCLUSIONS = (
    "دانشگاه", "دانشکده", "مدرسه", "مؤسسه", "موسسه", "شرکت", "سازمان",
    "محصول", "رویداد", "عنوان", "موضوع", "کاربری", "رشته", "درس", "پروژه",
    "برند", "گروه", "طرح", "کانال", "فروشگاه", "university", "college",
    "school", "company", "organization", "institution", "product", "event",
    "title", "subject", "course", "project", "brand", "username", "user name",
)
_PLACEHOLDER_NAMES = {
    "test", "testing", "unknown", "anonymous", "anon", "none", "asdf", "qwerty", "xxx",
    "نام", "ناشناس", "بدوننام", "تست",
}
_PLACEHOLDER_VALUES = {
    "test", "testing", "testanswer", "sample", "sampletext", "example", "placeholder",
    "dummy", "unknown", "anonymous", "anon", "none", "null", "undefined", "na",
    "asdf", "asdfgh", "qwerty", "qwertyuiop", "foobar", "loremipsum", "xxx",
    "johndoe", "janedoe", "yourname", "namehere", "firstname", "lastname",
    "نام", "نامنمونه", "ناشناس", "بدوننام", "تست", "نمونه", "مثال",
    "پاسخنمونه", "متننمونه", "نامخودراواردکنید",
}
_TEXT_FIELD_TYPES = {
    "text", "area", "fullname", "uni", "job", "edu", "address", "location", "province", "coupon",
}
_PATTERN_FIELD_TYPES = _TEXT_FIELD_TYPES | {
    "number", "amount", "price", "mobile", "nid", "email", "date", "datetime", "time", "slot",
    "rating", "scale", "bars",
}
_KEYBOARD_ROWS = (
    "qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890",
    "ضصثقفغعهخحجچ", "شسیبلاتنمکگ", "ظطزرذدپو",
)
_JALALI_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
                  1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178)


@dataclass(frozen=True)
class QualityFinding:
    code: str
    severity: str
    message: str
    requires_confirmation: bool = False


class OfflineQualityError(ValueError):
    """A deterministic quality finding that must prevent final submission."""

    def __init__(self, finding: QualityFinding):
        super().__init__(finding.message)
        self.code = finding.code
        self.finding = finding


def _clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.translate(str.maketrans("يىك", "ییک", "ـ"))
    text = "".join(char for char in text if unicodedata.category(char) not in {"Mn", "Me"})
    text = text.replace("\u200c", " ").replace("\u200f", " ").replace("\u200e", " ")
    text = re.sub(r"[_-]+", " ", text)
    return " ".join(text.split())


def _quality_tokens(normalized: str) -> list[str]:
    return re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)


def _compact_alphanumeric(normalized: str) -> str:
    return "".join(char for char in normalized if char.isalnum())


def _has_repeated_sequence(tokens: list[str]) -> bool:
    for token in tokens:
        if len(token) >= 4 and len(set(token)) == 1:
            return True
        if re.search(r"(.)\1{4,}", token):
            return True
        for unit_size in (2, 3):
            if len(token) >= unit_size * 3 and len(token) % unit_size == 0:
                if token == token[:unit_size] * (len(token) // unit_size):
                    return True
    return False


def _has_keyboard_sequence(tokens: list[str]) -> bool:
    for token in tokens:
        for index in range(max(0, len(token) - 3)):
            sequence = token[index:index + 4]
            if any(sequence in row or sequence in row[::-1] for row in _KEYBOARD_ROWS):
                return True
    return False


def _is_placeholder_email(text: str) -> bool:
    local, separator, domain = text.casefold().partition("@")
    if not separator:
        return False
    normalized_domain = domain.split(".")[-2:] if "." in domain else [domain]
    compact_domain = "".join(normalized_domain)
    return (
        _compact_alphanumeric(_clean_text(local)) in _PLACEHOLDER_VALUES
        or compact_domain in {"examplecom", "exampleorg", "examplenet", "invalid", "testcom"}
    )


def is_person_name_field(field_type: str, label: str, field_key: str = "") -> bool:
    """Classify only person-name fields; names of universities/products stay out."""
    descriptor = _clean_text(f"{label} {field_key}")
    kind = str(field_type or "").strip().casefold()
    if kind == "fullname":
        return True
    if any(exclusion in descriptor for exclusion in _NAME_EXCLUSIONS):
        return False
    if kind not in {"text", "area"}:
        return False
    return bool(
        re.search(r"(?:نام|اسم)", descriptor)
        or re.search(r"\b(?:name|full name|first name|last name|participant|applicant)\b", descriptor)
    )


def is_birth_date_field(field_type: str, label: str, field_key: str = "") -> bool:
    """Birthday rules apply only to date-like fields explicitly marked as birth."""
    if str(field_type or "").strip().casefold() not in {"date", "datetime"}:
        return False
    descriptor = _clean_text(f"{label} {field_key}")
    return bool(
        re.search(r"(?:تولد|زادروز|متولد)", descriptor)
        or re.search(r"\b(?:dob|birthday|birthdate|birth date|date of birth|date born)\b", descriptor)
    )


def _is_jalali_leap(year: int) -> bool:
    if year < _JALALI_BREAKS[0] or year >= _JALALI_BREAKS[-1]:
        return False
    jp = _JALALI_BREAKS[0]
    jm = jump = 0
    leap_j = -14
    for jm in _JALALI_BREAKS[1:]:
        jump = jm - jp
        if year < jm:
            break
        leap_j += jump // 33 * 8 + (jump % 33) // 4
        jp = jm
    n = year - jp
    leap_j += n // 33 * 8 + (n % 33 + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    if jump - n < 6:
        n = n - jump + (jump + 4) // 33 * 33
    cycle = ((n + 1) % 33 - 1) % 4
    if cycle == -1:
        cycle = 4
    return cycle == 0


def _jalali_month_days(year: int, month: int) -> int:
    if 1 <= month <= 6:
        return 31
    if 7 <= month <= 11:
        return 30
    if month == 12:
        return 30 if _is_jalali_leap(year) else 29
    return 0


def gregorian_to_jalali(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Convert a Gregorian date to Jalali without an external package."""
    g_days = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2, gm2, gd2 = year - 1600, month - 1, day - 1
    g_day_no = (365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100
                + (gy2 + 399) // 400 + g_days[gm2] + gd2)
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if month > 2 and leap:
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def current_jalali_date(today: date | datetime | None = None) -> tuple[int, int, int]:
    """Return today's Jalali date in the same Asia/Tehran zone used by the form."""
    if today is None:
        current = datetime.now(ZoneInfo("Asia/Tehran")).date()
    elif isinstance(today, datetime):
        current = today.date()
    else:
        current = today
    return gregorian_to_jalali(current.year, current.month, current.day)


def _birth_date_parts(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").translate(_DIGIT_TRANSLATION).strip()
    text = re.split(r"\s*(?:ساعت|—)\s*", text, maxsplit=1)[0].strip()
    match = re.fullmatch(r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})", text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    if year >= 1900:
        try:
            return gregorian_to_jalali(year, month, day) if date(year, month, day) else None
        except ValueError:
            return None
    if day < 1 or day > _jalali_month_days(year, month):
        return None
    return year, month, day


def analyze_offline_answer(
    field_type: str,
    label: str,
    field_key: str,
    value: Any,
    *,
    today: tuple[int, int, int] | None = None,
) -> list[QualityFinding]:
    """Return local quality findings; warnings never invalidate server answers."""
    if value is None or isinstance(value, (list, dict)) or not str(value).strip():
        return []

    kind = str(field_type or "").strip().casefold()
    text = str(value)
    findings: list[QualityFinding] = []
    normalized = _clean_text(text.translate(_DIGIT_TRANSLATION))
    tokens = _quality_tokens(normalized)
    compact = _compact_alphanumeric(normalized)
    person_name = is_person_name_field(kind, label, field_key)

    if person_name:
        letters = [char for char in normalized if char.isalpha()]
        repeated_letter_token = (
            len(letters) >= 3 and len(set(letters)) == 1
        ) or any(
            len(token_letters := [char for char in token if char.isalpha()]) >= 3
            and len(set(token_letters)) == 1
            for token in tokens
        )
        if not letters:
            findings.append(QualityFinding(
                "name_has_no_letters", "error",
                "برای این فیلد نام را با حروف بنویسید؛ عدد یا نماد به‌تنهایی نام نیست.",
            ))
        elif len(letters) < 2:
            findings.append(QualityFinding(
                "name_too_short", "error", "نام باید دست‌کم دو حرف داشته باشد؛ آن را بازبینی کنید.",
            ))
        elif repeated_letter_token:
            findings.append(QualityFinding(
                "suspicious_repeated_name", "error",
                "نام یا یکی از واژه‌های آن از تکرار یک حرف ساخته شده است؛ نام را اصلاح کنید.",
            ))
        elif compact in _PLACEHOLDER_NAMES:
            findings.append(QualityFinding(
                "placeholder_name", "error",
                "این پاسخ شبیه نام نمونه یا جای‌نگهدار است؛ نام فرد را وارد کنید.",
            ))
        elif compact in _PLACEHOLDER_VALUES:
            findings.append(QualityFinding(
                "placeholder_name", "warning",
                "این نام شبیه مقدار نمونه است؛ آن را بازبینی کنید و اگر درست است ادامه دهید.",
            ))
        elif _has_repeated_sequence(tokens):
            findings.append(QualityFinding(
                "repetitive_name_pattern", "warning",
                "نام الگوی تکراری دارد؛ آن را بازبینی کنید و اگر درست است ادامه دهید.",
            ))
        elif _has_keyboard_sequence(tokens):
            findings.append(QualityFinding(
                "keyboard_mash", "warning",
                "نام شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ آن را بازبینی کنید و اگر درست است ادامه دهید.",
            ))
        elif len(tokens) >= 2 and (
            len(set(tokens)) == 1 or any(count >= 3 for count in Counter(tokens).values())
        ):
            findings.append(QualityFinding(
                "repeated_name_token", "warning",
                "یک واژه در نام چندبار تکرار شده است؛ اگر عمدی است می‌توانید ادامه دهید.",
            ))

    if kind in _TEXT_FIELD_TYPES and not person_name:
        if compact in _PLACEHOLDER_VALUES:
            findings.append(QualityFinding(
                "placeholder_answer", "warning",
                "این پاسخ شبیه متن نمونه یا جای‌نگهدار است؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.",
            ))
        elif _has_repeated_sequence(tokens):
            findings.append(QualityFinding(
                "repetitive_answer_pattern", "warning",
                "این پاسخ الگوی تکراری دارد؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.",
            ))
        elif _has_keyboard_sequence(tokens):
            findings.append(QualityFinding(
                "keyboard_mash", "warning",
                "این پاسخ شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ مقدار را بازبینی کنید.",
            ))
        elif len(tokens) >= 2 and (
            len(set(tokens)) == 1 or any(count >= 3 for count in Counter(tokens).values())
        ):
            findings.append(QualityFinding(
                "repeated_answer_token", "warning",
                "یک واژه در این پاسخ چندبار تکرار شده است؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.",
            ))
        elif not any(char.isalnum() for char in normalized):
            findings.append(QualityFinding(
                "answer_only_symbols", "warning",
                "این پاسخ فقط از نشانه‌ها تشکیل شده است؛ اگر پاسخ کامل است می‌توانید ادامه دهید.",
            ))
        elif kind in {"text", "area", "address", "location"} and len(compact) <= 1:
            findings.append(QualityFinding(
                "very_short_answer", "warning",
                "این پاسخ بسیار کوتاه است؛ اگر کامل است می‌توانید ادامه دهید.",
            ))

    if kind in _PATTERN_FIELD_TYPES and kind not in _TEXT_FIELD_TYPES and not person_name:
        if _has_repeated_sequence(tokens):
            findings.append(QualityFinding(
                "repetitive_input_pattern", "warning",
                "این مقدار الگوی تکراری دارد؛ آن را بازبینی کنید و اگر درست است ادامه دهید.",
            ))
        elif _has_keyboard_sequence(tokens):
            findings.append(QualityFinding(
                "keyboard_sequence", "warning",
                "این مقدار شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ آن را بازبینی کنید.",
            ))
    if kind == "email" and _is_placeholder_email(text):
        findings.append(QualityFinding(
            "placeholder_email", "warning",
            "نشانی ایمیل شبیه نمونه یا دامنهٔ آزمایشی است؛ آن را بازبینی کنید.",
        ))

    if is_birth_date_field(kind, label, field_key):
        parts = _birth_date_parts(text)
        if parts is not None:
            current = today or current_jalali_date()
            if parts > current:
                findings.append(QualityFinding(
                    "birth_date_in_future", "error",
                    "تاریخ تولد نمی‌تواند در آینده باشد؛ تاریخ را بازبینی کنید.",
                ))
            elif parts == current:
                findings.append(QualityFinding(
                    "birth_date_is_today", "warning",
                    "تاریخ تولد برابر با امروز است؛ برای نوزاد تازه‌متولدشده می‌تواند درست باشد. در غیر این صورت تاریخ را اصلاح کنید.",
                    requires_confirmation=True,
                ))
            elif current[0] - parts[0] > 110:
                findings.append(QualityFinding(
                    "birth_date_unusually_old", "warning",
                    "این تاریخ تولد بیش از ۱۱۰ سال قبل است؛ اگر درست است می‌توانید ادامه دهید، وگرنه تاریخ را بازبینی کنید.",
                ))
    return findings
