"""Issue and verify tickets for the canonical shared-form responses only.

Ticket answers and status are always fetched from the Nora API; this module
never reads form responses from the bot's legacy SQLite database.
"""
# ruff: noqa: INP001, RUF001

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

import config
import shared_api
from bale_api import send, send_document, send_photo


_RESPONSE_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)


def _ticket_caption(_ticket: dict[str, Any]) -> str:
    return "بلیتت آماده‌ست 🎫"


def _ticket_image_data(ticket: dict[str, Any]) -> dict[str, str]:
    response_id = ticket["response_id"]
    verify_link = config.deep_link("ftv_" + response_id)
    image_data = {
        "event_title": ticket["event_title"],
        "name": ticket["participant_name"],
        "serial": ticket["serial"],
        "qr_data": verify_link or response_id,
        "event_date": ticket["event_date"],
        "event_time": ticket["event_time"],
    }
    ticket_type = ticket.get("ticket_type")
    if isinstance(ticket_type, dict) and isinstance(ticket_type.get("name"), str):
        image_data["ticket_type_name"] = ticket_type["name"]
    return image_data


def _deliver(cid: int | str, ticket: dict[str, Any]):
    caption = _ticket_caption(ticket)
    try:
        # Shared forms use their own approved visual. The configurable legacy
        # renderer and its SQLite response lookup remain untouched.
        import ticket as ticket_renderer  # noqa: PLC0415

        with tempfile.TemporaryDirectory(prefix="nora-shared-ticket-") as directory:
            image_path = ticket_renderer.build_shared_form_ticket(
                _ticket_image_data(ticket), out_path=str(Path(directory) / "ticket.jpg")
            )
            if not image_path:
                return send(
                    cid,
                    "فعلاً نتونستم عکس بلیت رو بسازم؛ از لینک صفحهٔ فرم دوباره وارد ربات شو.",
                )
            result = send_photo(
                cid, image_path, caption, filename="nora-ticket.jpg", content_type="image/jpeg"
            )
            if isinstance(result, dict) and result.get("ok") is True:
                return result
            # If Bale rejects the photo upload, still deliver the same JPG file.
            document_result = send_document(
                cid, image_path, caption, filename="nora-ticket.jpg", content_type="image/jpeg"
            )
            if isinstance(document_result, dict) and document_result.get("ok") is True:
                return document_result
    except Exception:
        logging.getLogger(__name__).exception("Shared ticket image rendering/delivery failed")
    return send(cid, "عکس بلیت ارسال نشد؛ چند لحظه دیگه دوباره امتحان کن.")


def _delivery_error(cid: int | str, error: shared_api.SharedAPIError):
    if error.code == "ticket_not_accepted":
        message = "⏳ ثبت‌نامت هنوز نهایی نشده؛ بعد از نهایی‌شدن، بلیت همین‌جا برات میاد."
    elif error.code == "ticket_payment_not_confirmed":
        message = (
            "⏳ پرداخت یا رسیدت هنوز تأیید نشده؛ اگر رسید رو فرستادی، پس از بازبینی دستیِ "
            "برگزارکننده همین پیوند رو دوباره باز کن. اگر نه، اول رسید کارت‌به‌کارت رو "
            "در خود فرم ثبت کن."
        )
    elif error.code in {"ticket_claimed_by_another_account", "ticket_already_claimed"}:
        message = "⛔ این لینک بلیت قبلاً به یه حساب بله وصل شده."
    elif error.status == 403:
        message = "⛔ این بلیت به حساب بلهٔ دیگه‌ای وصله یا دسترسی لازم رو نداری."
    elif error.status == 404:
        message = "❌ لینک بلیت پیدا نشد؛ از صفحهٔ فرم دوباره وارد ربات شو."
    elif error.status == 409:
        message = "⚠️ هنوز بلیت فعالی برای این ثبت‌نام نداریم."
    elif error.status == 410:
        message = "⏳ لینک دریافت بلیت منقضی شده؛ از صفحهٔ فرم دوباره وارد ربات شو."
    elif error.status == 422:
        message = "❌ لینک بلیت کامل یا معتبر نیست."
    else:
        message = "⚠️ فعلاً نتونستیم بلیت رو بفرستیم؛ چند لحظه دیگه دوباره امتحان کن."
    return send(cid, message)


def deliver_claim(cid: int | str, uid: int | str, token: str):
    """Claim and deliver a public-web ticket after any required form upload."""
    if str(cid) != str(uid):
        return send(
            cid,
            "برای اینکه بلیتت خصوصی بمونه، فقط توی گفت‌وگوی خصوصی ربات می‌تونیم بفرستیمش.",
        )
    try:
        ticket_data = shared_api.claim_bot_form_ticket(uid, token)
    except shared_api.SharedAPIError as error:
        return _delivery_error(cid, error)
    if ticket_data.get("receipt_required") and not ticket_data.get("receipt_submitted"):
        return send(
            cid,
            "فیش کارت‌به‌کارت رو توی خود فرم ثبت کن؛ "
            "بعد همین لینک رو دوباره باز کن تا بلیتت رو بگیری.",
        )
    return _deliver(cid, ticket_data)


def deliver_response(cid: int | str, uid: int | str, form_id: str, response_id: str):
    """Deliver an accepted bot-origin ticket without consulting local response data."""
    if str(cid) != str(uid):
        return send(cid, "برای حفظ حریم خصوصی، بلیت در گفت‌وگوی خصوصی ربات فرستاده می‌شود.")
    if not isinstance(response_id, str) or not _RESPONSE_ID.fullmatch(response_id):
        return send(cid, "⚠️ شناسهٔ پاسخ سروری معتبر نیست؛ بلیت از پایگاه محلی ساخته نمی‌شود.")
    try:
        ticket_data = shared_api.get_bot_form_ticket(uid, form_id, response_id)
    except shared_api.SharedAPIError as error:
        if error.code in {"ticket_not_eligible", "ticket_not_accepted"}:
            return None
        return _delivery_error(cid, error)
    return _deliver(cid, ticket_data)


def verify(cid: int | str, uid: int | str, response_id: str):
    """Staff-only shared ticket verification; no legacy SQLite lookup."""
    if str(cid) != str(uid):
        return send(cid, "استعلام بلیت فقط در گفت‌وگوی خصوصی ربات انجام می‌شود.")
    if not isinstance(response_id, str) or not _RESPONSE_ID.fullmatch(response_id):
        return send(cid, "❌ شناسهٔ بلیت معتبر نیست.")
    try:
        ticket_data = shared_api.verify_bot_form_ticket(uid, response_id)
    except shared_api.SharedAPIError as error:
        if error.status == 403:
            return send(cid, "🔒 این استعلام برای مسئولان دارای دسترسی بررسی پاسخ فرم است.")
        if error.status == 404:
            return send(cid, "❌ بلیت معتبر در پایگاه مشترک پیدا نشد.")
        return _delivery_error(cid, error)

    lines = [
        "🎫 بررسی بلیت سروری",
        "━━━━━━━━━━━━━━",
        f"📋 فرم: {ticket_data['form_title']}",
        f"👤 نام: {ticket_data['participant_name']}",
    ]
    ticket_type = ticket_data.get("ticket_type")
    if isinstance(ticket_type, dict) and isinstance(ticket_type.get("name"), str):
        lines.append(f"🎟 مدل بلیت: {ticket_type['name']}")
    lines.append(f"🔖 شماره ثبت: {ticket_data['serial']}")
    keyboard = None
    if ticket_data["checked_in"]:
        lines.extend(["", f"⚠️ این بلیت قبلاً استفاده شده است: {ticket_data['checked_in_at']}"])
    else:
        lines.extend(["", "✅ بلیت معتبر و استفاده‌نشده"])
        keyboard = {"inline_keyboard": [[{
            "text": "✅ ثبت ورود",
            "callback_data": "sftcheck_" + ticket_data["response_id"],
        }]]}
    return send(cid, "\n".join(lines), keyboard)


def check_in(cid: int | str, uid: int | str, response_id: str):  # noqa: PLR0911
    """Consume a ticket once through the role-checked shared API."""
    if str(cid) != str(uid):
        return send(cid, "ثبت ورود بلیت فقط در گفت‌وگوی خصوصی ربات انجام می‌شود.")
    if not isinstance(response_id, str) or not _RESPONSE_ID.fullmatch(response_id):
        return send(cid, "❌ شناسهٔ بلیت معتبر نیست.")
    try:
        result = shared_api.check_in_bot_form_ticket(uid, response_id)
    except shared_api.SharedAPIError as error:
        if error.status == 403:
            return send(cid, "🔒 فقط مسئول دارای دسترسی بررسی پاسخ فرم می‌تواند ورود را ثبت کند.")
        if error.status == 404:
            return send(cid, "❌ بلیت معتبر در پایگاه مشترک پیدا نشد.")
        return _delivery_error(cid, error)
    if result["already_checked_in"]:
        return send(cid, f"⚠️ این بلیت قبلاً استفاده شده است.\nشماره ثبت: {result['serial']}")
    return send(cid, f"✅ ورود در پایگاه مشترک ثبت شد.\nشماره ثبت: {result['serial']}")
