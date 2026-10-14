"""Conversational bot views over aggregate reports from the shared API only."""
from __future__ import annotations

import shared_api
from bale_api import send_or_edit


_PERIODS = {
    "today": "امروز",
    "yesterday": "دیروز",
    "7d": "۷ روز اخیر",
    "30d": "۳۰ روز اخیر",
    "90d": "۹۰ روز اخیر",
    "year": "یک سال اخیر",
    "all": "از ابتدا",
}
_SELECTED_PERIOD: dict[str, str] = {}
_DIGITS = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")

_SECTION_TITLES = {
    "rp_events": "گزارش رویدادها",
    "rp_users": "گزارش کاربران",
    "rp_forms": "گزارش فرم‌ها",
    "rp_att": "گزارش حضور و غیاب",
    "rp_finance": "گزارش مالی",
    "rp_certs": "گزارش گواهینامه‌ها",
    "rp_notify": "گزارش اطلاع‌رسانی",
    "rp_admins": "گزارش ادمین‌ها",
    "rp_top": "برترین‌ها",
    "rp_export": "خروجی گزارش",
}


def _count(value: int) -> str:
    return format(value, ",").translate(_DIGITS)


def _authorize(cid, uid):
    try:
        identity = shared_api.get_identity(uid)
    except shared_api.SharedAPIError as exc:
        if exc.status == 403:
            message = "🔒 دسترسی به داشبورد گزارشات سروری برای این حساب فعال نیست."
        else:
            message = "📊 داشبورد گزارشات سروری در دسترس نیست؛ هیچ آمار محلی جایگزین نشد."
        send_or_edit(cid, message)
        return None
    if not identity.has_permission("rp_view"):
        send_or_edit(cid, "🔒 دسترسی به داشبورد گزارشات سروری برای این نقش فعال نیست.")
        return None
    return identity


def _summary(cid, uid, period):
    try:
        return shared_api.get_report_summary(uid, period)
    except shared_api.SharedAPIError as exc:
        if exc.status == 403:
            message = "مجوز مشاهدهٔ گزارش سروری برای این نقش فعال نیست."
        elif exc.status == 0 or exc.status == 503:
            message = "پایگاه مشترک در دسترس نیست؛ هیچ آمار محلی جایگزین نشد."
        else:
            message = "گزارش سروری خوانده نشد؛ دادهٔ محلی نمایش داده نمی‌شود."
        send_or_edit(cid, message)
        return None


def _status_lines(title, counts, labels):
    if not counts:
        return [f"{title}: موردی ثبت نشده است."]
    lines = [title + ":"]
    for key, value in sorted(counts.items()):
        if type(value) is not int or value < 0:
            continue
        lines.append(f"• {labels.get(key, 'سایر وضعیت‌ها')}: {_count(value)}")
    return lines


def _dashboard_keyboard(identity):
    rows = [
        [
            {"text": "👥 کاربران", "callback_data": "rp_users"},
            {"text": "📝 فرم‌ها و پاسخ‌ها", "callback_data": "rp_forms"},
        ],
        [
            {"text": "📢 اعلان‌ها", "callback_data": "rp_notify"},
            {"text": "🎉 رویدادها", "callback_data": "rp_events"},
        ],
        [
            {"text": "✋ حضور", "callback_data": "rp_att"},
            {"text": "🎓 گواهی‌ها", "callback_data": "rp_certs"},
        ],
    ]
    if identity.role == "owner":
        rows.append([
            {"text": "💰 مالی", "callback_data": "rp_finance"},
            {"text": "👨‍💼 ادمین‌ها", "callback_data": "rp_admins"},
        ])
    rows.extend([
        [{"text": "🏆 برترین‌ها", "callback_data": "rp_top"}],
        [{"text": "📅 تغییر دوره", "callback_data": "rp_period"}],
    ])
    if identity.has_permission("rp_export"):
        rows.append([{"text": "📥 خروجی گزارش", "callback_data": "rp_export"}])
    rows.extend([
        [{"text": "🎲 قرعه‌کشی‌ها", "callback_data": "lt_all"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}],
    ])
    return {"inline_keyboard": rows}


def show_dashboard(cid, uid):
    """Show only approved aggregates from the shared backend, never local SQL."""
    identity = _authorize(cid, uid)
    if identity is None:
        return
    period = _SELECTED_PERIOD.get(str(uid), "30d")
    data = _summary(cid, uid, period)
    if data is None:
        return

    accounts = data["accounts"]
    account_total = accounts["total"]
    account_text = _count(account_total) if type(account_total) is int else "در دسترس نیست"
    lines = [
        "📊 داشبورد گزارشات · گزارش‌های زندهٔ پایگاه مشترک",
        "━━━━━━━━━━━━━━",
        f"📅 دوره: {_PERIODS[period]}",
        "",
        "آمار زیر فقط از API و پایگاه سرور است؛ دادهٔ مرورگر یا SQLite ربات جایگزین نمی‌شود.",
        "",
        f"📝 کل فرم‌های سرور: {_count(data['forms']['total'])}",
        f"📄 پاسخ‌های نهایی این دوره: {_count(data['responses']['total'])}",
        f"🔎 درخواست‌های بررسی این دوره: {_count(data['reviews']['total'])}",
        f"👥 حساب‌های بله: {account_text}",
        f"📢 اعلان‌های ثبت‌شده: {_count(data['notifications']['total'])}",
        "🎉 رویدادها: هنوز در گزارش پایگاه مشترک ثبت نمی‌شوند.",
        "⚡ فعالیت لحظه‌ای: در دادهٔ تجمیعی سرور موجود نیست.",
    ]
    cooperation = data["cooperation_requests"]
    if cooperation is not None:
        lines.append(f"🤝 درخواست‌های همکاری: {_count(cooperation['total'])}")
    lines.extend([
        "",
        "گزارش مالی، رویداد، حضور و گواهی تا ثبت همان داده‌ها در پایگاه مشترک در دسترس نیست.",
    ])
    return send_or_edit(cid, "\n".join(lines), _dashboard_keyboard(identity))


def show_periods(cid, uid):
    identity = _authorize(cid, uid)
    if identity is None:
        return
    current = _SELECTED_PERIOD.get(str(uid), "30d")
    lines = ["📅 انتخاب دوره زمانی · گزارش سروری", "━━━━━━━━━━━━━━", ""]
    buttons = []
    for key, label in _PERIODS.items():
        marker = "🔘" if key == current else "⚪"
        lines.append(f"{marker} {label}")
        buttons.append([{"text": f"{marker} {label}", "callback_data": f"rp_p_{key}"}])
    buttons.append([{"text": "🔙 گزارش‌های زنده", "callback_data": "admin_stats"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": buttons})


def pick_period(cid, uid, key):
    if key not in _PERIODS:
        return send_or_edit(cid, "بازهٔ این دکمه پشتیبانی نمی‌شود؛ گزارش تازه را از منوی گزارش‌ها باز کن.")
    if _authorize(cid, uid) is None:
        return
    _SELECTED_PERIOD[str(uid)] = key
    return show_dashboard(cid, uid)


def show_section(cid, uid, key):
    title = _SECTION_TITLES.get(key)
    if title is None:
        return send_or_edit(cid, "این پیوند گزارش معتبر نیست.")
    identity = _authorize(cid, uid)
    if identity is None:
        return
    if key in {"rp_finance", "rp_admins"} and identity.role != "owner":
        return send_or_edit(cid, "🔒 دسترسی این گزارش فقط برای مالک سروری است.")
    if key == "rp_export" and not identity.has_permission("rp_export"):
        return send_or_edit(cid, "🔒 دسترسی به خروجی گزارش برای این نقش فعال نیست.")

    period = _SELECTED_PERIOD.get(str(uid), "30d")
    if key not in {"rp_users", "rp_forms", "rp_notify"}:
        return send_or_edit(
            cid,
            f"{title}\n━━━━━━━━━━━━━━\n\n"
            "این داده هنوز در پایگاه مشترک ثبت نمی‌شود؛ برای جلوگیری از نمایش عدد محلی یا نادقیق، گزارشی جایگزین نشده است.",
            {"inline_keyboard": [[{"text": "🔙 گزارش‌های زنده", "callback_data": "admin_stats"}]]},
        )

    data = _summary(cid, uid, period)
    if data is None:
        return
    lines = [title, "━━━━━━━━━━━━━━", f"📅 دوره: {_PERIODS[period]}", ""]
    if key == "rp_users":
        account_data = data["accounts"]
        total = account_data["total"]
        lines.append(f"کل حساب‌های تأییدشدهٔ بله: {_count(total)}" if type(total) is int
                     else "شمار حساب‌ها با مجوز این نقش در دسترس نیست.")
        role_labels = {"owner": "مالک", "manager": "مدیر", "club-supervisor": "سرپرست باشگاه"}
        lines.extend(_status_lines("شمار حساب‌ها بر اساس نقش", account_data["by_role"] or {}, role_labels))
    elif key == "rp_forms":
        lines.append(f"کل فرم‌های سرور: {_count(data['forms']['total'])}")
        lines.append(f"فرم‌های ساخته‌شده در دوره: {_count(data['forms']['created_in_period'])}")
        lines.extend(_status_lines("وضعیت فرم‌ها", data["forms"]["by_status"], {
            "draft": "پیش‌نویس", "published": "منتشرشده", "paused": "متوقف",
        }))
        lines.extend(["", f"پاسخ‌های نهایی در دوره: {_count(data['responses']['total'])}"])
        lines.extend(_status_lines("وضعیت پاسخ‌ها", data["responses"]["by_status"], {
            "accepted": "پذیرفته‌شده", "waitlisted": "فهرست انتظار",
        }))
        lines.extend(["", f"درخواست‌های بررسی در دوره: {_count(data['reviews']['total'])}"])
        for kind, statuses in sorted(data["reviews"]["by_kind"].items()):
            kind_label = "پروفایل" if kind == "profile_review" else "فیش"
            lines.extend(_status_lines(f"بررسی {kind_label}", statuses, {
                "pending": "در انتظار", "approved": "تأییدشده", "rejected": "ردشده",
            }))
    else:
        lines.append(f"اعلان‌های ثبت‌شده در دوره: {_count(data['notifications']['total'])}")
        lines.extend(_status_lines("وضعیت تحویل اعلان‌ها", data["notifications"]["by_delivery_status"], {
            "pending": "در انتظار", "delivered": "تحویل‌شده", "failed": "ناموفق",
        }))
        cooperation = data["cooperation_requests"]
        if cooperation is not None:
            lines.extend(["", f"درخواست‌های همکاری: {_count(cooperation['total'])}"])
            lines.extend(_status_lines("وضعیت درخواست‌های همکاری", cooperation["by_status"], {
                "new": "تازه", "reviewing": "در حال بررسی", "accepted": "پذیرفته‌شده",
                "rejected": "ردشده",
            }))
    buttons = []
    if key == "rp_forms" and identity.has_permission("fm_responses"):
        buttons.append([{
            "text": "📄 مشاهدهٔ پاسخ‌های هر فرم",
            "callback_data": "sfr_forms",
        }])
    buttons.append([{"text": "🔙 گزارش‌های زنده", "callback_data": "admin_stats"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": buttons})
