from __future__ import annotations

from backend.form_quality import analyze_offline_answer, current_jalali_date


def finding(items, code):
    return next((item for item in items if item.code == code), None)


def test_free_text_quality_rules_are_broad_and_non_blocking():
    cases = [
        ("text", "توضیحات", "notes", "poiuytrewq", "keyboard_mash"),
        ("area", "پاسخ آزاد", "details", "abababab", "repetitive_answer_pattern"),
        ("text", "نظر", "comment", "سلام سلام", "repeated_answer_token"),
        ("address", "نشانی", "address", "???", "answer_only_symbols"),
        ("text", "توضیحات", "notes", "Test", "placeholder_answer"),
    ]
    for field_type, label, key, value, code in cases:
        result = analyze_offline_answer(field_type, label, key, value)
        issue = finding(result, code)
        assert issue is not None, (field_type, value, result)
        assert issue.severity == "warning"
        assert not any(item.severity == "error" for item in result)

    manual_university = analyze_offline_answer(
        "uni", "نام دانشگاه", "university", "تهران · دانشگاه خارج از فهرست"
    )
    assert manual_university == []


def test_structured_inputs_get_only_relevant_quality_warnings():
    repeated_nid = analyze_offline_answer("nid", "کد ملی", "nid", "۱۱۱۱۱۱۱۱۱۱")
    issue = finding(repeated_nid, "repetitive_input_pattern")
    assert issue is not None and issue.severity == "warning"
    assert not any(item.severity == "error" for item in repeated_nid)

    sequential_number = analyze_offline_answer("number", "کد پیگیری", "code", "۱۲۳۴۵۶۷۸۹۰")
    assert finding(sequential_number, "keyboard_sequence") is not None

    repeated_mobile = analyze_offline_answer("mobile", "موبایل", "mobile", "۰۹۱۱۱۱۱۱۱۱۱")
    assert finding(repeated_mobile, "repetitive_input_pattern") is not None

    placeholder_email = analyze_offline_answer("email", "ایمیل", "email", "test@example.com")
    assert finding(placeholder_email, "placeholder_email") is not None
    assert not any(item.severity == "error" for item in placeholder_email)

    selected_choice = analyze_offline_answer("choice", "گزینه", "choice", "Test")
    assert selected_choice == []

    multi_value = analyze_offline_answer("multi", "گزینه‌ها", "multi", ["Test", "گزینهٔ دوم"])
    assert multi_value == []


def test_name_and_birth_hard_rules_stay_specific_and_calendar_aware():
    repeated_name = analyze_offline_answer("text", "نام کامل", "full-name", "لیلا رررر")
    issue = finding(repeated_name, "suspicious_repeated_name")
    assert issue is not None and issue.severity == "error"

    placeholder_name = analyze_offline_answer("fullname", "نام همراه", "companion-name", "Test")
    issue = finding(placeholder_name, "placeholder_name")
    assert issue is not None and issue.severity == "error"

    sample_name = analyze_offline_answer("fullname", "نام", "name", "Sample")
    issue = finding(sample_name, "placeholder_name")
    assert issue is not None and issue.severity == "warning"

    today = current_jalali_date()
    today_text = f"{today[0]:04d}/{today[1]:02d}/{today[2]:02d}"
    today_birth = analyze_offline_answer("date", "تاریخ تولد", "birth-date", today_text, today=today)
    issue = finding(today_birth, "birth_date_is_today")
    assert issue is not None and issue.severity == "warning" and issue.requires_confirmation

    future = (today[0] + 1, 1, 1)
    future_text = f"{future[0]:04d}/01/01"
    future_birth = analyze_offline_answer("date", "تاریخ تولد", "birth-date", future_text, today=today)
    issue = finding(future_birth, "birth_date_in_future")
    assert issue is not None and issue.severity == "error"

    future_event = analyze_offline_answer("date", "تاریخ رویداد", "event-date", future_text, today=today)
    assert future_event == []
