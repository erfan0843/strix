"""Read-only bot reports over the shared forms API; never query local SQLite."""

# ruff: noqa: INP001, RUF001
from __future__ import annotations

import re

import jalali as _jd
import shared_api
from bale_api import send_or_edit


_FORM_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)
_RESPONSE_STATES = {"accepted": "ثبت‌شده", "waitlisted": "فهرست انتظار"}
_FORM_STATES = {
    "draft": "پیش‌نویس",
    "published": "منتشرشده",
    "paused": "متوقف",
    "archived": "بایگانی",
}


def _authorize(cid, uid) -> bool:
    try:
        identity = shared_api.get_identity(uid)
    except shared_api.SharedAPIError as error:
        message = (
            "هویت سروری در دسترس نیست؛ هیچ اطلاعات محلی جایگزین نمی‌شود."
            if error.status != 403
            else "این حساب مجوز مشاهدهٔ پاسخ‌های فرم را ندارد."
        )
        send_or_edit(cid, message)
        return False
    if not identity.has_permission("fm_responses"):
        send_or_edit(cid, "برای مشاهدهٔ پاسخ‌های مشترک، مجوز فرم‌ها فعال نیست.")
        return False
    return True


def _api_error(
    cid, error: shared_api.SharedAPIError, *, action: str, retry_callback: str = "sfr_forms"
) -> None:
    if error.status == 403:
        message = "این نقش مجوز مشاهدهٔ پاسخ‌های فرم را ندارد."
    elif error.status == 404:
        message = "فرم یا پاسخ پیدا نشد یا دیگر در دسترس نیست."
    else:
        message = f"{action} از پایگاه مشترک در دسترس نیست؛ دادهٔ محلی جایگزین نمی‌شود."
    send_or_edit(
        cid,
        message,
        {
            "inline_keyboard": [
                [{"text": "🔄 تلاش دوباره", "callback_data": retry_callback}],
                [{"text": "📊 گزارش فرم‌های سرور", "callback_data": "rp_forms"}],
            ]
        },
    )


def invalid_callback(cid):
    return send_or_edit(cid, "این دکمهٔ گزارش معتبر نیست؛ از گزارش فرم‌های سرور دوباره وارد شوید.")


def show_forms(cid, uid, page: int = 0):
    """List only server forms visible to a role with the explicit fm_responses permission."""
    if type(page) is not int or not 0 <= page <= 100_000:
        return invalid_callback(cid)
    if not _authorize(cid, uid):
        return None
    try:
        result = shared_api.list_bot_admin_forms(uid, page)
    except shared_api.SharedAPIError as error:
        return _api_error(cid, error, action="فهرست فرم‌ها")

    items = result["items"]
    if not items:
        return send_or_edit(
            cid,
            "📄 فرم‌های سرور\n━━━━━━━━━━━━━━\n\n"
            "فرمی در پایگاه مشترک پیدا نشد. فرم‌ها و پاسخ‌های محلی در این صفحه نمایش داده نمی‌شوند.",
            {
                "inline_keyboard": [
                    [{"text": "🔄 تازه‌سازی", "callback_data": "sfr_forms"}],
                    [{"text": "📊 گزارش فرم‌ها", "callback_data": "rp_forms"}],
                ]
            },
        )

    lines = [f"📄 فرم‌های سرور ({result['total']})", "━━━━━━━━━━━━━━", ""]
    buttons = []
    for item in items:
        status = _FORM_STATES[item["status"]]
        lines.append(f"📝 {item['name'][:54]}")
        lines.append(f"   {status} · {item['response_count']} پاسخ · نسخهٔ {item['version']}")
        buttons.append(
            [
                {
                    "text": f"📋 پاسخ‌ها: {item['name'][:32]}",
                    "callback_data": f"sfrf_{item['id']}",
                }
            ]
        )

    current_page = result["page"]
    if result["pages"] > 1:
        navigation = []
        if current_page > 0:
            navigation.append({"text": "⬅️", "callback_data": f"sfrl_{current_page - 1}"})
        navigation.append(
            {"text": f"{current_page + 1}/{result['pages']}", "callback_data": "noop"}
        )
        if current_page < result["pages"] - 1:
            navigation.append({"text": "➡️", "callback_data": f"sfrl_{current_page + 1}"})
        buttons.append(navigation)
    buttons.extend(
        [
            [{"text": "📊 گزارش فرم‌ها", "callback_data": "rp_forms"}],
            [{"text": "🔙 گزارش‌های زنده", "callback_data": "admin_stats"}],
        ]
    )
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": buttons})


def show_responses(cid, uid, form_id: str, page: int = 0):
    """Show a paginated summary; answer contents load only after a separate selection."""
    if not isinstance(form_id, str) or not _FORM_ID.fullmatch(form_id):
        return invalid_callback(cid)
    if type(page) is not int or not 0 <= page <= 100_000:
        return invalid_callback(cid)
    if not _authorize(cid, uid):
        return None
    try:
        result = shared_api.list_bot_admin_form_responses(uid, form_id, page)
    except shared_api.SharedAPIError as error:
        return _api_error(
            cid,
            error,
            action="پاسخ‌های فرم",
            retry_callback=f"sfrf_{form_id}" if error.status != 404 else "sfr_forms",
        )

    if not result["items"]:
        return send_or_edit(
            cid,
            "📋 پاسخ‌های فرم\n━━━━━━━━━━━━━━\n\nهنوز پاسخی در پایگاه مشترک ثبت نشده است.",
            {
                "inline_keyboard": [
                    [{"text": "🔄 تازه‌سازی", "callback_data": f"sfrf_{form_id}"}],
                    [{"text": "📄 فرم‌های سرور", "callback_data": "sfr_forms"}],
                ]
            },
        )

    form_name = result["items"][0]["form_name"]
    lines = [f"📋 پاسخ‌های سرور · {form_name[:48]}", "━━━━━━━━━━━━━━", ""]
    buttons = []
    for item in result["items"]:
        status = _RESPONSE_STATES[item["status"]]
        date_text = _jd.fmt(item["created_at"], "datetime")
        lines.append(f"{('✅' if item['status'] == 'accepted' else '⏳')} {status}")
        lines.append(f"   {date_text} · {item['answer_count']} پاسخ")
        buttons.append(
            [
                {
                    "text": f"📄 مشاهدهٔ پاسخ · {date_text[:24]}",
                    "callback_data": f"sfrd_{item['id']}",
                }
            ]
        )

    current_page = result["page"]
    if result["pages"] > 1:
        navigation = []
        if current_page > 0:
            navigation.append(
                {
                    "text": "⬅️",
                    "callback_data": f"sfrp_{form_id}_{current_page - 1}",
                }
            )
        navigation.append(
            {"text": f"{current_page + 1}/{result['pages']}", "callback_data": "noop"}
        )
        if current_page < result["pages"] - 1:
            navigation.append(
                {
                    "text": "➡️",
                    "callback_data": f"sfrp_{form_id}_{current_page + 1}",
                }
            )
        buttons.append(navigation)
    buttons.extend(
        [
            [{"text": "📄 فرم‌های سرور", "callback_data": "sfr_forms"}],
            [{"text": "📊 گزارش فرم‌ها", "callback_data": "rp_forms"}],
        ]
    )
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": buttons})


def show_response(cid, uid, response_id: str):
    """Read one server response; the backend rechecks fm_responses and form ownership."""
    if not isinstance(response_id, str) or not _FORM_ID.fullmatch(response_id):
        return invalid_callback(cid)
    if not _authorize(cid, uid):
        return None
    try:
        result = shared_api.get_bot_admin_form_response(uid, response_id)
    except shared_api.SharedAPIError as error:
        return _api_error(
            cid,
            error,
            action="جزئیات پاسخ",
            retry_callback=f"sfrd_{response_id}" if error.status != 404 else "sfr_forms",
        )

    response = result["response"]
    snapshot = response["form_snapshot"]
    status = _RESPONSE_STATES[response["status"]]
    lines = [
        f"📄 {snapshot['name'][:100]}",
        "━━━━━━━━━━━━━━",
        f"وضعیت: {status}",
        f"📅 {_jd.fmt(response['created_at'], 'datetime')}",
        "",
        "━━━ پاسخ‌ها ━━━",
        "",
    ]
    ticket_type = snapshot.get("ticket_type")
    if isinstance(ticket_type, dict) and isinstance(ticket_type.get("name"), str):
        lines.insert(4, f"🎟 مدل بلیت: {ticket_type['name']}")
    answers = response["answers"]
    for field in snapshot["fields"]:
        value = answers.get(field["id"])
        if isinstance(value, list):
            rendered = "، ".join(value) if value else "—"
        elif isinstance(value, str) and value.strip():
            rendered = value
        else:
            rendered = "—"
        lines.append(f"▫️ {field['label'][:100]}:\n   {rendered}")
    form_id = response["form_id"]
    return send_or_edit(
        cid,
        "\n".join(lines),
        {
            "inline_keyboard": [
                [{"text": "🔙 پاسخ‌های همین فرم", "callback_data": f"sfrp_{form_id}_0"}],
                [{"text": "📄 فرم‌های سرور", "callback_data": "sfr_forms"}],
            ]
        },
    )
