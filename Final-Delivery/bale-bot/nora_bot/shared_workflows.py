"""Bot views and adapters for workflows stored in the shared Nora API."""
from __future__ import annotations

from typing import Any
import os
import tempfile

import shared_api
from auth import clear_state, get_state_data, set_state
from bale_api import send, send_or_edit, send_photo, send_document, kb_cancel, kb_remove, BTN_BACK
from config import NORA_WEBAPP_URL
from database import log

STATE_REJECT = "shared_workflow_reject"

_PROFILE_LABELS = {
    "full_name": "نام و نام خانوادگی",
    "first_name": "نام",
    "last_name": "نام خانوادگی",
    "national_id": "کد ملی",
    "birth_date": "تاریخ تولد",
    "gender": "جنسیت",
    "father_name": "نام پدر",
    "mother_name": "نام مادر",
    "province": "استان",
    "city": "شهر",
    "address": "نشانی",
    "postal_code": "کد پستی",
    "education_level": "مقطع تحصیلی",
    "field_of_study": "رشته تحصیلی",
    "university": "دانشگاه یا مدرسه",
    "job_title": "شغل",
    "company_name": "محل کار",
    "email": "ایمیل",
    "bio": "معرفی کوتاه",
}


def _permission_for_kind(kind: str) -> str:
    return "us_approve" if kind == "profile_review" else "receipt_approve"


def _task_lines(task: dict[str, Any]) -> list[str]:
    data = task.get("payload") or {}
    if task.get("kind") == "profile_review":
        lines = ["📋 بررسی پروفایل", "━━━━━━━━━━━━━━"]
        for key, value in data.items():
            if key == "file_refs" or key.startswith("_legacy_"):
                continue
            if value is None or str(value).strip() == "" or key.endswith("_file_id"):
                continue
            label = _PROFILE_LABELS.get(key, key.replace("_", " "))
            lines.append(f"• {label}: {str(value)[:300]}")
        if data.get("file_refs"):
            lines.append("📎 تصویر پروفایل پیوست شده است.")
        if not any(line.startswith("•") for line in lines):
            lines.append("اطلاعاتی برای نمایش ثبت نشده است.")
    else:
        if data.get("registration_source") == "public_form":
            lines = ["🧾 بررسی فیش ثبت‌نام فرم وب", "━━━━━━━━━━━━━━"]
        else:
            amount = data.get("amount")
            amount_text = f"{amount:,}" if isinstance(amount, int) else "ثبت نشده"
            lines = [
                "🧾 بررسی فیش پرداخت",
                "━━━━━━━━━━━━━━",
                f"💰 مبلغ: {amount_text} ریال",
            ]
        for key, label in (
            ("event_title", "رویداد"),
            ("ref_code", "کد پیگیری"),
            ("transaction_id", "تراکنش"),
            ("registration_id", "ثبت‌نام"),
            ("form_id", "شناسهٔ فرم"),
            ("form_response_id", "پاسخ فرم"),
            ("submitted_at", "زمان ارسال"),
            ("note", "توضیح"),
        ):
            value = data.get(key)
            if value not in (None, ""):
                lines.append(f"• {label}: {str(value)[:300]}")
    lines += ["", f"🆔 کاربر: {task.get('bale_user_id') or '-'}", f"کد درخواست: {task['id'][:8]}"]
    return lines


def _send_private_attachment(
    cid: int, file_id: str, caption: str | None = None, file_name: str | None = None
) -> bool:
    try:
        content, content_type = shared_api.download_private_file(file_id)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ پیوست مشترک خوانده نشد: {exc.code}")
        return False
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}.get(content_type)
    if not suffix:
        return False
    name = str(file_name or "").replace(chr(92), "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable() and char not in {'"', "<", ">"})[:120]
    if not name:
        name = "attachment" + suffix
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="nora-file-", suffix=suffix)
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        if content_type.startswith("image/"):
            result = send_photo(cid, path, caption=caption, filename=name, content_type=content_type)
        else:
            result = send_document(cid, path, caption=caption, filename=name, content_type=content_type)
        return isinstance(result, dict) and result.get("ok") is True
    except Exception as exc:
        log(f"⚠️ ارسال پیوست مشترک انجام نشد: {type(exc).__name__}")
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _send_content_attachment(
    cid: int, delivery_id: str, *, caption: str | None = None
) -> bool:
    try:
        content, content_type, file_name = shared_api.download_content_file(delivery_id)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ فایل محتوای منتشرشده خوانده نشد: {exc.code}")
        return False
    suffix = {
        "application/pdf": ".pdf", "application/epub+zip": ".epub",
        "application/zip": ".zip", "application/x-zip-compressed": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.ms-powerpoint": ".ppt",
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    }.get(content_type)
    if not suffix:
        return False
    name = str(file_name or "").replace(chr(92), "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable() and char not in {'"', "<", ">"})[:120]
    if not name:
        name = "attachment" + suffix
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="nora-content-", suffix=suffix)
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        result = send_document(
            cid, path, caption=caption, filename=name, content_type=content_type
        )
        return isinstance(result, dict) and result.get("ok") is True
    except Exception as exc:
        log(f"⚠️ ارسال فایل منتشرشده انجام نشد: {type(exc).__name__}")
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def send_account_files(cid: int, uid: int) -> int:
    """Deliver only the current Bale user's private account files in a private chat."""
    if str(cid) != str(uid):
        send(cid, "برای حفظ حریم خصوصی، دریافت فایل‌های حسابت را در گفتگوی خصوصی ربات انجام بده.", kb_remove())
        return 0
    try:
        files = shared_api.list_private_files(uid)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ فهرست فایل‌های حساب خوانده نشد: {exc.code}")
        send(cid, "فهرست فایل‌های حساب فعلاً در دسترس نیست؛ بعداً دوباره تلاش کن.", kb_remove())
        return 0
    if not files:
        send(cid, "📭 فایلی برای دریافت در حساب بلهٔ شما ثبت نشده است.", kb_remove())
        return 0
    send(cid, f"📎 {len(files)} فایل خصوصی حساب شما؛ هر فایل جداگانه از همین‌جا ارسال می‌شود.")
    delivered = 0
    for item in files:
        if _send_private_attachment(cid, item["id"], caption=item["file_name"], file_name=item["file_name"]):
            delivered += 1
        else:
            send(cid, f"⚠️ ارسال «{item['file_name'][:100]}» انجام نشد؛ بعداً دوباره تلاش کن.")
    return delivered


def send_account_file(cid: int, uid: int, file_id: str) -> bool:
    """Deliver one private account attachment only to its matching Bale account."""
    if str(cid) != str(uid):
        send(cid, "برای حفظ حریم خصوصی، فایل را در گفتگوی خصوصی ربات دریافت کن.", kb_remove())
        return False
    try:
        files = shared_api.list_private_files(uid)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ فهرست فایل‌های حساب خوانده نشد: {exc.code}")
        send(cid, "فایل‌های حساب فعلاً در دسترس نیستند؛ بعداً دوباره تلاش کن.", kb_remove())
        return False
    item = next((row for row in files if row["id"] == file_id), None)
    if item is None:
        send(cid, "این فایل برای حساب بلهٔ شما ثبت نشده است.", kb_remove())
        return False
    if not _send_private_attachment(
        cid, file_id, caption=item["file_name"], file_name=item["file_name"]
    ):
        send(cid, "ارسال این فایل انجام نشد؛ بعداً دوباره تلاش کن.", kb_remove())
        return False
    return True


def send_content_file(cid: int, delivery_id: str) -> bool:
    """Deliver one published public asset after resolving it through the shared API."""
    if not _send_content_attachment(cid, delivery_id):
        send(cid, "این فایل از منبع مشترک دریافت نشد؛ از مدیر بخواه دوباره آن را منتشر کند.", kb_remove())
        return False
    return True


def show_inbox(
    cid: int,
    uid: int,
    *,
    kind: str | None = None,
    pre_list_notice: str | None = None,
    unavailable_notice: str | None = None,
) -> None:
    """Render pending tasks from the central API; never fall back to SQLite."""
    try:
        identity = shared_api.get_identity(uid)
        if kind:
            if not identity.has_permission(_permission_for_kind(kind)):
                return send(cid, "🔒 دسترسی این بخش برای حساب شما فعال نیست.", kb_remove())
        elif not (identity.has_permission("us_approve") or identity.has_permission("receipt_approve")):
            return send(cid, "🔒 دسترسی کارتابل برای حساب شما فعال نیست.", kb_remove())
        if pre_list_notice:
            send(cid, pre_list_notice, kb_remove())
        result = shared_api.list_workflows(uid, limit=50)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ کارتابل مشترک در دسترس نیست: {exc.code}")
        if unavailable_notice:
            send(cid, unavailable_notice, kb_remove())
        return send(cid, "کارتابل در دسترس نیست. اتصال به سرویس مشترک را بررسی کنید.", kb_remove())

    tasks = [task for task in result["items"] if kind is None or task.get("kind") == kind]
    if not tasks:
        return send_or_edit(cid, "✅ درخواستی در انتظار بررسی نیست.", {
            "inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": "admin_panel"}]]
        })

    send(cid, f"📥 {len(tasks)} درخواست در کارتابل:")
    for task in tasks:
        text = "\n".join(_task_lines(task))
        text = text[:3500]
        buttons = {"inline_keyboard": [
            [
                {"text": "✅ تأیید", "callback_data": f"wfok_{task['id']}"},
                {"text": "❌ رد", "callback_data": f"wfno_{task['id']}"},
            ],
        ]}
        data = task.get("payload") or {}
        file_refs = data.get("file_refs") if isinstance(data.get("file_refs"), list) else []
        if file_refs:
            if _send_private_attachment(cid, file_refs[0], caption=text[:900]):
                send(cid, "برای بررسی، پیوست را ببینید.", buttons)
            else:
                send(cid, text + "\n\nپیوست فعلاً در دسترس نیست.", buttons)
        else:
            photo_id = data.get("photo_file_id") or data.get("proof_file_id") or data.get("file_id")
            if task.get("kind") == "receipt_review" and isinstance(photo_id, str) and photo_id:
                send_photo(cid, photo_id, caption=text[:900], kb=buttons)
            else:
                send(cid, text, buttons)


def _find_pending_task(uid: int, task_id: str) -> dict[str, Any] | None:
    result = shared_api.list_workflows(uid, limit=100)
    return next((task for task in result["items"] if task.get("id") == task_id), None)


def approve_task(cid: int, uid: int, task_id: str) -> None:
    try:
        task = _find_pending_task(uid, task_id)
        if not task:
            return send(cid, "این درخواست قبلاً بررسی شده یا دیگر در کارتابل نیست.", kb_remove())
        identity = shared_api.get_identity(uid)
        if not identity.has_permission(_permission_for_kind(task["kind"])):
            return send(cid, "🔒 دسترسی لازم برای بررسی این درخواست را ندارید.", kb_remove())
        shared_api.decide_workflow(
            task_id, uid, "approved", expected_version=task["version"]
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ تأیید کارتابل انجام نشد: {exc.code}")
        return send(cid, "تأیید انجام نشد. درخواست را دوباره از کارتابل باز کنید.", kb_remove())
    send(cid, "✅ درخواست تأیید شد.", kb_remove())
    deliver_user_notifications(task.get("bale_user_id"))


def start_reject(cid: int, uid: int, task_id: str) -> None:
    try:
        task = _find_pending_task(uid, task_id)
        if not task:
            return send(cid, "این درخواست قبلاً بررسی شده یا دیگر در کارتابل نیست.", kb_remove())
        identity = shared_api.get_identity(uid)
        if not identity.has_permission(_permission_for_kind(task["kind"])):
            return send(cid, "🔒 دسترسی لازم برای بررسی این درخواست را ندارید.", kb_remove())
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ کارتابل مشترک در دسترس نیست: {exc.code}")
        return send(cid, "کارتابل در دسترس نیست. اتصال به سرویس مشترک را بررسی کنید.", kb_remove())
    set_state(uid, STATE_REJECT, {
        "task_id": task_id,
        "expected_version": task["version"],
        "target_bale_user_id": task.get("bale_user_id"),
    }, merge=False)
    send(cid, "دلیل رد را بنویسید؛ برای رد بدون توضیح «-» را بفرستید.", kb_cancel())


def handle_reject_reason(message: dict[str, Any]) -> None:
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text == BTN_BACK:
        clear_state(uid)
        return send(cid, "عملیات لغو شد.", kb_remove())
    state = get_state_data(uid)
    task_id = state.get("task_id")
    version = state.get("expected_version")
    clear_state(uid)
    if not task_id or not version:
        return send(cid, "درخواست پیدا نشد. کارتابل را دوباره باز کنید.", kb_remove())
    reason = "" if text in ("-", "—") else text[:500]
    try:
        shared_api.decide_workflow(
            task_id, uid, "rejected", reason, expected_version=int(version)
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ رد درخواست انجام نشد: {exc.code}")
        return send(cid, "رد درخواست انجام نشد. کارتابل را دوباره باز کنید.", kb_remove())
    send(cid, "❌ درخواست رد شد.", kb_remove())
    deliver_user_notifications(state.get("target_bale_user_id"))


def _notification_webapp_button(item: dict[str, Any]) -> dict[str, Any] | None:
    """فاز ۹.۴: اگر سرور پیوند نسبی صفحهٔ داخل برنامه داده و وب‌اپ تنظیم است، دکمهٔ بازکردن مینی‌اپ.

    فقط مسیر نسبی صفحه (event/account) پذیرفته می‌شود؛ هیچ نشانی مطلق/فایل از اعلان به دکمه نمی‌رسد.
    """
    link = item.get("link")
    if not NORA_WEBAPP_URL or not isinstance(link, str) or not link.startswith("/") or link.startswith("//"):
        return None
    if "/api/" in link or ".." in link or "\\" in link:
        return None
    return {"inline_keyboard": [[{"text": "🔗 باز کردن در مینی‌اپ", "web_app": {"url": NORA_WEBAPP_URL + link}}]]}


def _deliver_notification_content(item: dict[str, Any], target: int | str) -> bool:
    body = item["title"]
    if item.get("body"):
        body += "\n\n" + item["body"]
    try:
        button = _notification_webapp_button(item)
        result = send(target, body[:3500], button) if button else send(target, body[:3500])
    except Exception as exc:
        log(f"⚠️ ارسال متن اعلان انجام نشد: {type(exc).__name__}")
        return False
    if not (isinstance(result, dict) and result.get("ok") is True):
        return False
    refs = item.get("file_refs") if isinstance(item.get("file_refs"), list) else []
    if not refs:
        return True
    try:
        own_files = shared_api.list_private_files(target)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ پیوست اعلان خوانده نشد: {exc.code}")
        return False
    by_id = {file["id"]: file for file in own_files}
    for file_id in refs:
        file = by_id.get(file_id) if isinstance(file_id, str) else None
        if file is None:
            log("⚠️ پیوست اعلان در فهرست همان حساب پیدا نشد")
            return False
        if not _send_private_attachment(
            target, file_id, caption=file["file_name"], file_name=file["file_name"]
        ):
            return False
    return True


def deliver_user_notifications(bale_user_id: int | str | None) -> int:
    """Deliver one user's central outbox messages with provider acknowledgements."""
    if bale_user_id is None:
        return 0
    try:
        items = shared_api.list_notifications(bale_user_id)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ اعلان مشترک خوانده نشد: {exc.code}")
        return 0
    delivered = 0
    for item in items:
        try:
            if _deliver_notification_content(item, bale_user_id):
                shared_api.mark_notification_delivered(item["id"], bale_user_id)
                delivered += 1
            else:
                shared_api.mark_notification_failed(item["id"], bale_user_id)
        except shared_api.SharedAPIError as exc:
            log(f"⚠️ ثبت وضعیت اعلان انجام نشد: {exc.code}")
    return delivered


def deliver_pending_notifications(limit: int = 50) -> int:
    """Drain the shared notification queue; a failed API call is a no-op."""
    try:
        items = shared_api.list_pending_notifications(limit=limit)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ صف اعلان مشترک در دسترس نیست: {exc.code}")
        return 0
    delivered = 0
    for item in items:
        target = item["bale_user_id"]
        try:
            if _deliver_notification_content(item, target):
                shared_api.mark_notification_delivered(item["id"], target)
                delivered += 1
            else:
                shared_api.mark_notification_failed(item["id"], target)
        except shared_api.SharedAPIError as exc:
            log(f"⚠️ ثبت وضعیت اعلان انجام نشد: {exc.code}")
    return delivered


def sync_workflow_projections(limit: int = 50) -> int:
    """Apply approved shared workflow data to bot features as an idempotent projection."""
    try:
        tasks = shared_api.list_workflow_projections(limit=limit)
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ همگام‌سازی کارتابل مشترک در دسترس نیست: {exc.code}")
        return 0
    applied = 0
    for task in tasks:
        try:
            if task["kind"] == "profile_review":
                import profile as profile_mod
                profile_mod.apply_shared_review_projection(task)
            else:
                import payments as payments_mod
                payments_mod.apply_shared_review_projection(task)
            shared_api.mark_workflow_projection_applied(task["id"])
            applied += 1
        except Exception as exc:
            log(f"⚠️ همگام‌سازی درخواست {task['id'][:8]} انجام نشد: {type(exc).__name__}")
            try:
                shared_api.mark_workflow_projection_failed(task["id"])
            except shared_api.SharedAPIError as api_exc:
                log(f"⚠️ ثبت خطای همگام‌سازی انجام نشد: {api_exc.code}")
    return applied
