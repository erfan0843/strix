"""Conversational form filling backed only by the shared Nora API.

The local bot state contains a form/session pointer and navigation metadata;
answers are always read from and written to the canonical server draft.
"""
# ruff: noqa: INP001, RUF001

from __future__ import annotations

import re
import secrets
from decimal import Decimal, InvalidOperation
from typing import Any

import shared_api
import shared_form_ticket
from auth import clear_state, get_state_data, get_state_name, set_state, update_state_data
from bale_api import send, send_or_edit


STATE = "shared_form_fill"
_FORM_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)
_MULTI_PAGE_SIZE = 10


def _is_current(uid: int | str) -> bool:
    return get_state_name(uid) == STATE


def _state(uid: int | str) -> dict[str, Any] | None:
    if not _is_current(uid):
        return None
    data = get_state_data(uid)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("form_id"), str)
        or not _FORM_ID.fullmatch(data["form_id"])
        or not isinstance(data.get("session_key"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", data["session_key"])
    ):
        clear_state(uid)
        return None
    return data


def abandon(uid: int | str) -> None:
    """Leave the conversation without copying or deleting its server draft."""
    if _is_current(uid):
        clear_state(uid)


def _field_required(field: dict[str, Any]) -> bool:
    return field.get("req") is True or field.get("required") is True


def _field_options(field: dict[str, Any]) -> list[str]:
    raw = field.get("opts", field.get("options", []))
    options: list[str] = []
    if isinstance(raw, list):
        for item in raw[:100]:
            value = item.get("l") if isinstance(item, dict) else item
            if isinstance(value, str) and value.strip():
                options.append(value.strip())
    if options:
        return options
    return {
        "gender": ["زن", "مرد", "ترجیح می‌دهم نگویم"],
        "marital": ["مجرد", "متأهل", "ترجیح می‌دهم نگویم"],
        "yesno": ["بله", "خیر"],
    }.get(str(field.get("t") or "").lower(), [])


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    raw = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    raw = raw.replace("٫", ".").replace("٬", "").strip()
    try:
        parsed = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _numeric_options(field: dict[str, Any]) -> list[str]:
    field_type = str(field.get("t") or "").lower()
    if field_type not in {"rating", "scale", "bars"}:
        return []
    default_min, default_max = (1, 5) if field_type == "rating" else (0, 10)
    minimum_raw = field.get("min")
    maximum_raw = field.get("max")
    minimum = _number(default_min if minimum_raw in (None, "") else minimum_raw)
    maximum = _number(default_max if maximum_raw in (None, "") else maximum_raw)
    if minimum is None or maximum is None or minimum > maximum:
        return []
    if minimum != minimum.to_integral_value() or maximum != maximum.to_integral_value():
        return []
    low, high = int(minimum), int(maximum)
    if high - low > 10:
        return []
    return [str(value) for value in range(low, high + 1)]


def _field_order(result: dict[str, Any]) -> list[str]:
    return [field["id"] for field in result["form"]["fields"]]


def _answer_is_set(value: Any) -> bool:
    if value is None or value == "":
        return False
    return not isinstance(value, list) or bool(value)


def _next_unanswered(result: dict[str, Any], state: dict[str, Any]) -> str | None:
    answers = result["draft"]["answers"]
    skipped = set(state.get("skipped_fields") or [])
    for field_id in result["visible_field_ids"]:
        if field_id not in skipped and not _answer_is_set(answers.get(field_id)):
            return field_id
    return None


def _next_after_current(result: dict[str, Any], current_id: str) -> str | None:
    order = _field_order(result)
    try:
        current_position = order.index(current_id)
    except ValueError:
        current_position = -1
    return next(
        (
            field_id
            for field_id in result["visible_field_ids"]
            if field_id in order and order.index(field_id) > current_position
        ),
        None,
    )


def _previous_visible(result: dict[str, Any], current_id: str) -> str | None:
    visible = result["visible_field_ids"]
    try:
        position = visible.index(current_id)
    except ValueError:
        return None
    return visible[position - 1] if position > 0 else None


def _format_answer(value: Any, *, limit: int = 120) -> str:
    if isinstance(value, list):
        text = "، ".join(str(item) for item in value)
    elif value is None or value == "":
        text = "—"
    else:
        text = str(value)
    return " ".join(text.split())[:limit]


def _field_keyboard(  # noqa: PLR0912, PLR0915
    result: dict[str, Any], state: dict[str, Any], field: dict[str, Any]
) -> dict[str, Any]:
    field_id = field["id"]
    answers = result["draft"]["answers"]
    selected = answers.get(field_id, [])
    if not isinstance(selected, list):
        selected = []
    rows: list[list[dict[str, str]]] = []
    field_type = str(field.get("t") or "").lower()
    options = _field_options(field)
    numeric_options = _numeric_options(field)
    page = max(0, int(state.get("option_page", 0) or 0))

    if field_type == "terms":
        rows.append([{"text": "✅ می‌پذیرم", "callback_data": "bff_terms"}])
    elif field_type == "multi" and options:
        pages = max(1, (len(options) + _MULTI_PAGE_SIZE - 1) // _MULTI_PAGE_SIZE)
        page = min(page, pages - 1)
        start = page * _MULTI_PAGE_SIZE
        for index, label in enumerate(options[start : start + _MULTI_PAGE_SIZE], start=start):
            marked = index < len(options) and label in selected
            verb = "del" if marked else "add"
            rows.append(
                [
                    {
                        "text": f"{'☑️' if marked else '⬜'} {label[:54]}",
                        "callback_data": f"bffm{verb}_{index}",
                    }
                ]
            )
        if pages > 1:
            nav = []
            if page > 0:
                nav.append({"text": "گزینه‌های قبل", "callback_data": "bff_opts_prev"})
            nav.append({"text": f"{page + 1}/{pages}", "callback_data": "noop"})
            if page < pages - 1:
                nav.append({"text": "گزینه‌های بعد", "callback_data": "bff_opts_next"})
            rows.append(nav)
        rows.append(
            [
                {
                    "text": f"✅ تأیید انتخاب‌ها ({len(selected)})",
                    "callback_data": "bff_multi_done",
                }
            ]
        )
    elif options:
        pages = max(1, (len(options) + _MULTI_PAGE_SIZE - 1) // _MULTI_PAGE_SIZE)
        page = min(page, pages - 1)
        start = page * _MULTI_PAGE_SIZE
        current = answers.get(field_id)
        for index, label in enumerate(options[start : start + _MULTI_PAGE_SIZE], start=start):
            prefix = "✅ " if current == label else ""
            rows.append(
                [
                    {
                        "text": f"{prefix}{label[:56]}",
                        "callback_data": f"bffopt_{index}",
                    }
                ]
            )
        if pages > 1:
            nav = []
            if page > 0:
                nav.append({"text": "گزینه‌های قبل", "callback_data": "bff_opts_prev"})
            nav.append({"text": f"{page + 1}/{pages}", "callback_data": "noop"})
            if page < pages - 1:
                nav.append({"text": "گزینه‌های بعد", "callback_data": "bff_opts_next"})
            rows.append(nav)
    elif numeric_options:
        rows.extend(
            [[{"text": value, "callback_data": f"bffnum_{value}"}] for value in numeric_options]
        )

    if _answer_is_set(answers.get(field_id)):
        rows.append([{"text": "✅ ادامه با همین پاسخ", "callback_data": "bff_next"}])
    navigation: list[dict[str, str]] = []
    if _previous_visible(result, field_id):
        navigation.append({"text": "⬅️ پرسش قبل", "callback_data": "bff_back"})
    if not _field_required(field):
        navigation.append({"text": "⏭ رد کردن", "callback_data": "bff_skip"})
    if navigation:
        rows.append(navigation)
    rows.append([{"text": "لغو تکمیل فرم", "callback_data": "bff_cancel"}])
    return {"inline_keyboard": rows}


def _show_review(
    cid: int | str, uid: int | str, result: dict[str, Any], state: dict[str, Any], notice: str = ""
):
    answers = result["draft"]["answers"]
    skipped = set(state.get("skipped_fields") or [])
    fields = {field["id"]: field for field in result["form"]["fields"]}
    lines = ["✅ بازبینی پاسخ‌ها", "━━━━━━━━━━━━━━", ""]
    if notice:
        lines.extend([notice, ""])
    for number, field_id in enumerate(result["visible_field_ids"], 1):
        field = fields[field_id]
        answer = "رد شده" if field_id in skipped else _format_answer(answers.get(field_id))
        lines.append(f"{number}. {field['l'][:80]}: {answer}")
    lines.extend(
        ["", "اگر لازم است، پاسخ‌ها را اصلاح کنید؛ ثبت نهایی آن‌ها در پایگاه مشترک انجام می‌شود."]
    )
    update_state_data(uid, {"current_field_id": None, "reviewing": False, "option_page": 0})
    return send_or_edit(
        cid,
        "\n".join(lines),
        {
            "inline_keyboard": [
                [{"text": "✏️ ویرایش پاسخ‌ها", "callback_data": "bff_edit"}],
                [{"text": "✅ ثبت نهایی", "callback_data": "bff_submit"}],
                [{"text": "لغو تکمیل فرم", "callback_data": "bff_cancel"}],
            ]
        },
    )


def _show_field(
    cid: int | str,
    uid: int | str,
    result: dict[str, Any],
    state: dict[str, Any],
    field_id: str,
    *,
    notice: str = "",
):
    fields = {field["id"]: field for field in result["form"]["fields"]}
    if field_id not in fields or field_id not in result["visible_field_ids"]:
        next_id = _next_unanswered(result, state)
        return (
            _show_review(cid, uid, result, state, notice)
            if next_id is None
            else _show_field(cid, uid, result, state, next_id, notice=notice)
        )
    field = fields[field_id]
    visible_position = result["visible_field_ids"].index(field_id) + 1
    total = len(result["visible_field_ids"])
    current = result["draft"]["answers"].get(field_id)
    lines = [
        f"📝 {result['form']['name'][:80]}",
        f"پرسش {visible_position} از {total}",
        "━━━━━━━━━━━━━━",
        "",
    ]
    if notice:
        lines.extend([notice, ""])
    lines.append(f"{'⭐ ' if _field_required(field) else ''}{field['l']}")
    help_text = field.get("help") or field.get("placeholder")
    if isinstance(help_text, str) and help_text.strip():
        lines.append(f"\n💡 {help_text[:300]}")
    if field.get("t") == "terms":
        lines.append("\nبرای ادامه، پذیرش این مورد را ثبت کنید.")
    elif field.get("t") == "location":
        lines.append("\nنشانی را بنویسید یا موقعیت مکانی‌تان را بفرستید.")
    elif not _field_options(field) and not _numeric_options(field):
        lines.append("\nپاسخ‌تان را در یک پیام بفرستید.")
    if _answer_is_set(current):
        lines.append(f"\nپاسخ فعلی: {_format_answer(current)}")
    update_state_data(uid, {"current_field_id": field_id})
    return send_or_edit(
        cid,
        "\n".join(lines),
        _field_keyboard(result, state, field),
    )


def _show_next(
    cid: int | str,
    uid: int | str,
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    notice: str = "",
):
    current_id = state.get("current_field_id")
    if state.get("reviewing") and current_id in result["visible_field_ids"]:
        return _show_field(cid, uid, result, state, current_id, notice=notice)
    next_id = _next_unanswered(result, state)
    if next_id is None:
        return _show_review(cid, uid, result, state, notice)
    return _show_field(cid, uid, result, state, next_id, notice=notice)


def _api_error_text(error: shared_api.SharedAPIError, *, input_was_not_saved: bool = False) -> str:
    if error.code == "form_full" or error.status == 410:
        message = "ظرفیت یا مهلت این فرم تمام شده است. پاسخ در بات ثبت نشده."
    elif error.status == 429:
        message = "درخواست‌ها زیاد شده؛ کمی صبر کنید و دوباره تلاش کنید."
    elif error.status == 404:
        message = "فرایند پاسخ‌گویی این فرم پیدا نشد یا مهلتش تمام شده است؛ از فهرست فرم‌ها دوباره شروع کنید."
    elif error.status == 409 and error.code == "form_version_changed":
        message = "فرم به‌روزرسانی شده؛ نسخهٔ تازه را دوباره باز کنید."
    elif error.status == 422:
        message = "این پاسخ با تنظیم پرسش سازگار نیست؛ پاسخ را اصلاح کنید."
    elif error.status in {0, 502, 503, 504}:
        message = "اتصال پایگاه مشترک برقرار نشد. پاسخ محلی ذخیره نشده؛ کمی بعد دوباره تلاش کنید."
    else:
        message = "ثبت در پایگاه مشترک انجام نشد؛ دوباره تلاش کنید."
    if input_was_not_saved:
        message += " همان پاسخ را دوباره بفرستید؛ در بات نگه‌داری نشده است."
    return message


def _send_api_error(
    cid: int | str,
    error: shared_api.SharedAPIError,
    *,
    input_was_not_saved: bool = False,
):
    return send_or_edit(
        cid,
        "⚠️ " + _api_error_text(error, input_was_not_saved=input_was_not_saved),
        {
            "inline_keyboard": [
                [{"text": "🔄 بازخوانی پرسش", "callback_data": "bff_refresh"}],
                [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
            ]
        },
    )


def _starting_notice(cid: int | str):
    return send_or_edit(
        cid,
        "فرم هنوز برای پاسخ‌گویی آماده نشده است؛ برای ادامه دوباره تلاش کنید.",
        {
            "inline_keyboard": [
                [{"text": "🔄 تلاش دوباره", "callback_data": "bff_refresh"}],
                [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
            ]
        },
    )


def _load(cid: int | str, uid: int | str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    state = _state(uid)
    if state is None:
        send(cid, "فرایند گفتگومحور پیدا نشد؛ از فهرست فرم‌ها دوباره شروع کنید.")
        return None
    if state.get("starting") is True:
        _starting_notice(cid)
        return None
    try:
        result = shared_api.get_bot_form_draft(uid, state["form_id"], state["session_key"])
    except shared_api.SharedAPIError as error:
        if error.status in {404, 410}:
            clear_state(uid)
        _send_api_error(cid, error)
        return None
    if result["draft"]["submitted"]:
        _show_submitted(cid, uid, result["draft"]["status"], already=True)
        return None
    stored_version = state.get("form_version")
    current_version = result["draft"]["form_version"]
    if isinstance(stored_version, int) and stored_version != current_version:
        state.update(
            {
                "form_version": current_version,
                "current_field_id": result["visible_field_ids"][0]
                if result["visible_field_ids"]
                else None,
                "skipped_fields": [],
                "reviewing": False,
                "option_page": 0,
            }
        )
        update_state_data(
            uid,
            {
                "form_version": current_version,
                "current_field_id": state["current_field_id"],
                "skipped_fields": [],
                "reviewing": False,
                "option_page": 0,
            },
        )
        _show_next(
            cid,
            uid,
            result,
            state,
            notice="فرم تغییر کرده است؛ پیش‌نویس قبلی برای جلوگیری از ثبت ناسازگار پاک شد.",
        )
        return None
    return state, result


def _show_submitted(
    cid: int | str,
    uid: int | str,
    status: str,
    *,
    already: bool = False,
    form_id: str | None = None,
    response_id: str | None = None,
):
    clear_state(uid)
    if status == "waitlisted":
        text = (
            "⏳ پاسخ شما در پایگاه مشترک ثبت شد و در فهرست انتظار قرار گرفت؛ "
            "جایگاه نهایی هنوز تأیید نشده است. بلیتی صادر نمی‌شود."
        )
    else:
        text = "✅ پاسخ شما در پایگاه مشترک ثبت شد."
    if already:
        text += "\n\nاین پاسخ پیش‌تر ثبت شده بود."
    result = send_or_edit(
        cid,
        text,
        {
            "inline_keyboard": [
                [{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}],
                [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
                [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}],
            ]
        },
    )
    if status == "accepted" and form_id and response_id:
        shared_form_ticket.deliver_response(cid, uid, form_id, response_id)
    return result


def start(cid: int | str, uid: int | str, form_id: str):
    if not isinstance(form_id, str) or not _FORM_ID.fullmatch(form_id):
        return send(cid, "این دکمهٔ فرم معتبر نیست؛ از فهرست فرم‌ها دوباره انتخاب کنید.")
    current = _state(uid)
    same_form = current is not None and current["form_id"] == form_id
    if same_form and current.get("starting") is not True:
        return refresh(cid, uid)
    session_key = current["session_key"] if same_form else secrets.token_urlsafe(32)
    set_state(
        uid,
        STATE,
        {"form_id": form_id, "session_key": session_key, "starting": True},
        merge=False,
    )
    try:
        result = shared_api.start_bot_form_draft(uid, form_id, session_key)
    except shared_api.SharedAPIError as error:
        return _send_api_error(cid, error)
    if result["draft"]["submitted"]:
        return _show_submitted(cid, uid, result["draft"]["status"], already=True)
    visible = result["visible_field_ids"]
    state = {
        "form_id": form_id,
        "session_key": session_key,
        "form_version": result["draft"]["form_version"],
        "current_field_id": visible[0] if visible else None,
        "skipped_fields": [],
        "reviewing": False,
        "option_page": 0,
    }
    set_state(uid, STATE, state, merge=False)
    return _show_next(cid, uid, result, state)


def _validation_notice(error: shared_api.SharedAPIError) -> tuple[str, str | None]:
    detail = error.detail
    if isinstance(detail, dict):
        errors = detail.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            field_id = errors[0].get("field_id")
            message = errors[0].get("message")
            return (message if isinstance(message, str) else "پاسخ این پرسش را بررسی کنید."), (
                field_id if isinstance(field_id, str) else None
            )
    return "پاسخ این پرسش را بررسی کنید.", None


def _persist_answer(  # noqa: PLR0911
    cid: int | str,
    uid: int | str,
    state: dict[str, Any],
    field_id: str,
    *,
    value: object = None,
    remove: bool = False,
    advance: bool = True,
    notice: str = "",
):
    try:
        result = shared_api.save_bot_form_answer(
            uid, state["form_id"], state["session_key"], field_id, value, remove=remove
        )
    except shared_api.SharedAPIError as error:
        if error.status == 409 and error.code == "form_version_changed":
            return _load(cid, uid)
        if error.status == 422:
            detail, invalid_field = _validation_notice(error)
            try:
                latest = shared_api.get_bot_form_draft(uid, state["form_id"], state["session_key"])
            except shared_api.SharedAPIError:
                return _send_api_error(cid, error, input_was_not_saved=not remove)
            if invalid_field in latest["visible_field_ids"]:
                update_state_data(uid, {"current_field_id": invalid_field, "reviewing": True})
                return _show_field(
                    cid,
                    uid,
                    latest,
                    {**state, "current_field_id": invalid_field, "reviewing": True},
                    invalid_field,
                    notice=detail,
                )
            return _show_field(cid, uid, latest, state, field_id, notice=detail)
        return _send_api_error(cid, error, input_was_not_saved=not remove)

    skipped = list(state.get("skipped_fields") or [])
    if remove:
        if field_id not in skipped:
            skipped.append(field_id)
    else:
        skipped = [item for item in skipped if item != field_id]
    update_state_data(uid, {"skipped_fields": skipped})
    state["skipped_fields"] = skipped
    if not advance:
        state["current_field_id"] = field_id
        update_state_data(uid, {"current_field_id": field_id})
        return _show_field(cid, uid, result, state, field_id, notice=notice)

    if state.get("reviewing"):
        next_id = _next_after_current(result, field_id)
    else:
        next_id = _next_unanswered(result, state)
    if next_id is None:
        return _show_review(cid, uid, result, state, notice)
    state["current_field_id"] = next_id
    state["option_page"] = 0
    update_state_data(uid, {"current_field_id": next_id, "option_page": 0})
    return _show_field(cid, uid, result, state, next_id, notice=notice)


def handle_input(cid: int | str, uid: int | str, value: str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if field is None or field_id not in result["visible_field_ids"]:
        return _show_next(cid, uid, result, state)
    if not isinstance(value, str) or not value.strip():
        return send(cid, "پاسخ خالی است؛ متن را بفرستید یا از دکمه‌های همین پرسش استفاده کنید.")
    return _persist_answer(cid, uid, state, field_id, value=value)


def handle_location(cid: int | str, uid: int | str, location: dict[str, Any]):
    latitude = location.get("latitude") if isinstance(location, dict) else None
    longitude = location.get("longitude") if isinstance(location, dict) else None
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return send(cid, "موقعیت معتبر نیست؛ دوباره بفرستید یا نشانی را به‌صورت متن بنویسید.")
    return handle_input(cid, uid, f"{latitude:.6f}, {longitude:.6f}")


def handle_message(cid: int | str, uid: int | str, msg: dict[str, Any]):
    text = (msg.get("text") or "").strip() if isinstance(msg, dict) else ""
    if text in {"⏭️ رد کردن", "رد کردن", "رد", "/skip"}:
        return skip(cid, uid)
    if text in {"🔙 بازگشت", "بازگشت"}:
        return back(cid, uid)
    return handle_input(cid, uid, text)


def _option(cid: int | str, uid: int | str, index: int, *, multi_action: str | None = None):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    options = _field_options(field or {})
    if (
        field is None
        or field_id not in result["visible_field_ids"]
        or not 0 <= index < len(options)
    ):
        return send(cid, "این گزینه دیگر در فرم نیست؛ پرسش تازه را دنبال کنید.")
    if multi_action:
        current = result["draft"]["answers"].get(field_id, [])
        selected = list(current) if isinstance(current, list) else []
        label = options[index]
        if multi_action == "add" and label not in selected:
            selected.append(label)
        elif multi_action == "del" and label in selected:
            selected.remove(label)
        return _persist_answer(cid, uid, state, field_id, value=selected, advance=False)
    return _persist_answer(cid, uid, state, field_id, value=options[index])


def _numeric(cid: int | str, uid: int | str, value: str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if (
        field is None
        or field_id not in result["visible_field_ids"]
        or value not in _numeric_options(field)
    ):
        return send(cid, "این گزینه دیگر در فرم نیست؛ پرسش تازه را دنبال کنید.")
    return _persist_answer(cid, uid, state, field_id, value=value)


def _accept_terms(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if field is None or field.get("t") != "terms":
        return send(cid, "این دکمه دیگر به پرسش جاری مربوط نیست.")
    return _persist_answer(cid, uid, state, field_id, value="پذیرفتم")


def skip(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if field is None or _field_required(field):
        return send(cid, "این پرسش اجباری است؛ برای ادامه پاسخ بدهید.")
    return _persist_answer(cid, uid, state, field_id, remove=True)


def back(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    previous = _previous_visible(result, state.get("current_field_id"))
    if previous is None:
        return _show_field(cid, uid, result, state, state.get("current_field_id"))
    state.update({"current_field_id": previous, "reviewing": True, "option_page": 0})
    update_state_data(uid, {"current_field_id": previous, "reviewing": True, "option_page": 0})
    return _show_field(cid, uid, result, state, previous)


def _set_option_page(cid: int | str, uid: int | str, direction: int):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if field is None:
        return _show_next(cid, uid, result, state)
    options = _field_options(field)
    pages = max(1, (len(options) + _MULTI_PAGE_SIZE - 1) // _MULTI_PAGE_SIZE)
    page = max(0, min(pages - 1, int(state.get("option_page", 0) or 0) + direction))
    update_state_data(uid, {"option_page": page})
    state["option_page"] = page
    return _show_field(cid, uid, result, state, field_id)


def refresh(cid: int | str, uid: int | str):
    state = _state(uid)
    if state is not None and state.get("starting") is True:
        return start(cid, uid, state["form_id"])
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    return _show_next(cid, uid, result, state)


def edit(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    if not result["visible_field_ids"]:
        return _show_review(cid, uid, result, state)
    field_id = result["visible_field_ids"][0]
    state.update({"current_field_id": field_id, "reviewing": True, "option_page": 0})
    update_state_data(uid, {"current_field_id": field_id, "reviewing": True, "option_page": 0})
    return _show_field(cid, uid, result, state, field_id)


def continue_current(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    if field_id not in result["visible_field_ids"]:
        return _show_next(cid, uid, result, state)
    if state.get("reviewing"):
        next_id = _next_after_current(result, field_id)
    else:
        next_id = _next_unanswered(result, state)
    if next_id is None:
        return _show_review(cid, uid, result, state)
    state.update({"current_field_id": next_id, "option_page": 0})
    update_state_data(uid, {"current_field_id": next_id, "option_page": 0})
    return _show_field(cid, uid, result, state, next_id)


def _multi_done(cid: int | str, uid: int | str):
    loaded = _load(cid, uid)
    if loaded is None:
        return None
    state, result = loaded
    field_id = state.get("current_field_id")
    field = next((item for item in result["form"]["fields"] if item["id"] == field_id), None)
    if field is None or str(field.get("t") or "").lower() != "multi":
        return send(cid, "این دکمه دیگر به پرسش جاری مربوط نیست.")
    selected = result["draft"]["answers"].get(field_id, [])
    selected = selected if isinstance(selected, list) else []
    if not selected:
        if not _field_required(field):
            return _persist_answer(cid, uid, state, field_id, remove=True)
        return _show_field(
            cid,
            uid,
            result,
            state,
            field_id,
            notice="برای ادامه دست‌کم یک گزینه انتخاب کنید.",
        )
    minimum = field.get("minSelect")
    try:
        minimum_count = max(0, int(minimum)) if minimum not in (None, "") else 0
    except (TypeError, ValueError, OverflowError):
        minimum_count = 0
    if len(selected) < minimum_count:
        return _show_field(
            cid,
            uid,
            result,
            state,
            field_id,
            notice=f"برای ثبت این پرسش دست‌کم {minimum_count} گزینه لازم است.",
        )
    return continue_current(cid, uid)


def cancel(cid: int | str, uid: int | str):
    state = _state(uid)
    if state is None:
        return send(cid, "گفتگوی فرم باز نیست.")
    try:
        deleted = shared_api.delete_bot_form_draft(uid, state["form_id"], state["session_key"])
    except shared_api.SharedAPIError:
        deleted = None
    clear_state(uid)
    if deleted and deleted.get("submitted"):
        return send(cid, "این پاسخ قبلاً در پایگاه مشترک ثبت شده و قابل لغو نیست.")
    if deleted is None:
        return send(
            cid, "گفتگو پایان یافت؛ حذف پیش‌نویس از سرور تأیید نشد و تا پایان مهلتش در پایگاه می‌ماند."
        )
    if not deleted.get("deleted"):
        return send(cid, "پیش‌نویسی در پایگاه پیدا نشد؛ گفتگو پایان یافت.")
    return send_or_edit(
        cid,
        "پیش‌نویس گفتگومحور از پایگاه مشترک پاک شد.",
        {"inline_keyboard": [[{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}]]},
    )


def submit(cid: int | str, uid: int | str):
    state = _state(uid)
    if state is None:
        return send(cid, "فرایند گفتگومحور پیدا نشد؛ از فهرست فرم‌ها دوباره شروع کنید.")
    try:
        result = shared_api.submit_bot_form_response(uid, state["form_id"], state["session_key"])
    except shared_api.SharedAPIError as error:
        if error.status == 422 and error.code == "answer_validation_failed":
            try:
                latest = shared_api.get_bot_form_draft(uid, state["form_id"], state["session_key"])
            except shared_api.SharedAPIError:
                return _send_api_error(cid, error)
            notice, invalid_field = _validation_notice(error)
            if invalid_field in latest["visible_field_ids"]:
                update_state_data(
                    uid,
                    {
                        "current_field_id": invalid_field,
                        "reviewing": True,
                        "option_page": 0,
                    },
                )
                return _show_field(
                    cid,
                    uid,
                    latest,
                    {
                        **state,
                        "current_field_id": invalid_field,
                        "reviewing": True,
                        "option_page": 0,
                    },
                    invalid_field,
                    notice=notice,
                )
            return _show_review(cid, uid, latest, state, notice)
        if error.status == 404:
            clear_state(uid)
        return _send_api_error(cid, error)
    return _show_submitted(
        cid,
        uid,
        result["status"],
        already=result["already_submitted"],
        form_id=state["form_id"],
        response_id=result["response_id"],
    )


def handle_callback(cid: int | str, uid: int | str, data: str):  # noqa: PLR0911, PLR0912
    if data.startswith("bffstart_"):
        return start(cid, uid, data.removeprefix("bffstart_"))
    if data == "bff_refresh":
        return refresh(cid, uid)
    if data == "bff_edit":
        return edit(cid, uid)
    if data == "bff_back":
        return back(cid, uid)
    if data == "bff_skip":
        return skip(cid, uid)
    if data == "bff_next":
        return continue_current(cid, uid)
    if data == "bff_multi_done":
        return _multi_done(cid, uid)
    if data == "bff_opts_next":
        return _set_option_page(cid, uid, 1)
    if data == "bff_opts_prev":
        return _set_option_page(cid, uid, -1)
    if data == "bff_terms":
        return _accept_terms(cid, uid)
    if data == "bff_submit":
        return submit(cid, uid)
    if data == "bff_cancel":
        return cancel(cid, uid)
    for prefix, action in (
        ("bffmadd_", "add"),
        ("bffmdel_", "del"),
        ("bffopt_", None),
        ("bffnum_", "number"),
    ):
        if data.startswith(prefix):
            raw = data.removeprefix(prefix)
            if action == "number":
                return _numeric(cid, uid, raw)
            try:
                index = int(raw)
            except ValueError:
                return send(cid, "این گزینه دیگر معتبر نیست.")
            return _option(cid, uid, index, multi_action=action)
    return None
