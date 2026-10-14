"""
ربات نورا — فاز ۵
گروه فرهنگی و اجتماعی خط زندگی

معماری (طبق برنامه‌ریزی):
  🎯 هسته: رویدادها → ثبت‌نام → پرداخت → بلیت → حضور → گواهینامه → گزارش
  📝 کمکی: فرم‌ساز (فاز بعد)
  👤 کاربر: پروفایل، امتیاز، دعوت، اعلان، پشتیبانی
  ⚙️ ادمین: کاربران، داشبورد، تنظیمات (همه متن‌ها داینامیک)

جدید در فاز ۵:
  • رویدادها (۸ نوع، کامل)
  • پرداخت کیف پول بله (sendInvoice + PreCheckout + SuccessfulPayment)
  • OTP سفیر اصلاح‌شده (bot_id جدا از بات اصلی)
  • 👍 لایک خودکار روی پیام کاربران عادی
  • متن‌های قابل تغییر از پنل ادمین
  • فرم رضایت‌سنجی (askReview)
"""
import os
import sys
import time
import traceback
from datetime import datetime

from config import (
    BOT_TOKEN, SUPER_ADMIN_ID, BOT_NAME, ORG_NAME, VERSION,
    brand, org_name, bot_name,
    SAFIR_ENABLED, SAFIR_BOT_ID, MAIN_BOT_ID,
    PAYMENT_ENABLED, PAYMENT_TEST_MODE,
    AUTO_REACT_ENABLED, AUTO_REACT_EMOJI, AUTO_REACT_ADMINS,
    check_config, config_warnings,
)
from database import (
    init_db, db_execute, db_scalar, log, close_db,
    seed_default_settings, get_setting, cleanup_expired,
    auto_backup, backup_stats,
)
from bale_api import (
    send, send_or_edit, set_context, clear_context, forget_menu,
    answer_callback, get_updates, get_me, set_reaction,
    kb_auth, kb_contact, kb_cancel, kb_otp, kb_remove,
    kb_main, kb_admin, kb_force_join, kb_settings, BTN_BACK,
    kb_persistent, ensure_persistent, reset_persistent, MAIN_MENU_BUTTONS,
    BTN_EVENTS, BTN_FORMS, BTN_PROFILE, BTN_ATTEND, BTN_INVITE,
    BTN_NOTIF, BTN_SUPPORT, BTN_HOME, BTN_ADMIN,
    BTN_ADM_USERS, BTN_ADM_FORMS, BTN_ADM_REPORTS, BTN_ADM_SETTINGS,
    BTN_USER_VIEW,
)
from auth import (
    get_user, get_user_by_mobile, set_state, get_state, get_state_name,
    get_state_data, clear_state, create_auth_user, link_bale,
    update_activity, log_action, update_percent, normalize_mobile,
    normalize_digits, generate_otp, save_otp, verify_otp,
    send_otp_via_safir, can_resend_otp, get_active_channels,
    check_user_joined, ensure_super_admin, is_admin, is_blocked,
)
import profile as profile_mod
import admin as admin_mod
import shared_workflows as shared_workflows_mod
import import_excel as imp_mod
import events as ev_mod
import settings_admin as set_mod
import attendance as att_mod
import guard
import payments as pay_mod
import forms as fb_mod
import form_fields as ff_mod
import form_fill as fill_mod
import shared_form_flow as shared_form_flow_mod
import shared_form_ticket as shared_form_ticket_mod
import form_reports as frep_mod
import occasions as oc_mod
import permissions as perm_mod
import activity_log as alog_mod
import finance as fin_mod
import club as club_mod
import tickets as tk_mod
import lottery as lt_mod
import shared_reports as shared_reports_mod
import shared_form_reports as shared_form_reports_mod
import paylink as pl_mod
import payplan as pp_mod
import about as ab_mod
import certgen as cg_mod
import certissue as ci_mod
import jalali as _jd
import infra_fee as inf_mod
import ticket as ftk_mod
import eventcert as evc_mod
import certbatch as cb_mod
import certcenter as cc_mod
import attendance_auto as aa_mod
import survey as sv_mod
import certverify as cv_mod
import ads as ads_mod


# ==================== منوها ====================
# 🆕 فاز ۱۳: ادمین‌های کامل که موقتاً «نمای کاربر» را روشن کرده‌اند
#    (فقط در حافظه — با ریستارت ربات پاک می‌شود، که درست است)
_user_view = {}


def set_user_view(uid, on=True):
    """روشن/خاموش کردن «نمای کاربر» برای یک ادمین کامل"""
    if on:
        _user_view[uid] = True
    else:
        _user_view.pop(uid, None)
    from bale_api import reset_persistent
    reset_persistent()


def in_user_view(uid):
    return bool(_user_view.get(uid))


def _menu_flags(uid):
    """(admin, full) — با در نظر گرفتن «نمای کاربر»"""
    adm = is_admin(uid)
    if not adm:
        return False, False
    if _user_view.get(uid):
        return True, False
    try:
        return True, perm_mod.is_full_admin(uid)
    except Exception:
        return True, uid == SUPER_ADMIN_ID


def show_main_menu(cid, user, db_user=None, force_kb=False, as_user=None):
    """
    🏠 صفحه اصلی.

    🔴 فاز ۱۳: سوپرادمین و «ادمین کامل» منوی کاربر عادی را نمی‌بینند —
       برایشان منوی مدیریتی خالص نمایش داده می‌شود.
       با «👤 نمای کاربر» می‌توانند موقتاً منوی کاربر را ببینند
       (as_user=True) و با «👨‍💼 پنل ادمین» برگردند.
    """
    uid = user.get("id")
    if db_user is None:
        db_user = get_user(uid) or {}

    is_super = (uid == SUPER_ADMIN_ID)
    admin_flag = is_super or bool(db_user.get("is_admin"))

    # ادمین کامل / سوپرادمین → منوی مدیریتی
    try:
        full_flag = admin_flag and perm_mod.is_full_admin(uid)
    except Exception:
        full_flag = is_super
    if as_user is None:
        as_user = _user_view.get(uid, False)
    if as_user:
        full_flag = False

    role = "سوپرادمین 👑" if is_super else ("ادمین 👨‍💼" if admin_flag else "کاربر 👤")

    name = db_user.get("first_name") or user.get("first_name") or "کاربر"

    if full_flag:
        # ═══ منوی مدیریتی خالص (سوپرادمین / ادمین کامل) ═══
        lines = [
            f"🏠 {brand()}",
            org_name(),
            "━━━━━━━━━━━━━━",
            "",
            f"👋 سلام {name}!",
            f"🎭 {role}",
            "",
        ]
        try:
            n_ev = db_scalar("SELECT COUNT(*) FROM events "
                             "WHERE status='published'") or 0
            n_us = db_scalar("SELECT COUNT(*) FROM users") or 0
            n_pd = db_scalar("SELECT COUNT(*) FROM profile_submissions "
                             "WHERE status='pending'") or 0
            lines += [
                "📊 یک نگاه سریع:",
                f"├── 👥 کاربران: {n_us}",
                f"├── 🎉 رویداد فعال: {n_ev}",
                f"└── ⏳ درخواست پروفایل: {n_pd}",
            ]
            n_tk = db_scalar("SELECT COUNT(*) FROM tickets "
                             "WHERE unread_admin=1") or 0
            if n_tk:
                lines.append(f"🔴 {n_tk} تیکت خوانده‌نشده")
        except Exception:
            pass
        lines += ["", "👇 از دکمه‌های پایین صفحه انتخاب کنید",
                  "💡 «👤 نمای کاربر» = دیدن ربات از چشم کاربر عادی"]
    else:
        percent = int(db_user.get("complete_profile_percent") or 0)
        blocks = max(0, min(10, percent // 10))
        bar = "▓" * blocks + "░" * (10 - blocks)

        lines = [
            f"🏠 {brand()}",
            org_name(),
            "━━━━━━━━━━━━━━",
            "",
            f"👋 سلام {name}!",
            f"🎭 {role}",
        ]
        if db_user.get("mobile"):
            lines.append(f"📱 {db_user['mobile']}")

        lines += ["", f"📊 تکمیل پروفایل: {percent}%", bar]

        status = db_user.get("profile_status") or "draft"
        if status == "pending":
            lines += ["", "⏳ پروفایل شما در انتظار تأیید ادمین است"]
        elif status == "approved":
            lines += ["", "✅ پروفایل شما تأیید شده است"]
        elif status == "rejected":
            reason = db_user.get("rejection_reason")
            lines += ["", "❌ پروفایل شما رد شد"
                      + (f" — {reason}" if reason else "")]
        elif percent < 50:
            lines += ["", "💡 لطفاً پروفایل خود را تکمیل کنید"]

        # تعداد رویدادهای فعال
        active_ev = db_scalar("SELECT COUNT(*) FROM events "
                              "WHERE status='published'")
        if active_ev:
            lines += ["", f"🎉 {active_ev} رویداد فعال — از منو ببینید"]

        # تعداد فرم‌های فعال
        try:
            active_fm = db_scalar("SELECT COUNT(*) FROM forms "
                                  "WHERE status='active'")
            if active_fm:
                lines += [f"📝 {active_fm} فرم فعال — از منو ببینید"]
        except Exception:
            pass

        lines += ["", "👇 از دکمه‌های پایین صفحه انتخاب کنید"]
        if admin_flag and as_user:
            lines.append("💡 «👨‍💼 پنل ادمین» = بازگشت به منوی مدیریتی")

    # ═══════════════════════════════════════════════════
    # 🎯 فقط یک منو: دکمه‌های پایین صفحه
    #
    # ⚠️ باگ رفع‌شده: وقتی کاربر از یک پیام شیشه‌ای (مثل پنل ادمین)
    #    دکمه «بازگشت» را می‌زد، ensure_persistent می‌گفت «قبلاً
    #    فرستادم» و پیام با kb=None ویرایش می‌شد → کاربر هیچ منویی
    #    نداشت. حالا اگر از callback آمده باشیم، حتماً پیام تازه با
    #    کیبورد پایین می‌فرستیم.
    # ═══════════════════════════════════════════════════
    from bale_api import ensure_persistent, from_callback

    if force_kb or from_callback(cid) or \
            ensure_persistent(cid, admin_flag, is_full=full_flag):
        ensure_persistent(cid, admin_flag, is_full=full_flag)
        send(cid, "\n".join(lines), kb_main(admin_flag, full_flag))
    else:
        send_or_edit(cid, "\n".join(lines))


def show_force_join(cid, uid, not_joined):
    intro = get_setting("msg_force_join",
                        "⚠️ برای استفاده از ربات، ابتدا در کانال/گروه‌های زیر عضو شوید:")
    lines = ["🔗 عضویت اجباری", "━━━━━━━━━━━━━━", "", intro, ""]
    for ch in not_joined:
        icon = "🔒" if ch.get("is_private") else "📢"
        lines.append(f"{icon} {ch.get('channel_title') or ch.get('channel_username') or ''}")
    lines += ["", "✅ بعد از عضویت، دکمه «بررسی عضویت» را بزنید"]
    send(cid, "\n".join(lines), kb_force_join(not_joined))


def gate_force_join(cid, uid):
    if is_admin(uid):
        return False
    channels = get_active_channels()
    if not channels:
        return False
    not_joined = check_user_joined(uid, channels)
    if not_joined:
        show_force_join(cid, uid, not_joined)
        return True
    return False


# ==================== احراز هویت ====================
def handle_start(msg):
    user = msg.get("from", {})
    cid = msg["chat"]["id"]
    uid = user["id"]
    text = (msg.get("text") or "").strip()

    clear_state(uid)
    param = text.split(" ", 1)[1].strip() if " " in text else ""

    if uid == SUPER_ADMIN_ID:
        ensure_super_admin(uid, user.get("first_name") or "سوپرادمین")
        update_activity(uid)
        log_action(uid, "start")
        if param.startswith(("ft_", "ftv_")):
            return handle_deep_link(cid, uid, param, user)
        return show_main_menu(cid, user, force_kb=True)

    db_user = get_user(uid)

    if db_user and db_user.get("is_blocked"):
        return send(cid, get_setting("msg_blocked", "🚫 دسترسی شما مسدود شده است."))

    # Public-form ticket tokens are signed, single-purpose handoffs; they bind
    # this Bale user to the response and need no separate bot-account login.
    if param.startswith("ft_"):
        return handle_deep_link(cid, uid, param, user)

    # deep link: /start EV123 یا /start کد_دعوت
    if db_user and db_user.get("is_authenticated"):
        update_activity(uid)
        if gate_force_join(cid, uid):
            return
        log_action(uid, "start")
        if param:
            return handle_deep_link(cid, uid, param, user)
        return show_main_menu(cid, user, db_user, force_kb=True)

    welcome = get_setting("msg_welcome", "👋 به {bot} خوش آمدید!\n{org}")
    # 🏷️ فاز ۱۸-ج — هویت پویا در متن خوش‌آمد
    welcome = (welcome.replace("{bot}", brand())
                      .replace("{org}", org_name())
                      .replace("{name}", bot_name()))
    auth_msg = get_setting("msg_auth", "🔐 برای شروع، احراز هویت کنید:")
    send(cid, f"{welcome}\n━━━━━━━━━━━━━━\n\n{auth_msg}", kb_auth())
    set_state(uid, "waiting_auth", {"deep": param} if param else {}, merge=False)
    log_action(uid, "start_unauth")


def verify_certificate(cid, uid, serial):
    """
    🎓 فاز ۱۹ — بررسی اصالت گواهینامه با اسکن کیوآرکد.

    هرکسی (حتی بدون احراز هویت) می‌تواند اصالت را بررسی کند —
    این اصلاً هدف کیوآرکد است.
    """
    serial = (serial or "").strip()
    if not serial:
        return send(cid, "⚠️ شماره گواهینامه مشخص نیست")

    # 🔍 فاز ۳۴ — گزارش یکپارچه با اعتبار زمانی
    #    (کیوآرهای قدیمی هم اینجا جواب می‌گیرند)
    try:
        _r, _why = cv_mod.find(code=serial)
        if _r:
            _k, _i, _l = cv_mod.status_of(_r)
            cv_mod.log_verify(_r, uid, "qr", _k, serial)
            return send(cid, cv_mod.report(_r), {"inline_keyboard": [
                [{"text": "🔍 استعلام دیگر",
                  "callback_data": "cv_ask"}]]})
    except Exception as _e:
        log(f"⚠️ استعلام تازه: {_e}")

    row = db_execute("""SELECT c.*, u.first_name, u.last_name,
        u.national_id, e.title ev_title, e.start_date
        FROM certificates c
        LEFT JOIN users u ON u.bale_user_id=c.bale_user_id
        LEFT JOIN events e ON e.id=c.event_id
        WHERE c.serial=?""", (serial,), fetch="one")

    if not row:
        return send(cid, (
            f"❌ گواهینامه یافت نشد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🔖 شماره: {serial}\n\n"
            f"⚠️ این شماره در سامانه ثبت نشده است.\n"
            f"اگر فکر می‌کنید اشتباهی رخ داده، با ما تماس بگیرید."))

    if row.get("revoked"):
        return send(cid, (
            f"🚫 این گواهینامه باطل شده است\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🔖 شماره: {serial}"))

    nm = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
    nid = str(row.get("national_id") or "")
    if len(nid) >= 4:
        nid = nid[:3] + "*" * (len(nid) - 5) + nid[-2:]

    lines = [
        "✅ گواهینامه معتبر است",
        "━━━━━━━━━━━━━━", "",
        f"👤 دارنده: {nm or '—'}",
    ]
    if nid:
        lines.append(f"🆔 کد ملی: {nid}")
    lines += [
        f"🎓 عنوان: {row.get('ev_title') or '—'}",
        f"📅 تاریخ: {row.get('start_date') or '—'}",
        f"🔖 شماره: {row.get('serial')}",
        f"📆 صدور: {_jd.fmt(row.get('issued_at'), 'date')}",
        "", f"🏢 {org_name()}",
    ]
    return send(cid, "\n".join(lines))


def handle_deep_link(cid, uid, param, user):
    """
    پردازش پارامتر /start
      • کد رویداد (EV...) → نمایش رویداد
      • کد معرف (NORA...) → ثبت رابطه دعوت
    """
    param = (param or "").strip()
    if not param:
        return show_main_menu(cid, user)

    if param in {"mycerts", "myfiles"} and str(cid) != str(uid):
        return send(cid, "این دریافت برای حفظ حریم خصوصی فقط در گفتگوی خصوصی ربات انجام می‌شود.")
    if param == "mycerts":
        return att_mod.my_certificates(cid, uid)
    if param == "myfiles":
        return shared_workflows_mod.send_account_files(cid, uid)
    if param.startswith("private_"):
        return shared_workflows_mod.send_account_file(cid, uid, param[8:])
    if param.startswith("file_"):
        return shared_workflows_mod.send_content_file(cid, param[5:])

    # 🎫 فرم‌های سروری: لینک claim امن و QR اعتبارسنجی از پایگاه مشترک.
    if param.startswith("ftv_"):
        return shared_form_ticket_mod.verify(cid, uid, param[4:])
    if param.startswith("ft_"):
        return shared_form_ticket_mod.deliver_claim(cid, uid, param[3:])

    # 📝 لینک فرم:  ?start=form_<slug>
    if param.startswith("form_"):
        return fill_mod.open_form(cid, uid, param[5:], user)

    # 🔗 لینک پرداخت غیرمتمرکز:  ?start=pay_<code>
    if param.startswith("pay_"):
        return pl_mod.open_link(cid, uid, param[4:], user)

    # 🎓 فاز ۱۹ — اعتبارسنجی گواهینامه:  ?start=cert_<serial>
    if param.startswith("cert_"):
        return verify_certificate(cid, uid, param[5:])

    # 🎟️ فاز ۳۲ — دریافت گواهینامه با لینک دسته: ?start=gc_<code>
    # ⏱️ فاز ۳۳ — ثبت حضور با لینک یک‌بارمصرف: ?start=at_<token>
    if param.startswith("at_"):
        return aa_mod.user_token(cid, uid, param[3:])

    # 🔍 فاز ۳۴ — استعلام با شناسهٔ دولایه: ?start=cv_<کد>
    if param.startswith("cv_"):
        return cv_mod.handle_scan(cid, uid, param[3:])

    # 🏛️ فاز ۳۶ — دریافت گواهینامه با لینک مرکز صدور
    if param.startswith("cc_"):
        return cc_mod.claim_by_link(cid, uid, param[3:], user)

    if param.startswith("gc_"):
        return cb_mod.handle_claim(cid, uid, param[3:], user)

    # 🎫 اعتبارسنجی بلیت فرم:  ?start=verify_<qr>
    if param.startswith("verify_"):
        return verify_form_ticket(cid, uid, param[7:])

    # کد معرف
    ref = db_execute(
        "SELECT bale_user_id, first_name FROM users WHERE referral_code=?",
        (param,), fetch="one")
    if ref and ref.get("bale_user_id") and ref["bale_user_id"] != uid:
        me = get_user(uid)
        if me and not me.get("referred_by"):
            db_execute("UPDATE users SET referred_by=? WHERE bale_user_id=?",
                       (ref["bale_user_id"], uid))
            log_action(uid, "referred_by", {"by": ref["bale_user_id"]})
            send(cid, (
                f"🎁 شما با دعوت "
                f"{ref.get('first_name') or 'یکی از اعضا'} وارد شدید!"
            ))
            # اطلاع به دعوت‌کننده
            n = db_scalar("SELECT COUNT(*) FROM users WHERE referred_by=?",
                          (ref["bale_user_id"],))
            nm = (me.get("first_name") or "کاربر جدید")
            send(ref["bale_user_id"], (
                f"🎉 یک نفر با لینک شما عضو شد!\n\n"
                f"👤 {nm}\n"
                f"📊 مجموع دعوت‌های شما: {n}"
            ))
        return show_main_menu(cid, user)

    # کد رویداد
    return ev_mod.register_by_code(cid, uid, param)


def verify_form_ticket(cid, uid, qr):
    """🎫 اعتبارسنجی بلیت فرم با کد QR (فقط ادمین)"""
    if not is_admin(uid):
        return send(cid, "❌ فقط ادمین می‌تواند بلیت را بررسی کند")

    qr = (qr or "").strip()
    r = db_execute("SELECT * FROM form_responses WHERE qr_code=?", (qr,), fetch="one")
    if not r:
        return send(cid, f"❌ بلیت نامعتبر\n\n📱 کد: {qr}")

    form = fb_mod.get_form(r["form_id"])
    u = get_user(r.get("bale_user_id")) or {}
    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "—"

    lines = ["🎫 بررسی بلیت", "━━━━━━━━━━━━━━", "",
             f"📋 فرم: {form['title'] if form else '—'}",
             f"👤 نام: {nm}",
             f"🔖 کد پیگیری: {r.get('tracking_code') or '—'}",
             f"📅 ثبت: {(r.get('completed_at') or '')[:19]}"]

    if r.get("status") == "confirmed":
        lines += ["", "⚠️ این بلیت قبلاً استفاده شده است!",
                  f"👨‍💼 توسط: {r.get('reviewed_by') or '—'}",
                  f"🕐 در: {r.get('reviewed_at') or '—'}"]
        return send(cid, "\n".join(lines))

    if r.get("status") != "completed":
        lines += ["", f"⚠️ وضعیت: {r.get('status')}"]
        return send(cid, "\n".join(lines))

    lines += ["", "✅ بلیت معتبر و استفاده‌نشده"]
    return send(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "✅ تأیید ورود", "callback_data": f"fbrok_{r['id']}"}],
        [{"text": "📄 مشاهده کامل", "callback_data": f"fbrv_{r['id']}"}]]})


def handle_contact(msg):
    user = msg.get("from", {})
    cid = msg["chat"]["id"]
    uid = user["id"]

    if get_state_name(uid) != "waiting_contact":
        return

    contact = msg.get("contact") or {}
    owner = contact.get("user_id")
    if owner and int(owner) != int(uid):
        return send(cid, "❌ فقط شماره خودتان را ارسال کنید!", kb_contact())

    mobile = normalize_mobile(contact.get("phone_number"))
    if not mobile:
        return send(cid, "❌ شماره نامعتبر است", kb_contact())

    complete_auth(cid, user, mobile, "phone_share")


def handle_phone_otp(msg):
    user = msg.get("from", {})
    cid = msg["chat"]["id"]
    uid = user["id"]
    text = (msg.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return handle_start(msg)

    mobile = normalize_mobile(text)
    if not mobile:
        return send(cid, "❌ شماره نامعتبر است\n\nمثال: 09121234567", kb_cancel())

    ok, wait = can_resend_otp(uid)
    if not ok:
        return send(cid, f"⏳ لطفاً {wait} ثانیه دیگر تلاش کنید", kb_cancel())

    _send_otp(cid, uid, mobile)


def _send_otp(cid, uid, mobile):
    code = generate_otp()
    save_otp(uid, mobile, code)
    res = send_otp_via_safir(mobile, code)

    if res.get("ok"):
        # 💬 فاز ۱۷-ج: متن از پنل ادمین قابل ویرایش است
        txt = get_setting("msg_otp_sent", "").strip() or (
            "✅ کد یکبار مصرف برایتان ارسال شد\n"
            "━━━━━━━━━━━━━━\n\n"
            "📱 شماره: {mobile}\n"
            "⏰ اعتبار: ۳ دقیقه\n\n"
            "🔢 لطفاً کد ۶ رقمی را وارد کنید:")
        txt = txt.replace("{mobile}", str(mobile))
        if res.get("test_mode"):
            txt += f"\n\n⚠️ حالت تست (سفیر تنظیم نشده)\nکد: {code}"
        else:
            hint = get_setting("msg_otp_hint", "").strip()
            txt += "\n\n" + (hint or
                              "💡 کد در «بات رمز یکبار مصرف» بله "
                              "برای شما ارسال شده است.")
        send(cid, txt, kb_otp())
        set_state(uid, "waiting_otp", {"mobile": mobile}, merge=False)
    else:
        err = res.get("error", "نامشخص")
        log(f"❌ OTP ناموفق برای {mobile}: {err}")
        # به سوپرادمین جزئیات خطا را بده
        if SUPER_ADMIN_ID:
            send(SUPER_ADMIN_ID, (
                f"⚠️ خطای ارسال OTP\n\n"
                f"📱 {mobile}\n"
                f"🤖 bot_id: {SAFIR_BOT_ID}\n"
                f"📄 {err}\n\n"
                f"💡 از ⚙️ تنظیمات → 📱 تنظیمات OTP بررسی کنید."
            ))
        send(cid, (
            "❌ ارسال کد ناموفق بود.\n\n"
            "💡 لطفاً با «اشتراک شماره تلفن» وارد شوید."
        ), kb_auth())
        clear_state(uid)


def handle_otp(msg):
    user = msg.get("from", {})
    cid = msg["chat"]["id"]
    uid = user["id"]
    text = (msg.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return handle_start(msg)

    if text == "🔄 ارسال مجدد کد":
        data = get_state_data(uid)
        mobile = data.get("mobile")
        if not mobile:
            clear_state(uid)
            return send(cid, "⏰ منقضی شد. دوباره /start بزنید")
        ok, wait = can_resend_otp(uid)
        if not ok:
            return send(cid, f"⏳ {wait} ثانیه دیگر می‌توانید کد جدید بگیرید")
        return _send_otp(cid, uid, mobile)

    code = normalize_digits(text)
    if not code.isdigit() or len(code) != 6:
        return send(cid, "❌ کد باید ۶ رقم باشد")

    res = verify_otp(uid, code)
    if not res["success"]:
        return send(cid, f"❌ {res['message']}")

    complete_auth(cid, user, res["phone"], "otp")


def complete_auth(cid, user, mobile, method):
    uid = user["id"]
    deep = (get_state_data(uid) or {}).get("deep")
    existing = get_user_by_mobile(mobile)

    if existing and not existing.get("bale_user_id"):
        link_bale(existing["id"], user)
        update_percent(uid)
        send(cid, (
            f"🎉 خوش برگشتید!\n\n"
            f"✅ حساب قبلی شما پیدا و متصل شد\n"
            f"📱 {mobile}"
        ), kb_remove())

    elif existing and existing.get("bale_user_id") == uid:
        create_auth_user(user, mobile, method)
        update_percent(uid)
        send(cid, f"✅ احراز هویت موفق!\n📱 {mobile}", kb_remove())

    elif existing and existing.get("bale_user_id") != uid:
        clear_state(uid)
        return send(cid, (
            "⚠️ این شماره قبلاً به حساب دیگری متصل شده است.\n\n"
            "💡 با پشتیبانی تماس بگیرید."
        ), kb_remove())

    else:
        create_auth_user(user, mobile, method)
        update_percent(uid)
        send(cid, f"🎉 ثبت‌نام شما انجام شد!\n📱 {mobile}", kb_remove())

    clear_state(uid)
    log_action(uid, "authenticated", {"method": method})
    time.sleep(0.5)

    if gate_force_join(cid, uid):
        return

    if deep:
        return handle_deep_link(cid, uid, deep, user)
    show_main_menu(cid, user, get_user(uid))


# ==================== CALLBACK ROUTER ====================
# 🛡️ فاز ۴۰ — پیشوندهایی که شناسهٔ عددی می‌خواهند
#
# از خودِ همین فایل استخراج می‌شود: هر جا `num("x_")` یا
# `two("x_")` نوشته شده یعنی دنبالهٔ آن باید عدد باشد.
# اگر عدد نبود، callback خراب است و باید محترمانه رد شود.
#
# 🔴 چرا لازم شد؟ اسکن نشان داد ۹۸ نقطهٔ یکتا با callback
#    دستکاری‌شده TypeError می‌دادند. حلقهٔ اصلی می‌گرفتش و
#    ربات نمی‌مرد، ولی کاربر پیام بی‌پاسخ می‌دید.
def _build_numeric_prefixes():
    import re as _re
    from pathlib import Path as _P
    try:
        src = _P(__file__).read_text(encoding="utf-8")
    except Exception:
        return frozenset()
    out = set(_re.findall(r'num\("([^"]+)"', src))
    out |= set(_re.findall(r'two\("([^"]+)"', src))
    return frozenset(x for x in out if x.endswith("_"))


def _build_two_prefixes():
    """
    پیشوندهایی که با two() خوانده می‌شوند.

    قالبشان «پیشوند_بخش‌اول_شناسه» است و **شناسهٔ آخر** باید
    عدد باشد (بخش اول می‌تواند متن باشد، مثل «evmm_onsite_5»).
    """
    import re as _re
    from pathlib import Path as _P
    try:
        src = _P(__file__).read_text(encoding="utf-8")
    except Exception:
        return frozenset()
    return frozenset(x for x in _re.findall(r'two\("([^"]+)"', src)
                     if x.endswith("_"))


def _build_num_only_prefixes():
    """
    پیشوندهایی که **فقط** با num() خوانده می‌شوند.

    ⚠️ آن‌هایی که two() هم دارند کنار گذاشته می‌شوند، چون
       بخش اولشان می‌تواند متن باشد (مثل «evmm_onsite»).
    """
    import re as _re
    from pathlib import Path as _P
    try:
        src = _P(__file__).read_text(encoding="utf-8")
    except Exception:
        return frozenset()
    nums = {x for x in _re.findall(r'num\("([^"]+)"', src)
            if x.endswith("_")}
    twos = {x for x in _re.findall(r'two\("([^"]+)"', src)
            if x.endswith("_")}
    # ⚠️ پیشوندهایی که **دستی** هم پارس می‌شوند کنار می‌روند.
    #    مثال: «fbsec_5_join_us» — با num("fbsec_") خوانده
    #    می‌شود ولی چند خط بالاتر با split دستی هم مدیریت
    #    می‌شود و شناسه‌اش وسط است، نه آخر.
    manual = set()
    for m in _re.finditer(r'data\[len\("([^"]+)"\):\]', src):
        if m.group(1).endswith("_"):
            manual.add(m.group(1))
    return frozenset(nums - twos - manual)


_NUMERIC_PREFIXES = _build_numeric_prefixes()
_NUM_ONLY_PREFIXES = _build_num_only_prefixes()
_TWO_PREFIXES = _build_two_prefixes()


def _show_shared_review_inbox(cid, uid, kind, *, legacy_action=False):
    """Show only server-backed review tasks; surface, but never mutate, legacy rows."""
    if legacy_action:
        send(
            cid,
            "این دکمه از مسیر قدیمی است؛ تصمیم در SQLite ثبت نمی‌شود و فقط کارتابل سرور معتبر است.",
            kb_remove(),
        )
    legacy_queries = {
        "profile_review": (
            "SELECT COUNT(*) FROM profile_submissions "
            "WHERE status='pending' AND COALESCE(shared_task_id,'')=''",
            "پروفایل",
        ),
        "receipt_review": (
            "SELECT COUNT(*) FROM payment_receipts "
            "WHERE status='pending' AND COALESCE(shared_task_id,'')=''",
            "فیش پرداخت",
        ),
    }
    query, label = legacy_queries[kind]
    try:
        legacy_count = int(db_scalar(query, default=0) or 0)
    except (TypeError, ValueError):
        legacy_count = 0
    notice = None
    if legacy_count:
        notice = (
            f"⚠️ {legacy_count} {label} قدیمی در SQLite ربات مانده و در کارتابل سرور نیست. "
            "این موارد از این مسیر تأیید یا رد نمی‌شوند؛ برای رسیدگی به آن‌ها انتقال کنترل‌شده لازم است."
        )
    unavailable_notice = None if legacy_action else (
        "کارتابل مشترک مرجع بررسی است؛ درخواست‌های قدیمی و رسیدهایی که آنجا نیستند "
        "از این مسیر تأیید یا رد نمی‌شوند و انتقالشان جداگانه انجام می‌شود."
    )
    return shared_workflows_mod.show_inbox(
        cid,
        uid,
        kind=kind,
        pre_list_notice=notice,
        unavailable_notice=unavailable_notice,
    )


def handle_callback(cb):
    user = cb.get("from", {})
    uid = user.get("id")
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    cid = (msg.get("chat") or {}).get("id") or uid

    answer_callback(cb.get("id"))
    log(f"🔘 {uid}: {data}")

    # ✅ ویرایش در جا: message_id همان پیامی که رویش کلیک شد
    _adm, _full = _menu_flags(uid)
    set_context(cid, msg.get("message_id"), from_callback=True,
                is_admin=_adm, is_full=_full)


    if uid != SUPER_ADMIN_ID and is_blocked(uid):
        return send(cid, get_setting("msg_blocked", "🚫 دسترسی شما مسدود شده است."))

    # 🛡️ فاز ۴۰ — نگهبان شناسه
    #
    # 🔴 باگ رفع‌شده: `num()` وقتی نمی‌توانست عدد بسازد `None`
    #    برمی‌گرداند و **بی‌صدا** ادامه می‌داد. تابع مقصد بعد
    #    `int(None)` یا `row["x"]` می‌کرد و TypeError می‌داد.
    #    اسکن نشان داد ۹۸ نقطهٔ یکتا این‌طور می‌شکنند.
    #
    #    حالا `_BAD` علامت می‌خورد و بلافاصله بعد از استخراج
    #    بررسی می‌شود — کاربر پیام روشن می‌گیرد به‌جای سکوت.
    _bad = {"hit": False}

    def num(prefix, default=None):
        try:
            return int(data[len(prefix):])
        except (ValueError, TypeError):
            if default is None:
                _bad["hit"] = True
            return default

    def two(prefix):
        """استخراج دو پارامتر از callback مثل fbpm_card_12"""
        rest = data[len(prefix):]
        i = rest.rfind("_")
        if i < 0:
            _bad["hit"] = True
            return rest, None
        try:
            return rest[:i], int(rest[i + 1:])
        except (ValueError, TypeError):
            _bad["hit"] = True
            return rest[:i], None

    def _bad_id():
        """🌱 پیام یکسان برای شناسهٔ نامعتبر"""
        return send(cid, "🌱 این دکمه دیگر معتبر نیست.\n\n"
                         "💡 از منوی اصلی دوباره شروع کنید.",
                    {"inline_keyboard": [
                        [{"text": "🏠 منوی اصلی",
                          "callback_data": "back_main"}]]})

    if data.startswith("bff"):
        return shared_form_flow_mod.handle_callback(cid, uid, data)

    # 🛡️ پیش‌بررسی: اگر callback شناسهٔ عددی می‌خواهد ولی
    #    چیز دیگری آمده، همین‌جا جلویش را می‌گیریم — قبل از
    #    اینکه به هر هندلری برسد.
    #
    #    الگو: پیشوندی که با «_» تمام می‌شود و بقیه‌اش باید
    #    عدد (یا عدد_عدد) باشد.
    # 🛡️ اگر پیشوند **دقیقاً** با num() خوانده می‌شود، دنباله‌اش
    #    باید عدد باشد.
    #
    #    ⚠️ فقط تطابق دقیق (نه startswith): بعضی callbackها
    #       عمداً متن دارند — مثل «evmm_onsite» که با two()
    #       خوانده می‌شود و بخش اولش نام روش پرداخت است.
    if "_" in data:
        _tail = data.rsplit("_", 1)[-1]
        _digit = _tail.lstrip("-").isdigit()
        _bad_now = False

        # 🛡️ الف) num(): همهٔ دنبالهٔ پیشوند باید عدد باشد
        #
        #     ⚠️ نمی‌شود فقط `data[:rfind]` را سنجید: در
        #        «ffy_1_abc» آن می‌شود «ffy_1_» که در فهرست
        #        نیست. باید بلندترین پیشوند منطبق را یافت و
        #        **کل دنباله** را سنجید.
        if not _digit:
            _np = ""
            for _p in _NUM_ONLY_PREFIXES:
                if data.startswith(_p) and len(_p) > len(_np):
                    _np = _p
            if _np and not data[len(_np):].lstrip("-").isdigit():
                _bad_now = True

        # 🛡️ ب) two(): قالب «پیشوند_بخش‌اول_شناسه»
        #     «ffo_2_5» درست  ·  «ffo_999999» ناقص (بخش دوم ندارد)
        #     «ffy_1_abc» شناسه‌اش عدد نیست
        #
        #     بلندترین پیشوند منطبق را می‌گیریم تا «cc_pw_» بر
        #     «cc_» ترجیح داشته باشد.
        #     ⚠️ بعضی two() ها عمداً بدون شناسه صدا زده می‌شوند
        #        («evmm_onsite» در جریان ساخت رویداد). پس فقط
        #        وقتی ایراد می‌گیریم که **شناسه‌ای هست ولی عدد
        #        نیست** — نه وقتی اصلاً شناسه‌ای نیامده.
        if not _bad_now:
            _hit = ""
            for _tp in _TWO_PREFIXES:
                if data.startswith(_tp) and len(_tp) > len(_hit):
                    _hit = _tp
            if _hit:
                _rest = data[len(_hit):]
                if "_" in _rest:
                    # قالب کامل: بخش دوم باید عدد باشد
                    if not _digit:
                        _bad_now = True
                elif _digit:
                    # ⚠️ «ffo_999999» — یک بخش عددی تنها.
                    #    two() این را (rest, None) می‌خواند و
                    #    تابع مقصد int(None) می‌کند.
                    #    ولی «evmm_onsite» (بخش متنی تنها)
                    #    عمدی است و باید رد شود.
                    _bad_now = True

        if _bad_now:
            log(f"⚠️ شناسهٔ نامعتبر در «{data[:40]}»")
            return _bad_id()

    # ---- احراز ----
    if data == "auth_phone":
        set_state(uid, "waiting_contact", {}, merge=True)
        return send(cid, "📱 اشتراک شماره تلفن\n━━━━━━━━━━━━━━\n\nروی دکمه پایین بزنید:",
                    kb_contact())

    if data == "auth_otp":
        set_state(uid, "waiting_phone_otp", {}, merge=True)
        return send(cid, (
            "🔢 تأیید دو مرحله‌ای\n━━━━━━━━━━━━━━\n\n"
            "شماره موبایل خود را بفرستید:\nمثال: 09121234567"
        ), kb_cancel())

    if data == "check_join":
        channels = get_active_channels()
        if not channels:
            return show_main_menu(cid, user)
        not_joined = check_user_joined(uid, channels)
        if not_joined:
            send(cid, f"❌ هنوز در {len(not_joined)} کانال/گروه عضو نشده‌اید")
            return show_force_join(cid, uid, not_joined)
        send(cid, "✅ عضویت شما تأیید شد!", kb_remove())
        time.sleep(0.4)
        return show_main_menu(cid, user)

    # ---- منو ----
    if data == "back_main":
        clear_state(uid)
        return show_main_menu(cid, user)
    if data == "coming_soon":
        return send(cid, "🔜 این بخش در فاز بعدی فعال می‌شود!")
    if data == "noop":
        return

    # ---- پروفایل ----
    if data == "profile_view":
        return profile_mod.show_profile(cid, uid)
    if data == "profile_fill":
        return profile_mod.start_form(cid, uid)
    if data == "form_go":
        return profile_mod.ask_step(cid, uid, 0)
    if data == "form_submit":
        return profile_mod.submit_profile(cid, uid)
    if data == "profile_photo":
        return profile_mod.ask_photo(cid, uid)
    if data == "profile_photo_del":
        return profile_mod.delete_photo(cid, uid)

    # ---- رویدادها: کاربر ----
    if data == "u_events":
        return ev_mod.show_user_events(cid, uid, 0)
    if data.startswith("uevpg_"):
        return ev_mod.show_user_events(cid, uid, num("uevpg_", 0))
    if data.startswith("uev_"):
        return ev_mod.show_event_user(cid, uid, num("uev_"))
    if data.startswith("ureg_"):
        return ev_mod.register(cid, uid, num("ureg_"))
    # ═══ 🧱 فاز ۲۴ — هزینه زیرساخت ═══
    if data == "pay_infra":
        return inf_mod.show_panel(cid, uid)
    if data == "inf_prev":
        return inf_mod.show_preview(cid, uid)
    if data.startswith("infb_"):
        return inf_mod.toggle(cid, uid, data[len("infb_"):])
    if data.startswith("infe_"):
        return inf_mod.start_edit(cid, uid, data[len("infe_"):])
    if data.startswith("ucancel_"):
        return ev_mod.cancel_registration(cid, uid, num("ucancel_"))
    # ═══ 💳 فاز ۲۴ — ثبت‌نام نیمه‌تمام قفل نشود ═══
    if data.startswith("urepay_"):
        return ev_mod.resume_payment(cid, uid, num("urepay_"))
    if data.startswith("uregnew_"):
        return ev_mod.restart_registration(cid, uid, num("uregnew_"))
    if data.startswith("uticket_"):
        return ev_mod.show_ticket(cid, uid, num("uticket_"))
    if data.startswith("upay_"):
        eid = num("upay_")
        ev = ev_mod.get_event(eid)
        reg = db_execute(
            "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
            (eid, uid), fetch="one")
        if ev and reg:
            u = get_user(uid)
            price = int(ev.get("price") or 0)
            if u and u.get("is_vip") and ev.get("price_vip"):
                price = int(ev["price_vip"])
            return ev_mod.start_payment(cid, uid, ev, reg["id"], price)
        return send(cid, "❌ اطلاعات ثبت‌نام یافت نشد")
    if data == "u_myevents":
        return ev_mod.show_my_events(cid, uid)
    if data == "u_my_tickets":
        return ev_mod.show_my_events(cid, uid)
    if data == "ev_bycode":
        set_state(uid, "ev_code", {}, merge=False)
        return send(cid, (
            "🔑 ورود با کد دعوت\n━━━━━━━━━━━━━━\n\nکد دعوت را بفرستید:"
        ), kb_cancel())

    # ---- بخش‌های کاربر ----
    # ═══ ℹ️ فاز ۱۸-ب — درباره ما و پشتیبانی ═══
    if data == "u_support":
        return ab_mod.show_hub(cid, uid)
    if data == "ab_about":
        return ab_mod.show_about(cid, uid)
    if data == "ab_support":
        return ab_mod.show_support(cid, uid)
    if data == "ab_team":
        return ab_mod.show_team(cid, uid)
    if data == "ab_social":
        return ab_mod.show_social(cid, uid)
    if data == "ab_join":
        return ab_mod.show_join(cid, uid)
    if data == "ab_contact":
        return ab_mod.show_contact(cid, uid)
    if data in ("ab_mission", "ab_achieve", "ab_rules", "ab_hours",
                "ab_guide", "ab_intro"):
        return ab_mod.show_text_block(cid, uid, data[3:])
    # ── پنل ادمین درباره ما ──
    if data == "ab_admin":
        return ab_mod.show_admin(cid, uid)
    if data == "ab_preview":
        return ab_mod.show_hub(cid, uid)
    if data.startswith("abt_"):
        return ab_mod.toggle_block(cid, uid, data[len("abt_"):])
    if data.startswith("abe_"):
        return ab_mod.start_edit_text(cid, uid, data[len("abe_"):])
    if data == "ab_links":
        return ab_mod.show_links_admin(cid, uid)
    if data == "ablnew":
        return ab_mod.start_add_link(cid, uid)
    if data.startswith("ablnew_"):
        return ab_mod.start_add_link(cid, uid, data[len("ablnew_"):])
    if data.startswith("ablt_"):
        return ab_mod.toggle_link(cid, uid, num("ablt_"))
    if data.startswith("abld_"):
        return ab_mod.delete_link(cid, uid, num("abld_"))
    if data == "ab_people":
        return ab_mod.show_people_admin(cid, uid)
    if data == "abpnew":
        return ab_mod.start_add_person(cid, uid)
    if data.startswith("abpt_"):
        return ab_mod.toggle_person(cid, uid, num("abpt_"))
    if data.startswith("abpd_"):
        return ab_mod.delete_person(cid, uid, num("abpd_"))
    if data == "ab_joinform":
        return ab_mod.show_join_forms(cid, uid)
    # ── 📊 فاز ۱۸-ج: آمار نمایشی ──
    if data == "ab_stats":
        return ab_mod.show_stats_admin(cid, uid)
    # ── 🎛️ فاز ۲۰: چیدمان و روشن/خاموش گروهی ──
    if data == "ab_layout":
        return ab_mod.show_layout(cid, uid)
    if data.startswith("ablay_"):
        return ab_mod.show_layout(cid, uid, data[len("ablay_"):])
    if data == "ab_bulk":
        return ab_mod.show_bulk(cid, uid)
    if data.startswith("abbulk_"):
        return ab_mod.show_bulk(cid, uid, data[len("abbulk_"):])
    if data.startswith("abst_"):
        return ab_mod.toggle_stat(cid, uid, data[len("abst_"):])
    # ── 🏷️ فاز ۱۸-ج: هویت ربات ──
    if data == "ab_identity":
        return ab_mod.show_identity(cid, uid)
    if data == "abid_toggle":
        return ab_mod.toggle_identity(cid, uid)
    if data == "abid_reset":
        return ab_mod.reset_identity(cid, uid)
    if data.startswith("abid_"):
        return ab_mod.start_identity_edit(cid, uid, data[len("abid_"):])
    if data == "u_faq":
        return set_mod.show_faq(cid, uid)
    if data == "u_referral":
        return set_mod.show_referral(cid, uid)
    if data == "u_points":
        return set_mod.show_points(cid, uid)
    if data == "u_notifications":
        return set_mod.show_notifications(cid, uid)
    if data == "u_contact":
        set_state(uid, "contact_admin", {}, merge=False)
        return send(cid, (
            "💬 ارسال پیام به ادمین\n━━━━━━━━━━━━━━\n\nپیام خود را بنویسید:"
        ), kb_cancel())

    # ---- ادمین: رویداد ----
    if data == "ev_new":
        return ev_mod.start_create(cid, uid)
    if data == "ev_go":
        return ev_mod.ask_create_step(cid, uid, 0)
    if data == "ev_back":
        return ev_mod.wizard_back(cid, uid)
    if data == "ev_cancel":
        return ev_mod.wizard_cancel(cid, uid)
    if data == "ev_list":
        return ev_mod.show_admin_events(cid, uid, 0)
    if data.startswith("evpg_"):
        return ev_mod.show_admin_events(cid, uid, num("evpg_", 0))
    if data.startswith("ev_view_"):
        return ev_mod.show_event_admin(cid, uid, num("ev_view_"))
    if data.startswith("evt_"):
        from auth import update_state_data
        update_state_data(uid, {"event_type": data[4:]})
        d = get_state_data(uid)
        return ev_mod.ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
    if data.startswith("evl_"):
        from auth import update_state_data
        update_state_data(uid, {"location_type": data[4:]})
        d = get_state_data(uid)
        return ev_mod.ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
    if data.startswith("evp_"):
        from auth import update_state_data
        update_state_data(uid, {"privacy": data[4:]})
        d = get_state_data(uid)
        return ev_mod.ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
    if data.startswith("evpay_"):
        from auth import update_state_data
        # 🛡️ فاز ۴۰: مقدار باید ۰ یا ۱ باشد
        _v = data[6:]
        if not _v.isdigit():
            return _bad_id()
        update_state_data(uid, {"is_paid": int(_v)})
        d = get_state_data(uid)
        return ev_mod.ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
    if data.startswith("evf_"):
        from auth import update_state_data
        key = data[4:]
        if key == "done":
            d = get_state_data(uid)
            return ev_mod.ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
        d = get_state_data(uid)
        update_state_data(uid, {key: 0 if int(d.get(key) or 0) else 1})
        return ev_mod.show_features(cid, uid)
    if data == "ev_save_draft":
        return ev_mod.save_event(cid, uid, publish=False)
    if data == "ev_save_publish":
        return ev_mod.save_event(cid, uid, publish=True)
    if data.startswith("ev_pub_"):
        return ev_mod.set_event_status(cid, uid, num("ev_pub_"), "published")
    if data.startswith("ev_close_"):
        return ev_mod.set_event_status(cid, uid, num("ev_close_"), "closed")
    if data.startswith("ev_finish_"):
        return ev_mod.set_event_status(cid, uid, num("ev_finish_"), "finished")
    if data.startswith("ev_delq_"):
        return ev_mod.delete_event(cid, uid, num("ev_delq_"), False)
    if data.startswith("ev_dely_"):
        return ev_mod.delete_event(cid, uid, num("ev_dely_"), True)
    if data.startswith("ev_notifygo_"):
        return ev_mod.do_notify_event(cid, uid, num("ev_notifygo_"))
    if data.startswith("ev_notify_"):
        return ev_mod.notify_event(cid, uid, num("ev_notify_"))
    if data.startswith("ev_regs_"):
        parts = data.replace("ev_regs_", "").split("_")
        try:
            return ev_mod.show_registrations(cid, uid, int(parts[0]),
                                             int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ev_report_"):
        return ev_mod.event_report(cid, uid, num("ev_report_"))
    if data.startswith("ev_export_"):
        return ev_mod.export_registrations(cid, uid, num("ev_export_"))
    if data.startswith("regok_"):
        return ev_mod.approve_registration(cid, uid, num("regok_"), True)
    if data.startswith("regno_"):
        return ev_mod.approve_registration(cid, uid, num("regno_"), False)


    # ---- ✋ حضور و غیاب: کاربر ----
    if data == "u_attendance":
        return att_mod.user_attendance_menu(cid, uid)
    if data.startswith("uatt_rep_"):
        return att_mod.user_report(cid, uid, num("uatt_rep_"))
    if data == "u_att_report":
        return att_mod.user_report(cid, uid)
    if data.startswith("uatts_"):
        return att_mod.ask_code(cid, uid, num("uatts_"))
    if data.startswith("uatt_"):
        return att_mod.user_attendance_menu(cid, uid, num("uatt_"))

    # ---- 🎓 گواهینامه: کاربر ----
    if data == "u_my_certs":
        return att_mod.my_certificates(cid, uid)
    if data.startswith("ucertv_"):
        return att_mod.view_certificate(cid, uid, num("ucertv_"))
    if data.startswith("ucert_"):
        return att_mod.issue_certificate(cid, uid, num("ucert_"))

    # ---- ✋ حضور و غیاب: ادمین ----
    # ═══ 🔍 فاز ۳۴ — استعلام گواهینامه ═══
    if data == "cv_ask":
        return cv_mod.show_ask(cid, uid)
    if data == "cv_bycode":
        return cv_mod.start_code(cid, uid)
    if data == "cv_bydoc":
        return cv_mod.start_doc(cid, uid)
    if data.startswith("cve_doc_"):
        return cv_mod.start_doc_edit(cid, uid, num("cve_doc_"))
    if data.startswith("cve_val_"):
        return cv_mod.show_validity(cid, uid, num("cve_val_"))
    if data.startswith("cve_st_"):
        return cv_mod.show_stats(cid, uid, num("cve_st_"))
    if data.startswith("cvv_"):
        _v, _e = two("cvv_")
        return cv_mod.show_validity(cid, uid, _e, _v)
    if data.startswith("cve_"):
        return cv_mod.show_event_cfg(cid, uid, num("cve_"))

    # ═══ 📊 فاز ۳۳ — نظرسنجی حرفه‌ای ═══
    if data.startswith("sv_rep_"):
        return sv_mod.show_report(cid, uid, num("sv_rep_"))
    if data.startswith("sv_txt_"):
        _e, _p = two("sv_txt_")
        return sv_mod.show_comments(cid, uid, _e, _p)
    if data.startswith("sv_send_"):
        return sv_mod.do_send(cid, uid, num("sv_send_"))
    if data.startswith("sv_rem_"):
        return sv_mod.do_remind(cid, uid, num("sv_rem_"))
    if data.startswith("sv_xl_"):
        return sv_mod.export(cid, uid, num("sv_xl_"))

    # ═══ 🌐 فاز ۳۳ — حضور و غیاب آنلاین ═══
    if data.startswith("ao_m_"):
        return aa_mod.show_methods(cid, uid, num("ao_m_"))
    if data.startswith("ao_rot_"):
        return aa_mod.show_rotating(cid, uid, num("ao_rot_"))
    if data.startswith("ao_send_"):
        return aa_mod.send_links(cid, uid, num("ao_send_"))
    if data.startswith("ao_rc_"):
        return aa_mod.do_rollcall(cid, uid, num("ao_rc_"))
    if data.startswith("ao_dwr_"):
        return aa_mod.show_dwell_report(cid, uid, num("ao_dwr_"))
    if data.startswith("ao_dw_"):
        return aa_mod.start_dwell(cid, uid, num("ao_dw_"))
    if data.startswith("ao_lnke_"):
        return aa_mod.start_link(cid, uid, num("ao_lnke_"))
    if data.startswith("ao_link_"):
        return aa_mod.show_session_link(cid, uid, num("ao_link_"))
    if data.startswith("aom_"):
        _m, _s = two("aom_")
        return aa_mod.set_method(cid, uid, _m, _s)
    if data.startswith("aoj_"):
        return aa_mod.user_join(cid, uid, num("aoj_"))
    if data.startswith("aol_"):
        return aa_mod.user_leave(cid, uid, num("aol_"))
    if data.startswith("arc_"):
        return aa_mod.user_answer_rollcall(cid, uid, num("arc_"))
    if data.startswith("ao_"):
        return aa_mod.show_online(cid, uid, num("ao_"))

    if data.startswith("att_list_"):
        return att_mod.show_sessions(cid, uid, num("att_list_"))
    if data.startswith("att_new_"):
        return att_mod.new_session(cid, uid, num("att_new_"))
    if data.startswith("att_view_"):
        return att_mod.show_session(cid, uid, num("att_view_"))
    if data.startswith("att_toggle_"):
        return att_mod.toggle_session(cid, uid, num("att_toggle_"))
    if data.startswith("att_newcode_"):
        return att_mod.new_code(cid, uid, num("att_newcode_"))
    if data.startswith("att_announce_"):
        return att_mod.announce_code(cid, uid, num("att_announce_"))
    if data.startswith("att_dely_"):
        return att_mod.delete_session(cid, uid, num("att_dely_"), True)
    if data.startswith("att_del_"):
        return att_mod.delete_session(cid, uid, num("att_del_"), False)
    if data.startswith("att_report_"):
        return att_mod.event_attendance_report(cid, uid, num("att_report_"))
    if data.startswith("att_export_"):
        return att_mod.export_attendance(cid, uid, num("att_export_"))
    if data.startswith("att_who_"):
        parts = data.replace("att_who_", "").split("_")
        try:
            return att_mod.show_who(cid, uid, int(parts[0]),
                                    int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("att_manual_"):
        parts = data.replace("att_manual_", "").split("_")
        try:
            return att_mod.manual_list(cid, uid, int(parts[0]),
                                       int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("attm_"):
        parts = data.replace("attm_", "").split("_")
        try:
            return att_mod.toggle_manual(cid, uid, int(parts[0]), int(parts[1]),
                                         int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return
    # ═══ ✋ فاز ۲۲ — حضور و غیاب کامل ═══
    if data.startswith("att_abs_"):
        parts = data.replace("att_abs_", "").split("_")
        try:
            return att_mod.show_absent(cid, uid, int(parts[0]),
                                       int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("att_remind_"):
        return att_mod.remind_absent(cid, uid, num("att_remind_"))
    if data.startswith("att_meth_"):
        return att_mod.show_methods(cid, uid, num("att_meth_"))
    if data.startswith("att_setm_"):
        parts = data.replace("att_setm_", "").split("_", 1)
        try:
            return att_mod.set_method(cid, uid, int(parts[0]), parts[1])
        except (ValueError, IndexError):
            return
    if data.startswith("att_set_"):
        return att_mod.show_session_settings(cid, uid, num("att_set_"))
    if data.startswith("att_fld_"):
        parts = data.replace("att_fld_", "").split("_", 1)
        try:
            return att_mod.start_field(cid, uid, int(parts[0]), parts[1])
        except (ValueError, IndexError):
            return
    if data.startswith("att_loc_"):
        return att_mod.start_session_location(cid, uid, num("att_loc_"))
    if data.startswith("att_ally_"):
        return att_mod.mark_all(cid, uid, num("att_ally_"), True)
    if data.startswith("att_all_"):
        return att_mod.mark_all(cid, uid, num("att_all_"), False)
    if data.startswith("att_clry_"):
        return att_mod.clear_all(cid, uid, num("att_clry_"), True)
    if data.startswith("att_clr_"):
        return att_mod.clear_all(cid, uid, num("att_clr_"), False)
    if data.startswith("attst_"):
        parts = data.replace("attst_", "").split("_")
        try:
            return att_mod.show_status_picker(
                cid, uid, int(parts[0]), int(parts[1]),
                int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("attsv_"):
        parts = data.replace("attsv_", "").split("_")
        try:
            return att_mod.set_status(
                cid, uid, int(parts[0]), int(parts[1]), parts[2],
                int(parts[3]) if len(parts) > 3 else 0)
        except (ValueError, IndexError):
            return

    # ═══ 🎓 فاز ۲۲ — مرکز صدور گواهینامه رویداد ═══
    if data.startswith("ci_tpl_"):
        return ci_mod.show_templates(cid, uid, num("ci_tpl_"))
    if data.startswith("ci_setpl_"):
        parts = data.replace("ci_setpl_", "").split("_")
        try:
            return ci_mod.set_template(cid, uid, int(parts[0]),
                                       int(parts[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("ci_cond_"):
        return ci_mod.show_conditions(cid, uid, num("ci_cond_"))
    if data.startswith("ci_exc_"):
        return ci_mod.toggle_excused(cid, uid, num("ci_exc_"))
    if data.startswith("ci_setc_"):
        parts = data.replace("ci_setc_", "").split("_", 1)
        try:
            return ci_mod.set_condition(cid, uid, int(parts[0]), parts[1])
        except (ValueError, IndexError):
            return
    if data.startswith("ci_par_"):
        return ci_mod.show_params(cid, uid, num("ci_par_"))
    if data.startswith("ci_pset_"):
        parts = data.replace("ci_pset_", "").split("_", 1)
        try:
            return ci_mod.start_param(cid, uid, int(parts[0]), parts[1])
        except (ValueError, IndexError):
            return
    if data.startswith("ci_pclr_"):
        return ci_mod.clear_params(cid, uid, num("ci_pclr_"))
    if data.startswith("ci_prev_"):
        return ci_mod.preview(cid, uid, num("ci_prev_"))
    if data.startswith("ci_pick_"):
        parts = data.replace("ci_pick_", "").split("_")
        try:
            return ci_mod.show_pick(cid, uid, int(parts[0]),
                                    int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_tog_"):
        parts = data.replace("ci_tog_", "").split("_")
        try:
            return ci_mod.toggle_pick(cid, uid, int(parts[0]), int(parts[1]),
                                      int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_ok_"):
        parts = data.replace("ci_ok_", "").split("_")
        try:
            return ci_mod.show_list(cid, uid, int(parts[0]), "ok",
                                    int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_no_"):
        parts = data.replace("ci_no_", "").split("_")
        try:
            return ci_mod.show_list(cid, uid, int(parts[0]), "no",
                                    int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_one_"):
        parts = data.replace("ci_one_", "").split("_")
        try:
            return ci_mod.show_one(cid, uid, int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("ci_mk_"):
        parts = data.replace("ci_mk_", "").split("_")
        try:
            return ci_mod.issue_single(cid, uid, int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("ci_regen_"):
        parts = data.replace("ci_regen_", "").split("_")
        try:
            return ci_mod.issue_single(cid, uid, int(parts[0]),
                                       int(parts[1]), force=True)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_resend_"):
        parts = data.replace("ci_resend_", "").split("_")
        try:
            return ci_mod.resend(cid, uid, int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("ci_unrev_"):
        parts = data.replace("ci_unrev_", "").split("_")
        try:
            return ci_mod.revoke(cid, uid, int(parts[0]), int(parts[1]),
                                 undo=True)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_rev_"):
        parts = data.replace("ci_rev_", "").split("_")
        try:
            return ci_mod.revoke(cid, uid, int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("ci_run_"):
        return ci_mod.confirm_run(cid, uid, num("ci_run_"))
    if data.startswith("ci_go_"):
        return ci_mod.run_bulk(cid, uid, num("ci_go_"))
    if data.startswith("ci_regall_"):
        return ci_mod.run_bulk(cid, uid, num("ci_regall_"), regen=True)
    if data.startswith("ci_resall_"):
        return ci_mod.resend_all(cid, uid, num("ci_resall_"))
    if data.startswith("ci_done_"):
        parts = data.replace("ci_done_", "").split("_")
        try:
            return ci_mod.show_issued(cid, uid, int(parts[0]),
                                      int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return
    if data.startswith("ci_stat_"):
        return ci_mod.show_stats(cid, uid, num("ci_stat_"))

    # ---- 🎓 گواهینامه: ادمین ----
    if data == "cert_settings":
        return att_mod.show_cert_settings(cid, uid)
    # ═══ 🎓 فاز ۱۹ — قالب گواهینامه از فایل ورد ═══
    if data == "ct_panel":
        return cg_mod.show_panel(cid, uid)
    if data == "ct_help":
        return cg_mod.show_help(cid, uid)
    if data == "ct_install":
        return cg_mod.show_install(cid, uid)
    if data == "ct_recheck":
        return cg_mod.show_install(cid, uid, force=True)
    if data == "ct_engine":
        return cg_mod.show_engine(cid, uid)
    if data == "ct_engtest":
        return cg_mod.engine_test(cid, uid)
    if data == "ct_new_docx":
        return cg_mod.start_upload(cid, uid, "docx")
    if data == "ct_new_img":
        return cg_mod.start_upload(cid, uid, "image")
    if data.startswith("ctv_"):
        return cg_mod.show_template(cid, uid, num("ctv_"))
    if data.startswith("ctprev_"):
        return cg_mod.preview(cid, uid, num("ctprev_"))
    # ═══ 🎫 فاز ۲۶ — بلیط فرم ═══
    if data == "tk_panel":
        return ftk_mod.show_panel(cid, uid)
    if data == "tk_blocks":
        return ftk_mod.show_blocks(cid, uid)
    if data == "tk_style":
        return ftk_mod.show_style(cid, uid)
    if data == "tk_size":
        return ftk_mod.show_size(cid, uid)
    if data == "tk_assets":
        return ftk_mod.show_assets(cid, uid)
    if data == "tk_more":
        return ftk_mod.show_more(cid, uid)
    if data == "tk_text":
        return ftk_mod.show_text(cid, uid)
    if data == "tk_ns":
        return ftk_mod.show_pick(cid, uid, "namestyle")
    if data == "tk_eng":
        return ftk_mod.show_engine(cid, uid)
    if data == "tk_fatest":
        return ftk_mod.fa_test(cid, uid)
    if data.startswith("tkeng_"):
        return ftk_mod.set_engine(cid, uid, data[len("tkeng_"):])
    if data == "tk_prev":
        return ftk_mod.preview(cid, uid)
    if data == "tk_reset":
        return ftk_mod.do_reset(cid, uid)
    if data == "tk_clean":
        return ftk_mod.clean_now(cid, uid)
    if data == "tk_logopos":
        return ftk_mod.show_pick(cid, uid, "logopos")
    if data == "tk_bgmode":
        return ftk_mod.show_pick(cid, uid, "bgmode")
    if data == "tk_align":
        return ftk_mod.show_pick(cid, uid, "align")
    if data.startswith("tkbt_"):
        return ftk_mod.do_toggle_block(cid, uid, data[len("tkbt_"):])
    if data.startswith("tkbe_"):
        return ftk_mod.show_block_edit(cid, uid, data[len("tkbe_"):])
    if data.startswith("tkup_"):
        return ftk_mod.do_move(cid, uid, data[len("tkup_"):], -1)
    if data.startswith("tkdn_"):
        return ftk_mod.do_move(cid, uid, data[len("tkdn_"):], 1)
    if data.startswith("tksz_"):
        _p = data[len("tksz_"):].rsplit("_", 1)
        try:
            return ftk_mod.do_size_step(cid, uid, _p[0], int(_p[1]))
        except (ValueError, IndexError):
            return
    if data.startswith("tklb_"):
        return ftk_mod.start_label(cid, uid, data[len("tklb_"):])
    if data.startswith("tkpal_"):
        return ftk_mod.set_pick(cid, uid, "pal", data[len("tkpal_"):])
    if data.startswith("tksize_"):
        return ftk_mod.set_pick(cid, uid, "size", data[len("tksize_"):])
    if data.startswith("tklp_"):
        return ftk_mod.set_pick(cid, uid, "lp", data[len("tklp_"):])
    if data.startswith("tkbg_"):
        return ftk_mod.set_pick(cid, uid, "bg", data[len("tkbg_"):])
    if data.startswith("tkal_"):
        return ftk_mod.set_pick(cid, uid, "al", data[len("tkal_"):])
    if data.startswith("tkns_"):
        return ftk_mod.set_pick(cid, uid, "ns", data[len("tkns_"):])
    if data.startswith("tka_"):
        return ftk_mod.start_asset(cid, uid, data[len("tka_"):])
    if data.startswith("tkd_"):
        return ftk_mod.remove_asset(cid, uid, data[len("tkd_"):])
    if data.startswith("tkb_"):
        return ftk_mod.toggle_setting(cid, uid, data[len("tkb_"):])
    if data.startswith("tke_"):
        return ftk_mod.start_edit(cid, uid, data[len("tke_"):])

    # ═══ 🩺 فاز ۲۵ — عیب‌یابی قالب ═══
    if data.startswith("ctdiag_"):
        return cg_mod.show_diagnose(cid, uid, num("ctdiag_"))
    if data.startswith("cttest_"):
        return cg_mod.test_build(cid, uid, num("cttest_"))
    if data.startswith("ctget_"):
        return cg_mod.send_template_file(cid, uid, num("ctget_"))
    if data.startswith("ctdef_"):
        return cg_mod.set_default(cid, uid, num("ctdef_"))
    if data.startswith("ctdel_"):
        return cg_mod.delete_template(cid, uid, num("ctdel_"))
    if data.startswith("ctbox_"):
        return cg_mod.start_box(cid, uid, num("ctbox_"))
    # ── ⚙️ فاز ۱۹-ب: تنظیمات جامع گواهینامه و بلیط ──
    # ═══ 🎓 فاز ۳۲ — چند گواهینامه برای رویداد ═══
    if data.startswith("evc_p_"):
        return evc_mod.show_panel(cid, uid, num("evc_p_"))
    if data.startswith("evc_add_"):
        return evc_mod.start_add(cid, uid, num("evc_add_"))
    if data.startswith("evc_v_"):
        return evc_mod.show_cert(cid, uid, num("evc_v_"))
    if data.startswith("evc_cond_"):
        return evc_mod.show_cond(cid, uid, num("evc_cond_"))
    if data.startswith("evc_tpl_"):
        return evc_mod.show_tpl_picker(cid, uid, num("evc_tpl_"))
    if data.startswith("evc_del_"):
        return evc_mod.confirm_delete(cid, uid, num("evc_del_"))
    if data.startswith("evc_prev_"):
        return evc_mod.show_ad_preview(cid, uid, num("evc_prev_"))
    if data.startswith("evcD_"):
        return evc_mod.do_delete(cid, uid, num("evcD_"))
    if data.startswith("evce_"):
        _f, _r = two("evce_")
        return evc_mod.start_edit(cid, uid, _f, _r)
    if data.startswith("evct_"):
        _w, _r = two("evct_")
        return evc_mod.toggle(cid, uid, _w, _r)
    if data.startswith("evcm_"):
        _d, _r = two("evcm_")
        return evc_mod.do_move(cid, uid, _d, _r)
    if data.startswith("evcc_"):
        _c, _r = two("evcc_")
        return evc_mod.set_cond(cid, uid, _c, _r)
    if data.startswith("evcn_"):
        _k, _r = two("evcn_")
        return evc_mod.start_min(cid, uid, _k, _r)
    if data.startswith("evc_get_"):
        return evc_mod.user_get(cid, uid, num("evc_get_"))
    if data.startswith("evc_iss_"):
        _e, _r = two("evc_iss_")
        return evc_mod.user_issue(cid, uid, _e, _r)
    if data.startswith("evcT_"):
        _t, _r = two("evcT_")
        return evc_mod.set_tpl(cid, uid, _t, _r)

    # ═══ 🏛️ فاز ۳۶ — مرکز صدور گواهینامه ═══
    #
    # 🎯 «یه مرکز صدور گواهینامه تو قسمت کاربران اضافه کن»
    #    «اگه اون پنل که گفتم بسازی میتونی کلا قسمت صدور
    #     گروهی با اکسل پاک کنی»
    #
    #    صدور گروهی قدیمی (cb_*) جایش را به مرکز صدور داد.
    #    ورودی اکسل حالا یکی از چهار راهِ انتخاب گیرنده است،
    #    نه یک بخش جدا.
    if data in ("cc_home", "cb_home"):
        return cc_mod.show_home(cid, uid)
    if data == "cc_new":
        return cc_mod.start_new(cid, uid)
    if data.startswith("cc_list_"):
        return cc_mod.show_list(cid, uid, data[len("cc_list_"):])
    if data.startswith("cc_pg_"):
        _rest = data[len("cc_pg_"):]
        _st, _, _pg = _rest.rpartition("_")
        # 🛡️ فاز ۴۰: صفحه ممکن است عدد نباشد
        return cc_mod.show_list(cid, uid, _st,
                                int(_pg) if _pg.isdigit() else 0)
    if data.startswith("cc_v_"):
        return cc_mod.show_issue(cid, uid, num("cc_v_"))
    if data.startswith("cc_tpl_"):
        return cc_mod.show_tpl_pick(cid, uid, num("cc_tpl_"))
    if data.startswith("cc_settpl_"):
        _i, _t = two("cc_settpl_")
        return cc_mod.set_template(cid, uid, _i, _t)
    if data.startswith("cc_wiz_"):
        return cc_mod.wizard_start(cid, uid, num("cc_wiz_"))
    if data.startswith("cc_ph_"):
        return cc_mod.show_params(cid, uid, num("cc_ph_"))
    if data.startswith("cc_pe_"):
        _rest = data[len("cc_pe_"):]
        _i, _, _k = _rest.partition("_")
        return cc_mod.start_param(cid, uid, _i, _k)
    if data.startswith("cc_aud_"):
        return cc_mod.show_audience(cid, uid, num("cc_aud_"))
    if data.startswith("cc_ev_"):
        return cc_mod.from_event(cid, uid, num("cc_ev_"))
    if data.startswith("cc_ae_"):
        return cc_mod.pick_event(cid, uid, num("cc_ae_"))
    if data.startswith("cc_aep_"):
        _i, _p = two("cc_aep_")
        return cc_mod.pick_event(cid, uid, _i, _p)
    if data.startswith("cc_as_"):
        return cc_mod.pick_segment(cid, uid, num("cc_as_"))
    if data.startswith("cc_amn_"):
        return cc_mod.ask_manual(cid, uid, num("cc_amn_"))
    if data.startswith("cc_asr_"):
        return cc_mod.ask_search(cid, uid, num("cc_asr_"))
    if data.startswith("cc_addu_"):
        _i, _u = two("cc_addu_")
        return cc_mod.add_one_user(cid, uid, _i, _u)
    if data.startswith("cc_xs_"):
        return cc_mod.send_sample_excel(cid, uid, num("cc_xs_"))
    if data.startswith("cc_ax_"):
        return cc_mod.ask_excel(cid, uid, num("cc_ax_"))
    if data.startswith("cc_sete_"):
        _i, _e = two("cc_sete_")
        return cc_mod.set_event(cid, uid, _i, _e)
    if data.startswith("cc_sets_"):
        _rest = data[len("cc_sets_"):]
        _i, _, _sg = _rest.partition("_")
        return cc_mod.set_segment(cid, uid, _i, _sg)
    if data.startswith("cc_aclr_"):
        return cc_mod.clear_audience(cid, uid, num("cc_aclr_"))
    if data.startswith("cc_alist_"):
        _i, _p = two("cc_alist_")
        return cc_mod.show_share_list(cid, uid, _i, _p)
    if data.startswith("cc_prev_"):
        return cc_mod.show_preview(cid, uid, num("cc_prev_"))
    if data.startswith("cc_pw_"):
        # 🛡️ فاز ۴۰: قالب «cc_pw_<شناسه>_<روش>» — اگر بخش دوم
        #    نبود، split با ValueError می‌مرد.
        _rest = data[len("cc_pw_"):]
        if "_" not in _rest:
            return _bad_id()
        _i, _w = _rest.split("_", 1)
        return cc_mod.publish_way(cid, uid, _i, _w)
    if data.startswith("cc_pub_"):
        return cc_mod.show_publish(cid, uid, num("cc_pub_"))
    if data.startswith("cc_pubc_"):
        return cc_mod.confirm_publish(cid, uid, num("cc_pubc_"))
    if data.startswith("cc_pubY_"):
        return cc_mod.do_publish(cid, uid, num("cc_pubY_"))
    if data.startswith("cc_renot_"):
        return cc_mod.renotify(cid, uid, num("cc_renot_"))
    if data.startswith("cc_rep_"):
        return cc_mod.show_report(cid, uid, num("cc_rep_"))
    if data.startswith("cc_link_"):
        return cc_mod.show_link(cid, uid, num("cc_link_"))
    if data.startswith("cc_msgt_"):
        return cc_mod.start_msg(cid, uid, num("cc_msgt_"), "t")
    if data.startswith("cc_msgb_"):
        return cc_mod.start_msg(cid, uid, num("cc_msgb_"), "b")
    if data.startswith("cc_msg_"):
        return cc_mod.show_msg(cid, uid, num("cc_msg_"))
    if data.startswith("cc_doc_"):
        return cc_mod.start_docno(cid, uid, num("cc_doc_"))
    if data.startswith("cc_photo_"):
        return cc_mod.toggle_photo(cid, uid, num("cc_photo_"))
    if data.startswith("cc_why_"):
        return cc_mod.why_blocked(cid, uid, num("cc_why_"))
    if data.startswith("cc_ren_"):
        return cc_mod.start_rename(cid, uid, num("cc_ren_"))
    if data.startswith("cc_delY_"):
        return cc_mod.do_delete(cid, uid, num("cc_delY_"))
    if data.startswith("cc_del_"):
        return cc_mod.confirm_delete(cid, uid, num("cc_del_"))
    if data == "cc_set":
        return cc_mod.show_settings(cid, uid)
    if data.startswith("ccsb_"):
        return cc_mod.toggle_setting(cid, uid, data[len("ccsb_"):])
    if data.startswith("ccse_"):
        return cc_mod.start_setting(cid, uid, data[len("ccse_"):])
    if data == "cc_photo":
        return cc_mod.show_photo_panel(cid, uid)
    if data.startswith("ccpb_"):
        return cc_mod.toggle_photo_setting(cid, uid, data[len("ccpb_"):])
    if data.startswith("ccpe_"):
        return cc_mod.start_photo_setting(cid, uid, data[len("ccpe_"):])
    if data == "cc_silh":
        return cc_mod.show_silhouette(cid, uid)
    if data == "cc_stats":
        return cc_mod.show_stats(cid, uid)
    # 👤 کاربر: دریافت گواهینامه
    if data.startswith("ccget_"):
        return cc_mod.user_get(cid, uid, num("ccget_"))
    if data == "cb_new":
        return cb_mod.start_new(cid, uid)
    if data == "cb_sample":
        return cb_mod.send_sample(cid, uid)
    if data.startswith("cb_rows_"):
        _b, _pg = two("cb_rows_")
        return cb_mod.show_rows(cid, uid, _b, _pg)
    if data.startswith("cb_v_"):
        return cb_mod.show_batch(cid, uid, num("cb_v_"))
    if data.startswith("cb_link_"):
        return cb_mod.send_link(cid, uid, num("cb_link_"))
    if data.startswith("cb_by_"):
        return cb_mod.show_match(cid, uid, num("cb_by_"))
    if data.startswith("cb_tpl_"):
        return cb_mod.show_tpl(cid, uid, num("cb_tpl_"))
    if data.startswith("cb_tog_"):
        return cb_mod.toggle_active(cid, uid, num("cb_tog_"))
    if data.startswith("cb_exp_"):
        return cb_mod.export_status(cid, uid, num("cb_exp_"))
    if data.startswith("cb_del_"):
        return cb_mod.confirm_delete(cid, uid, num("cb_del_"))
    if data.startswith("cbD_"):
        return cb_mod.do_delete(cid, uid, num("cbD_"))
    if data.startswith("cbe_"):
        _f, _b = two("cbe_")
        return cb_mod.start_edit(cid, uid, _f, _b)
    if data.startswith("cbB_"):
        _by, _b = two("cbB_")
        return cb_mod.set_match(cid, uid, _by, _b)
    if data.startswith("cbT_"):
        _t, _b = two("cbT_")
        return cb_mod.set_tpl(cid, uid, _t, _b)

    if data == "ct_hub":
        return cg_mod.show_hub(cid, uid)
    if data == "ct_stats":
        return cg_mod.show_stats_page(cid, uid)
    if data == "ct_set_cert":
        return cg_mod.show_settings(cid, uid, "cert")
    if data == "ct_set_ticket":
        return cg_mod.show_settings(cid, uid, "ticket")
    if data.startswith("ctsb_"):
        return cg_mod.toggle_setting(cid, uid, data[len("ctsb_"):])
    if data.startswith("ctse_"):
        return cg_mod.start_setting(cid, uid, data[len("ctse_"):])
    if data == "ct_clean":
        return cg_mod.clean_now(cid, uid)
    # ── 🖼️ تصاویر گواهینامه ──
    if data == "ct_assets":
        return cg_mod.show_assets(cid, uid)
    if data.startswith("ctas_"):
        return cg_mod.start_asset(cid, uid, data[len("ctas_"):])
    if data.startswith("ctad_"):
        return cg_mod.remove_asset(cid, uid, data[len("ctad_"):])
    if data == "ct_sizes":
        return cg_mod.show_sizes(cid, uid)
    if data.startswith("ctmm_"):
        return cg_mod.start_size(cid, uid, data[len("ctmm_"):])
    if data == "cert_edit":
        return att_mod.start_cert_edit(cid, uid)
    if data == "cert_reset":
        return att_mod.reset_cert(cid, uid)
    if data == "cert_preview":
        return att_mod.preview_cert(cid, uid)
    if data.startswith("cert_bulky_"):
        return att_mod.bulk_certificates(cid, uid, num("cert_bulky_"), True)
    if data.startswith("cert_bulk_"):
        return att_mod.bulk_certificates(cid, uid, num("cert_bulk_"), False)

    # ---- 👥 دعوت دوستان ----
    if data == "u_ref_share":
        return set_mod.share_referral(cid, uid)
    if data == "u_ref_list":
        return set_mod.show_referral_list(cid, uid)

    # ---- 📢 اطلاع‌رسانی: فیلترها ----
    if data.startswith("bcf_"):
        return admin_mod.choose_filter(cid, uid, data[4:])
    if data.startswith("bce_"):
        return admin_mod.choose_filter_event(cid, uid, num("bce_"))
    if data == "bc_edit":
        return admin_mod.edit_broadcast(cid, uid)


    # ---- 👥 مدیریت کاربران (طبق معماری) ----
    if data == "admin_users":
        return admin_mod.show_users_menu(cid, uid)
    if data == "um_list":
        return admin_mod.show_user_list(cid, uid, 0)
    if data == "um_add":
        return admin_mod.start_add_user(cid, uid)
    if data == "um_tags":
        return admin_mod.show_tags(cid, uid)
    if data == "um_vip":
        return admin_mod.show_vip(cid, uid)
    if data == "um_admins":
        return admin_mod.show_admins(cid, uid)
    if data == "um_adminlog":
        return admin_mod.show_admin_log(cid, uid)
    if data == "um_blocked":
        return admin_mod.show_blocked(cid, uid)
    if data == "um_report":
        return admin_mod.show_users_report(cid, uid)

    # ---- 💳 پرداخت ----
    if data == "set_payment":
        return pay_mod.show_payment_settings(cid, uid)

    # ═══ 🆕 فاز ۱۳: روش‌های پرداخت پیشرفته ═══
    if data == "pay_adv":
        return pay_mod.show_advanced_payment(cid, uid)
    if data == "payp_toggle":
        return pay_mod.toggle_points_payment(cid, uid)
    if data == "paydm":
        return pay_mod.show_default_methods(cid, uid)
    if data.startswith("paydm_"):
        return pay_mod.toggle_default_method(cid, uid, data[6:])
    if data.startswith("payn_"):
        return pay_mod.start_pay_num(cid, uid, data[5:])
    # ═══ 💳 فاز ۱۶ — کارمزد درگاه ═══
    if data == "pay_fee":
        return pay_mod.show_fee_settings(cid, uid)
    if data.startswith("payfm_"):
        return pay_mod.show_fee_method(cid, uid, data[6:])
    if data.startswith("payft_"):
        return pay_mod.toggle_fee(cid, uid, data[6:])
    if data.startswith("payfe_"):
        _pt, _m = data[6:].split("_", 1) if "_" in data[6:] else (data[6:], "")
        return pay_mod.start_fee_edit(cid, uid, _pt, _m)

    # ═══ 💠 فاز ۱۸-الف — پرداخت مرحله‌ای (اقساط/جلسه‌ای) ═══
    if data == "pp_panel":
        return pp_mod.show_panel(cid, uid)
    if data == "pp_plans":
        return pp_mod.show_plans(cid, uid)
    if data == "pp_new":
        return pp_mod.start_new(cid, uid)
    if data == "pp_open":
        return pp_mod.show_open(cid, uid)
    if data == "pp_mine":
        return pp_mod.show_my_installments(cid, uid)
    if data.startswith("ppay_"):
        return pp_mod.pay_one(cid, uid, num("ppay_"))
    if data.startswith("ppok_"):
        return pp_mod.admin_mark_paid(cid, uid, num("ppok_"))
    if data.startswith("ppv_"):
        return pp_mod.show_plan(cid, uid, num("ppv_"))
    if data.startswith("pptog_"):
        return pp_mod.toggle_plan(cid, uid, num("pptog_"))
    if data.startswith("ppdel_"):
        return pp_mod.delete_plan(cid, uid, num("ppdel_"))
    if data.startswith("ppe_"):
        k_, p_id = two("ppe_")
        return pp_mod.start_edit(cid, uid, k_, p_id)
    if data.startswith("ppm_"):
        rest_ = data[len("ppm_"):]
        if "_" in rest_:
            a, b = rest_.split("_", 1)
            try:
                return pp_mod.pick_mode(cid, uid, int(a), b)
            except (ValueError, TypeError):
                pass
        return pp_mod.pick_mode(cid, uid, num("ppm_"))
    if data.startswith("ppset_iv_"):
        return pp_mod.pick_default_interval(cid, uid, data[len("ppset_iv_"):])
    if data == "ppset_interval":
        return pp_mod.pick_default_interval(cid, uid)
    if data == "ppset_parts":
        return pp_mod.start_num_setting(cid, uid, "parts")
    if data == "ppset_prepay":
        return pp_mod.start_num_setting(cid, uid, "prepay")
    if data.startswith("ppiv_"):
        rest_ = data[len("ppiv_"):]
        if "_" in rest_:
            a, b = rest_.split("_", 1)
            try:
                return pp_mod.pick_interval(cid, uid, int(a), b)
            except (ValueError, TypeError):
                pass
        return pp_mod.pick_interval(cid, uid, num("ppiv_"))

    # ═══ 🔗 فاز ۱۷ — پرداخت غیرمتمرکز ═══
    if data == "pl_panel":
        return pl_mod.show_panel(cid, uid, 0)
    if data.startswith("pl_pg_"):
        return pl_mod.show_panel(cid, uid, num("pl_pg_", 0))
    if data == "pl_new":
        return pl_mod.start_new(cid, uid)
    if data == "pl_rep":
        return pl_mod.show_payments(cid, uid)
    if data == "pl_exp":
        return pl_mod.export_payments(cid, uid)
    if data.startswith("pl_v_"):
        return pl_mod.show_link(cid, uid, num("pl_v_"))
    if data.startswith("pl_share_"):
        return pl_mod.share_link(cid, uid, num("pl_share_"))
    if data.startswith("pl_meth_"):
        return pl_mod.show_methods(cid, uid, num("pl_meth_"))
    if data.startswith("pl_sm_"):
        _m, _l = two("pl_sm_")
        return pl_mod.set_method(cid, uid, _m, _l)
    if data.startswith("pl_use_"):
        return pl_mod.show_usage(cid, uid, num("pl_use_"))
    if data.startswith("pl_su_"):
        _k, _l = two("pl_su_")
        return pl_mod.set_usage(cid, uid, _k, _l)
    if data.startswith("pl_max_"):
        return pl_mod.start_max(cid, uid, num("pl_max_"))
    if data.startswith("pl_ask_"):
        return pl_mod.show_asks(cid, uid, num("pl_ask_"))
    if data.startswith("pl_t_"):
        _k, _l = two("pl_t_")
        return pl_mod.toggle_flag(cid, uid, _k, _l)
    if data.startswith("pl_e_"):
        _f, _l = two("pl_e_")
        return pl_mod.start_edit(cid, uid, _f, _l)
    if data.startswith("pl_tog_"):
        return pl_mod.toggle_active(cid, uid, num("pl_tog_"))
    if data.startswith("pl_dely_"):
        return pl_mod.delete_link(cid, uid, num("pl_dely_"), True)
    if data.startswith("pl_del_"):
        return pl_mod.delete_link(cid, uid, num("pl_del_"), False)
    if data.startswith("pl_tx_"):
        return pl_mod.show_payments(cid, uid, num("pl_tx_"))
    if data.startswith("plpay_"):
        return pl_mod.start_payment(cid, uid, num("plpay_"))
    if data.startswith("plrok_"):
        return pay_mod.approve_paylink_receipt(cid, uid, num("plrok_"), True)
    if data.startswith("plrno_"):
        return pay_mod.approve_paylink_receipt(cid, uid, num("plrno_"), False)

    if data == "pay_onsite":
        return pay_mod.show_onsite_debts(cid, uid)
    if data.startswith("payos_"):
        return pay_mod.mark_onsite_paid(cid, uid, num("payos_"))

    # کاربر: انتخاب روش پرداخت / تأیید امتیاز
    if data.startswith("paypick_"):
        _m, _r = two("paypick_")
        return pay_mod.pick_method(cid, uid, _m, _r)
    if data.startswith("paypt_go_"):
        return pay_mod.confirm_points(cid, uid, num("paypt_go_"), True)
    if data.startswith("paypt_other_"):
        return pay_mod.confirm_points(cid, uid, num("paypt_other_"), False)
    if data == "pay_cards":
        return pay_mod.show_cards(cid, uid)
    if data == "card_add":
        return pay_mod.start_add_card(cid, uid)
    if data.startswith("card_view_"):
        return pay_mod.view_card(cid, uid, num("card_view_"))
    if data.startswith("card_tog_"):
        return pay_mod.toggle_card(cid, uid, num("card_tog_"))
    if data.startswith("card_def_"):
        return pay_mod.set_default_card(cid, uid, num("card_def_"))
    if data.startswith("card_dely_"):
        return pay_mod.delete_card(cid, uid, num("card_dely_"), True)
    if data.startswith("card_del_"):
        return pay_mod.delete_card(cid, uid, num("card_del_"), False)
    if data == "pay_wallet":
        return pay_mod.show_wallet_info(cid, uid)
    if data == "pay_gateways":
        return pay_mod.show_gateways(cid, uid)
    if data == "gw_add":
        return pay_mod.start_add_gateway(cid, uid)
    if data.startswith("gwt_"):
        return pay_mod.pick_gateway_type(cid, uid, data[4:])
    if data.startswith("gw_view_"):
        return pay_mod.view_gateway(cid, uid, num("gw_view_"))
    if data.startswith("gw_tog_"):
        return pay_mod.toggle_gateway(cid, uid, num("gw_tog_"))
    if data.startswith("gw_del_"):
        return pay_mod.delete_gateway(cid, uid, num("gw_del_"))
    # ═══ 🛡️ فاز ۱۸-ب — هشدار فیلترشکن ═══
    if data == "pay_vpn":
        return pay_mod.show_vpn_settings(cid, uid)
    if data == "payvpn_toggle":
        return pay_mod.toggle_vpn_warn(cid, uid)
    if data == "payvpn_preview":
        return pay_mod.preview_vpn_warn(cid, uid)

    if data == "pay_texts":
        return pay_mod.show_payment_texts(cid, uid)
    if data == "ptx_reset":
        return pay_mod.reset_payment_texts(cid, uid)
    if data.startswith("ptx_"):
        return pay_mod.start_edit_payment_text(cid, uid, data[4:])
    if data == "pay_receipts":
        return _show_shared_review_inbox(cid, uid, "receipt_review")
    if data.startswith("rcpok_") or data.startswith("rcpno_"):
        # دکمه‌های پیام‌های قدیمی حق نوشتن در SQLite را ندارند.
        return _show_shared_review_inbox(
            cid, uid, "receipt_review", legacy_action=True
        )

    # ---- روش پرداخت در ویزارد رویداد ----
    # ═══ 🧭 فاز ۱۵ — دستیار بعد از ساخت رویداد ═══
    if data.startswith("evwiz_"):
        return ev_mod.show_reg_wizard(cid, uid, num("evwiz_"))
    if data.startswith("evrev_"):
        return ev_mod.show_review(cid, uid, num("evrev_"))
    if data.startswith("evrm_"):
        _m, _e = two("evrm_")
        return ev_mod.pick_reg_mode(cid, uid, _m, _e)
    if data.startswith("evpick_"):
        _f, _e = two("evpick_")
        return ev_mod.set_reg_form(cid, uid, _f, _e)
    if data.startswith("evqf_"):
        _k, _e = two("evqf_")
        return ev_mod.toggle_quick_field(cid, uid, _k, _e)
    if data.startswith("evqok_"):
        return ev_mod.build_quick_form(cid, uid, num("evqok_"))
    if data.startswith("evcap_"):
        _k, _e = two("evcap_")
        return ev_mod.start_num_edit(cid, uid, _k, _e)

    if data == "ev_paymenu":
        return ev_mod.show_payment_choice(cid, uid)
    # 🆕 فاز ۱۳ — انتخاب روش‌های چند روشی
    if data == "evmmok":
        return ev_mod.confirm_multi(cid, uid)
    if data.startswith("evmmok_"):
        return ev_mod.confirm_multi(cid, uid, num("evmmok_"))
    if data == "evmulti":
        return ev_mod.show_multi_picker(cid, uid)
    if data.startswith("evmulti_"):
        return ev_mod.show_multi_picker(cid, uid, num("evmulti_"))
    if data.startswith("evmm_"):
        _m, _e = two("evmm_")
        return ev_mod.toggle_multi_method(cid, uid, _m, _e)
    if data.startswith("paym_"):
        return ev_mod.pick_payment_method(cid, uid, data[5:])
    if data.startswith("paycard_"):
        return ev_mod.pick_payment_card(cid, uid, num("paycard_"))
    if data.startswith("paygw_"):
        return ev_mod.pick_payment_gateway(cid, uid, num("paygw_"))

    # ---- ادمین: عمومی ----
    if data == "admin_panel":
        return admin_mod.show_admin_panel(cid, uid)
    # 🆕 فاز ۱۳ — منوهای جمع‌شده
    # ═══ 📣 فاز ۲۰ — پنل تبلیغات ═══
    if data == "ad_panel":
        return ads_mod.show_panel(cid, uid)
    if data == "ad_new":
        return ads_mod.start_new(cid, uid)
    if data.startswith("adnew_"):
        return ads_mod.start_new(cid, uid, data[len("adnew_"):])
    if data.startswith("adv_"):
        return ads_mod.show_ad(cid, uid, num("adv_"))
    if data.startswith("adprev_"):
        return ads_mod.preview(cid, uid, num("adprev_"))
    if data.startswith("adtest_"):
        return ads_mod.test_send(cid, uid, num("adtest_"))
    if data.startswith("adgo2_"):
        return ads_mod.start_campaign(cid, uid, num("adgo2_"), True)
    if data.startswith("adgo_"):
        return ads_mod.start_campaign(cid, uid, num("adgo_"))
    if data.startswith("adpause_"):
        return ads_mod.pause_ad(cid, uid, num("adpause_"))
    if data.startswith("adcopy_"):
        return ads_mod.copy_ad(cid, uid, num("adcopy_"))
    if data.startswith("addel_"):
        return ads_mod.delete_ad(cid, uid, num("addel_"))
    if data.startswith("admedia_"):
        return ads_mod.start_media(cid, uid, num("admedia_"))
    if data.startswith("adbtn_"):
        return ads_mod.show_button(cid, uid, num("adbtn_"))
    if data.startswith("adab_") and not data.startswith("adabt_"):
        return ads_mod.show_ab(cid, uid, num("adab_"))
    if data.startswith("adabt_"):
        return ads_mod.toggle_ab(cid, uid, num("adabt_"))
    if data.startswith("adadv_"):
        return ads_mod.show_advanced(cid, uid, num("adadv_"))
    if data.startswith("adq_"):
        return ads_mod.toggle_quiet(cid, uid, num("adq_"))
    if data.startswith("adtgt_"):
        return ads_mod.show_target(cid, uid, num("adtgt_"))
    if data.startswith("adtg_"):
        k_, a_id = two("adtg_")
        return ads_mod.show_target(cid, uid, a_id, k_)
    if data.startswith("adsch_"):
        return ads_mod.show_schedule(cid, uid, num("adsch_"))
    if data.startswith("adsc_"):
        k_, a_id = two("adsc_")
        return ads_mod.show_schedule(cid, uid, a_id, k_)
    if data.startswith("adlink_"):
        k_, a_id = two("adlink_")
        return ads_mod.link_target(cid, uid, k_, a_id)
    if data.startswith("adle_"):
        o_, a_id = two("adle_")
        try:
            return ads_mod.link_target(cid, uid, "event", a_id, int(o_))
        except (ValueError, TypeError):
            return send(cid, "❌ نامعتبر")
    if data.startswith("adlf_"):
        o_, a_id = two("adlf_")
        try:
            return ads_mod.link_target(cid, uid, "form", a_id, int(o_))
        except (ValueError, TypeError):
            return send(cid, "❌ نامعتبر")
    if data.startswith("ade_"):
        f_, a_id = two("ade_")
        return ads_mod.start_edit(cid, uid, f_, a_id)
    if data == "ad_report":
        return ads_mod.show_report(cid, uid)
    if data == "ad_settings":
        return ads_mod.show_settings(cid, uid)
    if data == "ad_tips":
        return ads_mod.show_tips(cid, uid)
    if data.startswith("adsb_"):
        return ads_mod.toggle_setting(cid, uid, data[len("adsb_"):])
    if data.startswith("adse_"):
        return ads_mod.start_setting(cid, uid, data[len("adse_"):])
    if data.startswith("adclick_"):
        return ads_mod.click(cid, uid, num("adclick_"))
    if data == "ad_optout":
        return ads_mod.user_optout(cid, uid)

    if data == "admin_notify":
        return admin_mod.show_notify_menu(cid, uid)
    if data == "admin_care":
        return admin_mod.show_care_menu(cid, uid)
    if data == "pm_help":
        return admin_mod.show_role_help(cid, uid)
    if data.startswith("up_"):
        return admin_mod.show_user_list(cid, uid, num("up_", 0))
    if data.startswith("uv_"):
        return admin_mod.show_user_detail(cid, uid, num("uv_"))
    if data.startswith(("ub_", "uub_", "uvip_", "uadm_", "udq_", "udy_")):
        return admin_mod.handle_user_action(cid, uid, data)
    # ═══ ✏️ فاز ۱۷ — ویرایش پروفایل کاربر توسط ادمین ═══
    if data.startswith("upe_"):
        return admin_mod.show_profile_editor(cid, uid, num("upe_"))
    if data.startswith("upf_"):
        _k, _t = two("upf_")
        return admin_mod.start_edit_profile_field(cid, uid, _k, _t)
    if data.startswith("upv_"):
        _rest = data[4:]
        _parts = _rest.rsplit("_", 2)
        if len(_parts) == 3:
            return admin_mod.set_profile_choice(cid, uid, _parts[0],
                                                _parts[1], _parts[2])
        return send(cid, "❌ نامعتبر")
    if data.startswith("upst_"):
        return admin_mod.toggle_profile_status(cid, uid, num("upst_"))
    if data.startswith("uprc_"):
        return admin_mod.recalc_profile(cid, uid, num("uprc_"))

    if data == "u_search":
        return admin_mod.start_search(cid, uid)
    if data == "shared_inbox":
        return shared_workflows_mod.show_inbox(cid, uid)
    if data.startswith("wfok_"):
        return shared_workflows_mod.approve_task(cid, uid, data[5:])
    if data.startswith("wfno_"):
        return shared_workflows_mod.start_reject(cid, uid, data[5:])
    if data == "admin_subs":
        return _show_shared_review_inbox(cid, uid, "profile_review")
    if data.startswith("sa_") or data.startswith("sr_"):
        # پیام‌های قدیمی پروفایل فقط می‌توانند کارتابل سرور را باز کنند.
        return _show_shared_review_inbox(
            cid, uid, "profile_review", legacy_action=True
        )
    if data == "admin_force_join":
        return admin_mod.show_force_join_settings(cid, uid)
    if data.startswith("fj_"):
        return admin_mod.handle_force_join_callback(cid, uid, data)
    if data in {"admin_stats", "admin_stats_old"}:
        return shared_reports_mod.show_dashboard(cid, uid)

    # گزارش پاسخ‌های فرم سرور فقط‌خواندنی است و مجوز را API دوباره کنترل می‌کند.
    if data == "sfr_forms":
        return shared_form_reports_mod.show_forms(cid, uid, 0)
    if data.startswith("sfrl_"):
        raw_page = data.removeprefix("sfrl_")
        return shared_form_reports_mod.show_forms(
            cid, uid, int(raw_page) if raw_page.isdigit() else -1
        )
    if data.startswith("sfrf_"):
        return shared_form_reports_mod.show_responses(cid, uid, data.removeprefix("sfrf_"), 0)
    if data.startswith("sfrp_"):
        form_id, separator, raw_page = data.removeprefix("sfrp_").rpartition("_")
        if not separator:
            return shared_form_reports_mod.invalid_callback(cid)
        return shared_form_reports_mod.show_responses(
            cid, uid, form_id, int(raw_page) if raw_page.isdigit() else -1
        )
    if data.startswith("sfrd_"):
        return shared_form_reports_mod.show_response(cid, uid, data.removeprefix("sfrd_"))

    # گزارش‌های ربات از همان API و مجوز پایگاه مشترک استفاده می‌کنند.
    if data == "rp_period":
        return shared_reports_mod.show_periods(cid, uid)
    if data.startswith("rp_p_"):
        return shared_reports_mod.pick_period(cid, uid, data[5:])
    if data in {
        "rp_events", "rp_users", "rp_forms", "rp_att", "rp_finance",
        "rp_certs", "rp_notify", "rp_admins", "rp_top", "rp_export",
    }:
        return shared_reports_mod.show_section(cid, uid, data)

    # ═══ 🎲 قرعه‌کشی (فاز ۱۴) ═══
    if data == "lt_all":
        return lt_mod.show_all(cid, uid, 0)
    if data.startswith("lt_pg_"):
        return lt_mod.show_all(cid, uid, num("lt_pg_", 0))
    if data.startswith("lt_form_"):
        return lt_mod.show_panel(cid, uid, "form", num("lt_form_"))
    if data.startswith("lt_event_"):
        return lt_mod.show_panel(cid, uid, "event", num("lt_event_"))
    if data.startswith("lt_v_"):
        return lt_mod.show_lottery(cid, uid, num("lt_v_"))
    if data.startswith("lt_mode_"):
        return lt_mod.show_modes(cid, uid, num("lt_mode_"))
    if data.startswith("lt_setm_"):
        _m, _i = two("lt_setm_")
        return lt_mod.set_mode(cid, uid, _m, _i)
    if data.startswith("lt_when_"):
        return lt_mod.show_when(cid, uid, num("lt_when_"))
    if data.startswith("lt_setw_"):
        _w2, _i = two("lt_setw_")
        return lt_mod.set_when(cid, uid, _w2, _i)
    if data.startswith("lt_date_"):
        return lt_mod.start_date(cid, uid, num("lt_date_"))
    if data.startswith("lt_prz_"):
        return lt_mod.show_prizes(cid, uid, num("lt_prz_"))
    if data.startswith("lt_padd_"):
        return lt_mod.start_add_prize(cid, uid, num("lt_padd_"))
    if data.startswith("lt_pv_"):
        return lt_mod.view_prize(cid, uid, num("lt_pv_"))
    if data.startswith("lt_pdel_"):
        return lt_mod.delete_prize(cid, uid, num("lt_pdel_"))
    if data.startswith("ltn_minscore_"):
        return lt_mod.start_min_score(cid, uid, num("ltn_minscore_"))
    if data.startswith("ltn_"):
        _f, _i = two("ltn_")
        return lt_mod.start_prize_num(cid, uid, _f, _i)
    if data.startswith("lt_cond_"):
        return lt_mod.show_conditions(cid, uid, num("lt_cond_"))
    if data.startswith("lt_notif_"):
        return lt_mod.show_notif(cid, uid, num("lt_notif_"))
    if data.startswith("lt_tog_"):
        _k, _i = two("lt_tog_")
        return lt_mod.toggle_flag(cid, uid, _k, _i)
    if data.startswith("lt_draw_"):
        return lt_mod.confirm_draw(cid, uid, num("lt_draw_"))
    if data.startswith("lt_go_"):
        return lt_mod.run_draw(cid, uid, num("lt_go_"))
    if data.startswith("lt_win_"):
        return lt_mod.show_winners(cid, uid, num("lt_win_"))
    if data.startswith("lt_rsty_"):
        return lt_mod.reset_draw(cid, uid, num("lt_rsty_"), True)
    if data.startswith("lt_reset_"):
        return lt_mod.reset_draw(cid, uid, num("lt_reset_"), False)
    if data.startswith("lt_exp_"):
        return lt_mod.export_winners(cid, uid, num("lt_exp_"))
    if data.startswith("ltu_form_"):
        return lt_mod.user_result(cid, uid, "form", num("ltu_form_"))
    if data.startswith("ltu_event_"):
        return lt_mod.user_result(cid, uid, "event", num("ltu_event_"))
    if data == "admin_dbinfo":
        return admin_mod.show_dbinfo(cid, uid)
    if data == "admin_backup":
        return admin_mod.show_backup_panel(cid, uid)
    if data == "admin_backup_now":
        return admin_mod.do_backup(cid, uid)
    if data == "admin_backup_last":
        return admin_mod.send_last_backup(cid, uid)
    if data == "admin_export":
        return admin_mod.export_users(cid, uid)
    if data == "admin_import":
        return imp_mod.handle_import_command({"chat": {"id": cid}, "from": {"id": uid}})
    if data == "admin_broadcast":
        return admin_mod.start_broadcast(cid, uid)
    if data == "bc_go":
        return admin_mod.do_broadcast(cid, uid)

    # ---- تنظیمات ----
    if data == "admin_settings":
        return set_mod.show_settings(cid, uid)
    if data == "set_texts":
        return set_mod.show_texts(cid, uid)
    if data.startswith("txtcat_"):
        cats = []
        for _, _, c in set_mod.EDITABLE_TEXTS:
            if c not in cats:
                cats.append(c)
        i = num("txtcat_", 0)
        if 0 <= i < len(cats):
            return set_mod.show_texts(cid, uid, cats[i])
        return
    if data.startswith("txted_"):
        return set_mod.start_edit_text(cid, uid, data[6:])
    if data == "set_otp":
        return set_mod.show_otp_settings(cid, uid)
    if data == "otp_test":
        return set_mod.start_otp_test(cid, uid)
    if data == "tx_list":
        # 🔄 فاز ۱۳: به لیست کامل مالی هدایت می‌شود (سازگاری با نسخه قبل)
        return fin_mod.show_transactions(cid, uid, 0, "all")
    if data == "pay_test":
        return set_mod.payment_test_menu(cid, uid)
    if data == "pay_test_invoice":
        return set_mod.confirm_test_invoice(cid, uid)
    if data == "pay_test_inv_go":
        return set_mod.send_test_invoice(cid, uid)
    if data == "pay_test_event":
        return set_mod.create_test_event(cid, uid)
    if data == "pay_test_inquire":
        return set_mod.start_inquire(cid, uid)
    if data.startswith("pay_test_del_"):
        return set_mod.delete_test_event(cid, uid, num("pay_test_del_"))

    # ═══════════════════════════════════════════════════
    # 📝 فرم‌ساز — بخش ادمین
    # ═══════════════════════════════════════════════════
    if data == "fb_panel":
        return fb_mod.show_panel(cid, uid)
    if data == "fb_new":
        return fb_mod.start_create(cid, uid)
    if data.startswith("fbt_"):
        return fb_mod.pick_type(cid, uid, data[4:])
    if data == "fb_list":
        return fb_mod.show_list(cid, uid, 0)
    if data == "fb_filter":
        return fb_mod.show_filter(cid, uid)
    if data == "fb_search":
        return fb_mod.start_search(cid, uid)
    if data.startswith("fbflt_"):
        return fb_mod.show_list(cid, uid, 0, ftype=data[6:])
    if data.startswith("fbpg_"):
        rest = data[5:]
        if "_" in rest:
            p, ft = rest.split("_", 1)
            return fb_mod.show_list(cid, uid, int(p) if p.isdigit() else 0, ftype=ft)
        return fb_mod.show_list(cid, uid, int(rest) if rest.isdigit() else 0)
    if data == "fb_allresp":
        return fb_mod.show_all_responses(cid, uid)
    if data == "fb_allstats":
        return fb_mod.show_all_stats(cid, uid)
    if data == "fb_admins":
        return admin_mod.show_admins(cid, uid)
    if data == "fb_settings":
        return fb_mod.show_settings(cid, uid)
    if data == "fb_texts":
        return fb_mod.show_texts(cid, uid)
    if data.startswith("fbtxt_"):
        return fb_mod.start_edit_text(cid, uid, data[6:])
    if data == "fb_txtreset":
        return fb_mod.reset_texts(cid, uid)
    if data == "fb_clearcache":
        return fb_mod.clear_cache(cid, uid)
    if data == "fb_cleandraft":
        return fb_mod.clean_drafts(cid, uid)
    if data == "fb_gtags":
        return fb_mod.show_global_tags(cid, uid)
    if data == "fb_tagadd":
        return fb_mod.start_add_tag(cid, uid)
    if data.startswith("fbtagaddf_"):
        return fb_mod.start_add_tag(cid, uid, num("fbtagaddf_"))
    if data.startswith("fbtagdel_"):
        return fb_mod.delete_tag(cid, uid, num("fbtagdel_"))
    if data.startswith("fbtags_"):
        return fb_mod.show_form_tags(cid, uid, num("fbtags_"))
    if data == "fb_copyfrom":
        return fb_mod.show_list(cid, uid, 0)

    # ---- یک فرم ----
    if data.startswith("fbv_"):
        return fb_mod.show_form(cid, uid, num("fbv_"))
    if data.startswith("fbmore_"):
        return fb_mod.show_more(cid, uid, num("fbmore_"))
    if data.startswith("fbinfo_"):
        return fb_mod.show_info(cid, uid, num("fbinfo_"))
    if data.startswith("fbmedia_"):
        return fb_mod.show_media(cid, uid, num("fbmedia_"))
    if data.startswith("fbban_"):
        return fb_mod.start_media(cid, uid, num("fbban_"), "banner")
    if data.startswith("fblogo_"):
        return fb_mod.start_media(cid, uid, num("fblogo_"), "logo")
    if data.startswith("fbbandel_"):
        return fb_mod.delete_media(cid, uid, num("fbbandel_"), "banner")
    if data.startswith("fblogodel_"):
        return fb_mod.delete_media(cid, uid, num("fblogodel_"), "logo")
    if data.startswith("fbset_"):
        key, f_id = two("fbset_")
        return fb_mod.start_edit_info(cid, uid, f_id, key)
    if data.startswith("fbpub_"):
        return fb_mod.publish_form(cid, uid, num("fbpub_"), True)
    if data.startswith("fbunpub_"):
        return fb_mod.publish_form(cid, uid, num("fbunpub_"), False)
    if data.startswith("fblink_"):
        return fb_mod.show_link(cid, uid, num("fblink_"))
    if data.startswith("fbqr_"):
        return fb_mod.show_qr(cid, uid, num("fbqr_"))
    if data.startswith("fbcopy_"):
        return fb_mod.copy_form(cid, uid, num("fbcopy_"))
    if data.startswith("fbdely_"):
        return fb_mod.delete_form(cid, uid, num("fbdely_"), True)
    if data.startswith("fbdel_"):
        return fb_mod.delete_form(cid, uid, num("fbdel_"), False)
    if data.startswith("fbfadm_"):
        return fb_mod.show_form_admins(cid, uid, num("fbfadm_"))
    if data.startswith("fbadmadd_"):
        return fb_mod.start_add_form_admin(cid, uid, num("fbadmadd_"))
    if data.startswith("fbadmdel_"):
        rid_, f_id = two("fbadmdel_")
        return fb_mod.remove_form_admin(cid, uid, rid_, f_id)
    if data.startswith("fblinkev_"):
        return fb_mod.show_link_event(cid, uid, num("fblinkev_"))
    if data.startswith("fbeva_"):
        return fb_mod.show_event_access(cid, uid, num("fbeva_"))
    if data.startswith("fbevs_"):
        _m, _f = two("fbevs_")
        return fb_mod.show_event_access(cid, uid, _f, _m)
    if data.startswith("fblev_"):
        e_id, f_id = two("fblev_")
        try:
            return fb_mod.show_link_event(cid, uid, f_id, int(e_id))
        except (ValueError, TypeError):
            return fb_mod.show_link_event(cid, uid, f_id)

    # ---- پرداخت فرم ----
    if data.startswith("fbpay_"):
        return fb_mod.show_payment(cid, uid, num("fbpay_"))
    if data.startswith("fbprice_"):
        return fb_mod.start_price(cid, uid, num("fbprice_"))
    if data.startswith("fbpm_"):
        method, f_id = two("fbpm_")
        return fb_mod.set_payment_method(cid, uid, f_id, method)
    if data.startswith("fbpcard_"):
        return fb_mod.pick_card(cid, uid, num("fbpcard_"))
    if data.startswith("fbpcs_"):
        c_id, f_id = two("fbpcs_")
        try:
            return fb_mod.pick_card(cid, uid, f_id, int(c_id))
        except (ValueError, TypeError):
            return fb_mod.pick_card(cid, uid, f_id)
    if data.startswith("fbpgw_"):
        return fb_mod.pick_gateway(cid, uid, num("fbpgw_"))
    if data.startswith("fbpgs_"):
        g_id, f_id = two("fbpgs_")
        try:
            return fb_mod.pick_gateway(cid, uid, f_id, int(g_id))
        except (ValueError, TypeError):
            return fb_mod.pick_gateway(cid, uid, f_id)

    # ---- تنظیمات پیشرفته ----
    # ═══ 📄 فاز ۱۵ — غیبت مجاز ═══
    if data == "exq_new":
        return att_mod.start_excuse(cid, uid)
    if data.startswith("exqe_"):
        return att_mod.start_excuse(cid, uid, num("exqe_"))
    if data == "ex_list":
        return att_mod.show_excuses(cid, uid)
    if data.startswith("exok_"):
        return att_mod.review_excuse(cid, uid, num("exok_"), True)
    if data.startswith("exno_"):
        return att_mod.review_excuse(cid, uid, num("exno_"), False)

    # ═══ 🆕 فاز ۱۵ — گواهینامه/کارت/پیام فرم (کاربر) ═══
    if data.startswith("ffcert_"):
        return fill_mod.send_form_cert(cid, uid, num("ffcert_"))
    if data.startswith("ffcard_"):
        return fill_mod.send_id_card(cid, uid, num("ffcard_"))
    if data.startswith("ffmsg_"):
        return fill_mod.start_contact(cid, uid, num("ffmsg_"))

    # ═══ 🔀 فاز ۱۷ — گردش کار: صف تأیید ═══
    if data == "fb_approvals":
        return frep_mod.show_approvals(cid, uid, 0)
    if data.startswith("fwok_"):
        return frep_mod.review_response(cid, uid, num("fwok_"), True)
    if data.startswith("fwno_"):
        return frep_mod.review_response(cid, uid, num("fwno_"), False)

    if data.startswith("fbrev_"):
        return fb_mod.show_review(cid, uid, num("fbrev_"))
    # ⚠️ ترتیب مهم: fbadv2_ قبل از fbadv_ چون پیشوند مشترک دارند
    if data.startswith("fbadv2_"):
        return fb_mod.show_advanced2(cid, uid, num("fbadv2_"))
    if data.startswith("fbadv_"):
        return fb_mod.show_advanced(cid, uid, num("fbadv_"))
    # ═══ 🔐 فاز ۲۳ — دسترسی کاربر بعد از ثبت ═══
    if data.startswith("fbafter_"):
        return fb_mod.show_after_submit(cid, uid, num("fbafter_"))
    if data.startswith("fbaft_"):
        _m, _f = two("fbaft_")
        return fb_mod.set_after_submit(cid, uid, _f, _m)
    # ═══ 📢 اطلاع‌رسانی فرم ═══
    if data.startswith("fbnoty_"):
        return fb_mod.notify_users(cid, uid, num("fbnoty_"), True)
    if data.startswith("fbnotify_"):
        return fb_mod.notify_users(cid, uid, num("fbnotify_"), False)
    # ═══ ☑️ چند مورد هزینه‌دار ═══
    if data.startswith("fbimt_"):
        return ff_mod.toggle_multi_item(cid, uid, num("fbimt_"))
    if data.startswith("fbimx_"):
        return ff_mod.start_max_items(cid, uid, num("fbimx_"))
    if data.startswith("fbtog_"):
        col, f_id = two("fbtog_")
        return fb_mod.toggle_setting(cid, uid, f_id, col)
    if data.startswith("fbdirs_"):
        d_, f_id = two("fbdirs_")
        return fb_mod.set_dir(cid, uid, f_id, d_)
    if data.startswith("fbdir_"):
        return fb_mod.show_dir(cid, uid, num("fbdir_"))
    if data.startswith("fbdisps_"):
        m_, f_id = two("fbdisps_")
        return fb_mod.set_display(cid, uid, f_id, m_)
    if data.startswith("fbdisp_"):
        return fb_mod.show_display(cid, uid, num("fbdisp_"))
    if data.startswith("fbpvs_"):
        m_, f_id = two("fbpvs_")
        return fb_mod.set_phone_mode(cid, uid, f_id, m_)
    if data.startswith("fbpv_"):
        return fb_mod.show_phone_mode(cid, uid, num("fbpv_"))
    if data.startswith("fblimit_"):
        return fb_mod.show_limit(cid, uid, num("fblimit_"))
    if data.startswith("fbmax_"):
        return fb_mod.start_max(cid, uid, num("fbmax_"))
    if data.startswith("fbtime_"):
        w_, f_id = two("fbtime_")
        return fb_mod.start_time(cid, uid, f_id, w_)

    # ---- سوالات فرم ----
    if data.startswith("fbfa2_"):
        return frep_mod.show_field_analysis_menu(cid, uid, num("fbfa2_"))
    if data.startswith("fbfa_"):
        return ff_mod.show_add_field(cid, uid, num("fbfa_"))
    if data.startswith("fbcats_"):
        return ff_mod.show_all_cats(cid, uid, num("fbcats_"))
    if data.startswith("fbtpl_"):
        return fb_mod.use_template(cid, uid, num("fbtpl_"))
    if data.startswith("fbdet_"):
        return fb_mod.show_details(cid, uid, num("fbdet_"))

    # ── ✨ فاز ۱۸-الف: امکانات ویژه هر نوع فرم ──
    if data.startswith("fbfeat_"):
        return fb_mod.show_features(cid, uid, num("fbfeat_"))
    if data.startswith("fbft_"):
        k_, f_id = two("fbft_")
        return fb_mod.toggle_feature(cid, uid, k_, f_id)
    if data.startswith("fbfx_"):
        k_, f_id = two("fbfx_")
        return fb_mod.start_feature_edit(cid, uid, k_, f_id)

    # ── 👁️ فاز ۱۸-الف: سطح دسترسی فرم ──
    if data.startswith("fbvis_"):
        return fb_mod.show_visibility(cid, uid, num("fbvis_"))
    if data.startswith("fbvs_"):
        v_, f_id = two("fbvs_")
        return fb_mod.set_visibility(cid, uid, v_, f_id)
    if data.startswith("fbsec_"):
        rest_ = data[len("fbsec_"):]
        if "_" in rest_:
            a, b = rest_.split("_", 1)
            try:
                return fb_mod.show_sections(cid, uid, int(a), b)
            except (ValueError, TypeError):
                pass
        return fb_mod.show_sections(cid, uid, num("fbsec_"))
    if data.startswith("fbcode_"):
        return fb_mod.start_access_code(cid, uid, num("fbcode_"))
    if data.startswith("fbterms_"):
        return fb_mod.show_terms(cid, uid, num("fbterms_"))
    if data.startswith("fbtt_"):
        return ff_mod.start_terms_text(cid, uid, num("fbtt_"))
    if data.startswith("fbit_"):
        return ff_mod.show_items(cid, uid, num("fbit_"))
    if data.startswith("fbia_"):
        return ff_mod.start_add_item(cid, uid, num("fbia_"))
    if data.startswith("fbie_"):
        i_, fl_ = two("fbie_")
        return ff_mod.start_add_item(cid, uid, fl_, i_)
    if data.startswith("fbid_"):
        i_, fl_ = two("fbid_")
        return ff_mod.delete_item(cid, uid, fl_, i_)
    if data.startswith("fbfs_"):
        return ff_mod.start_field_search(cid, uid, num("fbfs_"))
    if data.startswith("fbfp_"):
        p_, f_id = two("fbfp_")
        return ff_mod.show_fields(cid, uid, f_id, int(p_) if p_.isdigit() else 0)
    if data.startswith("fbf_"):
        return ff_mod.show_fields(cid, uid, num("fbf_"), 0)
    if data.startswith("fbc_"):
        cat, f_id = two("fbc_")
        return ff_mod.show_category(cid, uid, f_id, cat)
    if data.startswith("fbn_"):
        ftype, f_id = two("fbn_")
        return ff_mod.create_field(cid, uid, f_id, ftype)
    if data.startswith("fbfe_"):
        return ff_mod.edit_field(cid, uid, num("fbfe_"))
    if data.startswith("fbfl_"):
        return ff_mod.start_edit_field_text(cid, uid, num("fbfl_"), "label")
    if data.startswith("fbfd_"):
        return ff_mod.start_edit_field_text(cid, uid, num("fbfd_"), "description")
    if data.startswith("fbfh_"):
        return ff_mod.start_edit_field_text(cid, uid, num("fbfh_"), "help_text")
    if data.startswith("fbfreq_"):
        return ff_mod.toggle_required(cid, uid, num("fbfreq_"))
    if data.startswith("fbfsc_"):
        return ff_mod.start_field_number(cid, uid, num("fbfsc_"), "score")
    if data.startswith("fbfmf_"):
        return ff_mod.start_field_number(cid, uid, num("fbfmf_"), "max_files")
    if data.startswith("fbfmm_"):
        return ff_mod.start_field_number(cid, uid, num("fbfmm_"), "minmax")
    if data.startswith("fbfc_"):
        return ff_mod.start_field_number(cid, uid, num("fbfc_"), "correct")
    if data.startswith("fbfmedset_"):
        return ff_mod.set_field_media(cid, uid, num("fbfmedset_"))
    if data.startswith("fbfmeddel_"):
        return ff_mod.delete_field_media(cid, uid, num("fbfmeddel_"))
    if data.startswith("fbfmed_"):
        return ff_mod.start_field_media(cid, uid, num("fbfmed_"))
    if data.startswith("fbfup_"):
        return ff_mod.move_field(cid, uid, num("fbfup_"), "up")
    if data.startswith("fbfdn_"):
        return ff_mod.move_field(cid, uid, num("fbfdn_"), "down")
    if data.startswith("fbfcp_"):
        return ff_mod.copy_field(cid, uid, num("fbfcp_"))
    if data.startswith("fbfdely_"):
        return ff_mod.delete_field(cid, uid, num("fbfdely_"), True)
    if data.startswith("fbfdel_"):
        return ff_mod.delete_field(cid, uid, num("fbfdel_"), False)
    if data.startswith("fbsort_"):
        return ff_mod.show_sort(cid, uid, num("fbsort_"))
    if data.startswith("fbsu_"):
        return ff_mod.move_in_sort(cid, uid, num("fbsu_"), "up")
    if data.startswith("fbsd_"):
        return ff_mod.move_in_sort(cid, uid, num("fbsd_"), "down")

    # ---- گزینه‌ها ----
    if data.startswith("fbfo_"):
        return ff_mod.show_options(cid, uid, num("fbfo_"))
    if data.startswith("fboa_"):
        return ff_mod.start_add_option(cid, uid, num("fboa_"), False)
    if data.startswith("fbob_"):
        return ff_mod.start_add_option(cid, uid, num("fbob_"), True)
    if data.startswith("fbocl_"):
        return ff_mod.clear_options(cid, uid, num("fbocl_"))
    if data.startswith("fboe_"):
        i_, fl_id = two("fboe_")
        return ff_mod.start_edit_option(cid, uid, fl_id, i_)
    if data.startswith("fbod_"):
        i_, fl_id = two("fbod_")
        return ff_mod.delete_option(cid, uid, fl_id, i_)
    if data.startswith("fbou_"):
        i_, fl_id = two("fbou_")
        return ff_mod.move_option_up(cid, uid, fl_id, i_)

    # ---- شرط ----
    if data.startswith("fbfcond_"):
        return ff_mod.show_condition(cid, uid, num("fbfcond_"))
    if data.startswith("fbcfs_"):
        r_, fl_id = two("fbcfs_")
        return ff_mod.pick_condition_field(cid, uid, fl_id, r_)
    if data.startswith("fbcf_"):
        return ff_mod.pick_condition_field(cid, uid, num("fbcf_"))
    if data.startswith("fbcos_"):
        op_, fl_id = two("fbcos_")
        return ff_mod.pick_condition_op(cid, uid, fl_id, op_)
    if data.startswith("fbco_"):
        return ff_mod.pick_condition_op(cid, uid, num("fbco_"))
    if data.startswith("fbcv_"):
        return ff_mod.start_condition_value(cid, uid, num("fbcv_"))
    if data.startswith("fbcd_"):
        return ff_mod.delete_condition(cid, uid, num("fbcd_"))

    # ---- پاسخ‌ها و گزارش ----
    if data.startswith("fbrp_"):
        p_, f_id = two("fbrp_")
        return frep_mod.show_responses(cid, uid, f_id, int(p_) if p_.isdigit() else 0)
    if data.startswith("fbrfs_"):
        flt, f_id = two("fbrfs_")
        return frep_mod.show_responses(cid, uid, f_id, 0, flt)
    if data.startswith("fbrf_"):
        return frep_mod.show_resp_filter(cid, uid, num("fbrf_"))
    if data.startswith("fbrv_"):
        return frep_mod.view_response(cid, uid, num("fbrv_"))
    if data.startswith("fbrm_"):
        return frep_mod.show_response_media(cid, uid, num("fbrm_"))
    if data.startswith("fbrts_"):
        t_, r_id = two("fbrts_")
        return frep_mod.toggle_tag(cid, uid, t_, r_id)
    if data.startswith("fbrt_"):
        return frep_mod.show_tag_picker(cid, uid, num("fbrt_"))
    if data.startswith("fbrn_"):
        return frep_mod.start_note(cid, uid, num("fbrn_"))
    if data.startswith("fbrmsg_"):
        return frep_mod.start_msg_user(cid, uid, num("fbrmsg_"))
    if data.startswith("sftcheck_"):
        return shared_form_ticket_mod.check_in(cid, uid, data[len("sftcheck_"):])
    if data.startswith("fbrok_"):
        return frep_mod.approve_response(cid, uid, num("fbrok_"))
    if data.startswith("fbrtk_"):
        return frep_mod.send_ticket_to_user(cid, uid, num("fbrtk_"))
    if data.startswith("fbrdy_"):
        return frep_mod.delete_response(cid, uid, num("fbrdy_"), True)
    if data.startswith("fbrdel_"):
        return frep_mod.delete_response(cid, uid, num("fbrdel_"), False)
    if data.startswith("fbr_"):
        return frep_mod.show_responses(cid, uid, num("fbr_"), 0)
    if data.startswith("fbrep_"):
        return frep_mod.show_report(cid, uid, num("fbrep_"))
    if data.startswith("fban_"):
        return frep_mod.analyze_field(cid, uid, num("fban_"))
    if data.startswith("fbres_"):
        return frep_mod.show_results(cid, uid, num("fbres_"))
    if data.startswith("fbx_"):
        return frep_mod.export_excel(cid, uid, num("fbx_"))
    if data.startswith("fbpdf_"):
        return frep_mod.export_text(cid, uid, num("fbpdf_"))
    if data.startswith("fbprev_"):
        return frep_mod.preview_form(cid, uid, num("fbprev_"))
    if data.startswith("fbcastgo_"):
        return frep_mod.do_broadcast_form(cid, uid, num("fbcastgo_"))
    if data.startswith("fbcast_"):
        return frep_mod.broadcast_form(cid, uid, num("fbcast_"))

    # ═══════════════════════════════════════════════════
    # ✍️ پر کردن فرم — بخش کاربر
    # ═══════════════════════════════════════════════════
    if data == "u_forms":
        return fill_mod.show_public_forms(cid, uid, 0)
    if data == "ff_myforms":
        return fill_mod.show_my_forms(cid, uid, 0)
    if data.startswith("ffmypg_"):
        return fill_mod.show_my_forms(cid, uid, num("ffmypg_", 0))
    if data == "ff_local_forms":
        return fill_mod.show_local_my_forms(cid, uid, 0)
    if data.startswith("fflocalpg_"):
        return fill_mod.show_local_my_forms(cid, uid, num("fflocalpg_", 0))
    if data.startswith("ffsr_"):
        return fill_mod.show_shared_response(cid, uid, data.removeprefix("ffsr_"))
    if data.startswith("ffpg_"):
        return fill_mod.show_public_forms(cid, uid, num("ffpg_", 0))
    if data.startswith("ffopen_"):
        return fill_mod.open_form(cid, uid, str(num("ffopen_")), user)
    if data.startswith("ffstart_"):
        return fill_mod.start_fill(cid, uid, num("ffstart_"))
    if data.startswith("ffnew_"):
        return fill_mod.restart_fill(cid, uid, num("ffnew_"))
    if data.startswith("ffres_"):
        return fill_mod.resume_fill(cid, uid, num("ffres_"))
    if data == "fflist":
        return fill_mod.show_question_list(cid, uid)
    if data == "ffprev":
        return fill_mod.go_prev_question(cid, uid)
    if data.startswith("ffq_"):
        return fill_mod.ask_field(cid, uid, num("ffq_"))
    if data.startswith("ffi_"):
        i_, fl_id = two("ffi_")
        return fill_mod.pick_item(cid, uid, fl_id, i_)
    if data.startswith("ffo_"):
        i_, fl_id = two("ffo_")
        return fill_mod.pick_option(cid, uid, fl_id, i_)
    if data.startswith("ffmok_"):
        return fill_mod.confirm_multi(cid, uid, num("ffmok_"))
    if data.startswith("ffm_"):
        i_, fl_id = two("ffm_")
        return fill_mod.toggle_multi(cid, uid, fl_id, i_)
    if data.startswith("ffr_"):
        v_, fl_id = two("ffr_")
        return fill_mod.pick_rating(cid, uid, fl_id, v_)
    if data.startswith("ffy_"):
        return fill_mod.pick_confirm(cid, uid, num("ffy_"), True)
    if data.startswith("ffn_"):
        return fill_mod.pick_confirm(cid, uid, num("ffn_"), False)
    if data.startswith("ffe_"):
        i_, fl_id = two("ffe_")
        return fill_mod.pick_education(cid, uid, fl_id, i_)
    if data.startswith("ffcyo_"):
        return fill_mod.other_city(cid, uid, num("ffcyo_"))
    if data.startswith("ffcy_"):
        i_, fl_id = two("ffcy_")
        return fill_mod.pick_city(cid, uid, fl_id, i_)
    if data.startswith("ffp_"):
        i_, fl_id = two("ffp_")
        return fill_mod.pick_province(cid, uid, fl_id, i_)
    if data.startswith("ffskip_"):
        return fill_mod.skip_field(cid, uid, num("ffskip_"))
    if data.startswith("fffok_"):
        return fill_mod.confirm_files(cid, uid, num("fffok_"))
    if data.startswith("ffsubmit_"):
        return fill_mod.submit_form(cid, uid, num("ffsubmit_"))
    if data.startswith("ffcancel_"):
        return fill_mod.cancel_fill(cid, uid, num("ffcancel_"))
    # ═══ 🧾 فاز ۲۳ — صورتحساب · چند مورد · انصراف ═══
    if data.startswith("ffinv_"):
        return fill_mod.show_invoice(cid, uid, num("ffinv_"))
    if data.startswith("ffpay_"):
        return fill_mod.go_pay(cid, uid, num("ffpay_"))
    if data.startswith("ffback_"):
        return fill_mod.back_to_form(cid, uid, num("ffback_"))
    if data.startswith("ffwdy_"):
        return fill_mod.withdraw_response(cid, uid, num("ffwdy_"), True)
    if data.startswith("ffwd_"):
        return fill_mod.withdraw_response(cid, uid, num("ffwd_"), False)
    if data.startswith("ffim_"):
        _p = data.replace("ffim_", "").split("_")
        try:
            return fill_mod.toggle_item(cid, uid, int(_p[1]), int(_p[0]))
        except (ValueError, IndexError):
            return
    if data.startswith("ffiok_"):
        return fill_mod.confirm_items(cid, uid, num("ffiok_"))
    if data.startswith("fftk_"):
        return fill_mod.send_ticket(cid, uid, num("fftk_"))
    if data.startswith("ffedit_"):
        return fill_mod.edit_my_response(cid, uid, num("ffedit_"))
    if data.startswith("ffmy_"):
        return fill_mod.show_my_response(cid, uid, num("ffmy_"))

    # ═══════════════════════════════════════════════════
    # ⚙️ قابلیت‌های پیشرفته رویداد (فاز ۱۱)
    # ═══════════════════════════════════════════════════
    if data.startswith("evx_"):
        return ev_mod.show_advanced(cid, uid, num("evx_"))
    # ═══ 🎉 فاز ۲۳ — منوی مرتب رویداد ═══
    if data.startswith("evset_"):
        return ev_mod.show_event_settings(cid, uid, num("evset_"))
    if data.startswith("evmore_"):
        return ev_mod.show_event_more(cid, uid, num("evmore_"))
    if data.startswith("evinv_"):
        return ev_mod.show_invites(cid, uid, num("evinv_"))
    if data.startswith("evres_"):
        return ev_mod.show_restrictions(cid, uid, num("evres_"))
    if data.startswith("evshow_"):
        return ev_mod.show_display_opts(cid, uid, num("evshow_"))
    if data.startswith("evcnt_"):
        return ev_mod.show_content(cid, uid, num("evcnt_"))
    if data.startswith("evloc_"):
        return ev_mod.show_location_opts(cid, uid, num("evloc_"))
    if data.startswith("evref_"):
        return ev_mod.show_refund(cid, uid, num("evref_"))
    if data.startswith("evrem_"):
        return ev_mod.show_reminder(cid, uid, num("evrem_"))
    if data.startswith("evrate_"):
        return ev_mod.show_ratings(cid, uid, num("evrate_"))
    if data.startswith("evgens_"):
        g_, e_ = two("evgens_")
        return ev_mod.show_gender_restrict(cid, uid, e_, g_)
    if data.startswith("evgen_"):
        return ev_mod.show_gender_restrict(cid, uid, num("evgen_"))
    if data.startswith("evlts_"):
        t_, e_ = two("evlts_")
        return ev_mod.show_link_time(cid, uid, e_, t_)
    if data.startswith("evlt_"):
        return ev_mod.show_link_time(cid, uid, num("evlt_"))
    if data.startswith("evtogr_"):
        c_, e_ = two("evtogr_")
        return ev_mod.toggle_ev(cid, uid, e_, c_, back="review")
    if data.startswith("evtog_"):
        c_, e_ = two("evtog_")
        return ev_mod.toggle_ev(cid, uid, e_, c_)
    if data.startswith("evtxt_"):
        k_, e_ = two("evtxt_")
        return ev_mod.start_ev_text(cid, uid, e_, k_)
    if data.startswith("evnum_"):
        k_, e_ = two("evnum_")
        return ev_mod.start_ev_num(cid, uid, e_, k_)
    if data.startswith("evcadd_"):
        return ev_mod.add_code(cid, uid, num("evcadd_"))
    if data.startswith("evcdel_"):
        c_, e_ = two("evcdel_")
        return ev_mod.delete_code(cid, uid, c_, e_)
    if data.startswith("evcode_"):
        return ev_mod.show_codes(cid, uid, num("evcode_"))
    if data.startswith("evpwdset_"):
        return ev_mod.start_password(cid, uid, num("evpwdset_"))
    if data.startswith("evpwddel_"):
        return ev_mod.delete_password(cid, uid, num("evpwddel_"))
    if data.startswith("evpwd_"):
        return ev_mod.show_password(cid, uid, num("evpwd_"))

    # ---- 📊 نظرسنجی / 📝 فرم / 🎁 تخفیف رویداد ----
    if data.startswith("evsurv_"):
        return ev_mod.show_survey(cid, uid, num("evsurv_"))
    if data.startswith("evsfnew_"):
        return ev_mod.create_survey_form(cid, uid, num("evsfnew_"))
    if data.startswith("evsfs_"):
        f_, e_ = two("evsfs_")
        try:
            return ev_mod.pick_survey_form(cid, uid, e_, int(f_))
        except (ValueError, TypeError):
            return ev_mod.pick_survey_form(cid, uid, e_)
    if data.startswith("evsf_"):
        return ev_mod.pick_survey_form(cid, uid, num("evsf_"))
    if data.startswith("evsts_"):
        t_, e_ = two("evsts_")
        return ev_mod.show_survey_time(cid, uid, e_, t_)
    if data.startswith("evst_"):
        return ev_mod.show_survey_time(cid, uid, num("evst_"))
    if data.startswith("evformnew_"):
        return ev_mod.create_reg_form(cid, uid, num("evformnew_"))
    if data.startswith("evforms_"):
        f_, e_ = two("evforms_")
        try:
            return ev_mod.show_reg_form(cid, uid, e_, int(f_))
        except (ValueError, TypeError):
            return ev_mod.show_reg_form(cid, uid, e_)
    if data.startswith("evform_"):
        return ev_mod.show_reg_form(cid, uid, num("evform_"))
    if data.startswith("evdisc_"):
        return ev_mod.show_discounts(cid, uid, num("evdisc_"))
    if data.startswith("evdadd_"):
        return ev_mod.start_add_discount(cid, uid, num("evdadd_"))
    if data.startswith("evdrep_"):
        return ev_mod.discount_report(cid, uid, num("evdrep_"))
    if data.startswith("evdv_"):
        d_, e_ = two("evdv_")
        return ev_mod.view_discount(cid, uid, d_, e_)
    if data.startswith("evdtg_"):
        d_, e_ = two("evdtg_")
        return ev_mod.toggle_discount(cid, uid, d_, e_)
    if data.startswith("evddel_"):
        d_, e_ = two("evddel_")
        return ev_mod.delete_discount(cid, uid, d_, e_)

    # ═══════════════════════════════════════════════════
    # 🎂 مناسبت‌ها و تبریک خودکار
    # ═══════════════════════════════════════════════════
    if data == "oc_panel":
        return oc_mod.show_panel(cid, uid)
    if data == "oc_tog_birthday":
        return oc_mod.toggle_flag(cid, uid, "birthday")
    if data == "oc_tog_enabled":
        return oc_mod.toggle_flag(cid, uid, "enabled")
    if data == "oc_list":
        return oc_mod.show_list(cid, uid, 0)
    if data.startswith("oc_pg_"):
        return oc_mod.show_list(cid, uid, num("oc_pg_", 0))
    if data == "oc_add":
        return oc_mod.start_add(cid, uid)
    if data == "oc_bpoints":
        return oc_mod.start_bpoints(cid, uid)
    if data == "oc_texts":
        return oc_mod.show_texts(cid, uid)
    if data.startswith("octx_"):
        return oc_mod.start_edit_text(cid, uid, "oc_txt_" + data[5:])
    if data == "oc_run":
        return oc_mod.run_now(cid, uid)
    if data == "oc_history":
        return oc_mod.show_history(cid, uid)
    if data.startswith("oc_v_"):
        return oc_mod.view_occasion(cid, uid, num("oc_v_"))
    if data.startswith("oc_tg_"):
        return oc_mod.toggle_occasion(cid, uid, num("oc_tg_"))
    if data.startswith("oc_dely_"):
        return oc_mod.delete_occasion(cid, uid, num("oc_dely_"), True)
    if data.startswith("oc_del_"):
        return oc_mod.delete_occasion(cid, uid, num("oc_del_"), False)
    if data.startswith("oc_date_"):
        return oc_mod.start_edit(cid, uid, num("oc_date_"), "date")
    if data.startswith("oc_pts_"):
        return oc_mod.start_edit(cid, uid, num("oc_pts_"), "pts")
    if data.startswith("oc_msg_"):
        return oc_mod.start_edit(cid, uid, num("oc_msg_"), "msg")
    if data.startswith("oc_gens_"):
        g_, o_id = two("oc_gens_")
        return oc_mod.show_gender(cid, uid, o_id, g_)
    if data.startswith("oc_gen_"):
        return oc_mod.show_gender(cid, uid, num("oc_gen_"))
    if data.startswith("oc_test_"):
        return oc_mod.test_occasion(cid, uid, num("oc_test_"))

    # ---- 🏅 امتیازهای شرطی ----
    if data == "pr_list":
        return oc_mod.show_rules(cid, uid)
    if data == "pr_toggle_sys":
        return oc_mod.toggle_rules_system(cid, uid)
    if data == "pr_add":
        return oc_mod.start_add_rule(cid, uid)
    if data.startswith("pr_v_"):
        return oc_mod.view_rule(cid, uid, num("pr_v_"))
    if data.startswith("pr_tg_"):
        return oc_mod.toggle_rule(cid, uid, num("pr_tg_"))
    if data.startswith("pr_once_"):
        return oc_mod.toggle_once(cid, uid, num("pr_once_"))
    if data.startswith("pr_dely_"):
        return oc_mod.delete_rule(cid, uid, num("pr_dely_"), True)
    if data.startswith("pr_del_"):
        return oc_mod.delete_rule(cid, uid, num("pr_del_"), False)
    if data.startswith("pr_trg_"):
        return oc_mod.pick_trigger(cid, uid, num("pr_trg_"))
    if data.startswith("prtg_"):
        t_, r_ = two("prtg_")
        return oc_mod.pick_trigger(cid, uid, r_, t_)
    if data.startswith("prn_"):
        k_, r_ = two("prn_")
        return oc_mod.start_rule_field(cid, uid, r_, k_, is_num=True)
    if data.startswith("prt_"):
        k_, r_ = two("prt_")
        return oc_mod.start_rule_field(cid, uid, r_, k_, is_num=False)

    # ═══════════════════════════════════════════════════
    # 📋 لاگ فعالیت (فارسی)
    # ═══════════════════════════════════════════════════
    if data == "lg_list":
        return alog_mod.show_logs(cid, uid, 0)
    if data == "lg_cats":
        return alog_mod.show_categories(cid, uid)
    if data == "lg_stats":
        return alog_mod.show_stats(cid, uid)
    if data == "lg_export":
        return alog_mod.export_logs(cid, uid)
    if data == "lg_cleany":
        return alog_mod.clean_logs(cid, uid, True)
    if data == "lg_clean":
        return alog_mod.clean_logs(cid, uid, False)
    if data.startswith("lg_adm_"):
        return alog_mod.show_logs(cid, uid, 0, "همه", num("lg_adm_", 0))
    if data.startswith("lg_c_"):
        _r = data[5:]
        _c, _, _p = _r.rpartition("_")
        return alog_mod.show_logs(cid, uid,
                                  int(_p) if _p.isdigit() else 0, _c or "همه")
    if data.startswith("lg_p_"):
        _r = data[5:]
        _p, _, _c = _r.partition("_")
        return alog_mod.show_logs(cid, uid,
                                  int(_p) if _p.isdigit() else 0, _c or "همه")

    # ═══════════════════════════════════════════════════
    # 💰 مالی و تراکنش‌ها
    # ═══════════════════════════════════════════════════
    if data == "fin_dash":
        return fin_mod.show_dashboard(cid, uid)
    if data == "fin_fees":
        return fin_mod.show_fees(cid, uid)
    if data == "fin_break":
        return fin_mod.show_breakdown(cid, uid)
    if data == "fin_period":
        return fin_mod.show_period(cid, uid)
    # ⚠️ قبل از fin_pending — هر دو با fin_p شروع می‌شوند
    if data.startswith("fin_per_"):
        return fin_mod.show_period(cid, uid, data[len("fin_per_"):])
    if data == "fin_events":
        return fin_mod.show_by_event(cid, uid)
    if data == "fin_forms":
        return fin_mod.show_by_form(cid, uid)
    if data == "fin_methods":
        return fin_mod.show_by_method(cid, uid)
    if data == "fin_pending":
        return fin_mod.show_pending(cid, uid)
    if data == "fin_byuser":
        return fin_mod.show_user_payments(cid, uid)
    if data == "fin_export":
        return fin_mod.export_finance(cid, uid)
    if data.startswith("fin_tx_"):
        _r = data[7:]
        _p, _, _f = _r.partition("_")
        return fin_mod.show_transactions(cid, uid,
                                         int(_p) if _p.isdigit() else 0,
                                         _f or "all")

    # ═══════════════════════════════════════════════════
    # 🔐 نقش و دسترسی ادمین
    # ═══════════════════════════════════════════════════
    if data.startswith("pm_view_"):
        return admin_mod.show_admin_perms(cid, uid, num("pm_view_"))
    if data.startswith("pm_roles_"):
        return admin_mod.show_role_picker(cid, uid, num("pm_roles_"))
    if data.startswith("pm_setr_"):
        _r, _t = two("pm_setr_")
        return admin_mod.set_admin_role(cid, uid, _t, _r)
    if data.startswith("pm_cats_"):
        return admin_mod.show_perm_cats(cid, uid, num("pm_cats_"))
    if data.startswith("pm_cat_"):
        _c, _t = two("pm_cat_")
        return admin_mod.show_perm_cat(cid, uid, _t, _c)
    if data.startswith("pm_tog_"):
        _k, _t = two("pm_tog_")
        return admin_mod.toggle_admin_perm(cid, uid, _t, _k)
    if data.startswith("pm_revoke_"):
        return admin_mod.revoke_admin_perms(cid, uid, num("pm_revoke_"))

    # ═══════════════════════════════════════════════════
    # 🏅 باشگاه: دستاورد، فروشگاه، رتبه‌بندی
    # ═══════════════════════════════════════════════════
    if data == "cl_my":
        return club_mod.show_my_achievements(cid, uid)
    if data == "cl_all":
        return club_mod.show_all_achievements(cid, uid)
    if data == "cl_shop":
        return club_mod.show_shop(cid, uid)
    if data == "cl_myredeem":
        return club_mod.show_my_redemptions(cid, uid)
    if data.startswith("cl_bd_"):
        return club_mod.show_leaderboard(cid, uid, data[6:])
    if data == "cl_board":
        return club_mod.show_leaderboard(cid, uid, "points")
    if data.startswith("cl_buyok_"):
        return club_mod.do_buy(cid, uid, num("cl_buyok_"))
    if data.startswith("cl_buy_"):
        return club_mod.confirm_buy(cid, uid, num("cl_buy_"))

    # ---- پنل ادمین باشگاه ----
    if data == "cl_panel":
        return club_mod.show_admin_panel(cid, uid)
    if data == "cl_reqs":
        return club_mod.show_requests(cid, uid)
    if data == "cl_adm_ach":
        return club_mod.show_admin_achievements(cid, uid)
    if data == "cl_adm_rw":
        return club_mod.show_admin_rewards(cid, uid)
    if data == "cl_settings":
        return club_mod.show_settings(cid, uid)
    if data == "cl_aadd":
        return club_mod.start_add(cid, uid, "a")
    if data == "cl_radd":
        return club_mod.start_add(cid, uid, "r")
    if data.startswith("cl_tog_"):
        return club_mod.toggle_flag(cid, uid, data[7:])
    if data.startswith("cl_ok_"):
        return club_mod.handle_request(cid, uid, num("cl_ok_"), True)
    if data.startswith("cl_rej_"):
        return club_mod.handle_request(cid, uid, num("cl_rej_"), False)
    if data.startswith("cl_av_"):
        return club_mod.view_achievement(cid, uid, num("cl_av_"))
    if data.startswith("cl_rv_"):
        return club_mod.view_reward(cid, uid, num("cl_rv_"))
    if data.startswith("cl_atg_"):
        return club_mod.toggle_item(cid, uid, "a", num("cl_atg_"))
    if data.startswith("cl_rtg_"):
        return club_mod.toggle_item(cid, uid, "r", num("cl_rtg_"))
    if data.startswith("cl_adely_"):
        return club_mod.delete_item(cid, uid, "a", num("cl_adely_"), True)
    if data.startswith("cl_rdely_"):
        return club_mod.delete_item(cid, uid, "r", num("cl_rdely_"), True)
    if data.startswith("cl_adel_"):
        return club_mod.delete_item(cid, uid, "a", num("cl_adel_"), False)
    if data.startswith("cl_rdel_"):
        return club_mod.delete_item(cid, uid, "r", num("cl_rdel_"), False)
    if data.startswith("cln_"):
        _f, _i = two("cln_")
        return club_mod.start_num_edit(cid, uid, "a", _i, _f)
    if data.startswith("clrn_"):
        _f, _i = two("clrn_")
        return club_mod.start_num_edit(cid, uid, "r", _i, _f)

    # ═══════════════════════════════════════════════════
    # 📱 تیکت پشتیبانی
    # ═══════════════════════════════════════════════════
    if data == "tk_my":
        return tk_mod.show_my_tickets(cid, uid)
    if data == "tk_new":
        return tk_mod.start_new(cid, uid)
    if data.startswith("tk_cat_"):
        return tk_mod.pick_category(cid, uid, data[7:])
    if data.startswith("tk_v_"):
        return tk_mod.view_ticket(cid, uid, num("tk_v_"))
    if data.startswith("tk_r_"):
        return tk_mod.start_reply(cid, uid, num("tk_r_"))
    if data.startswith("tk_s_"):
        _st, _i = two("tk_s_")
        return tk_mod.set_status(cid, uid, _i, _st)
    if data.startswith("tk_prs_"):
        _p, _i = two("tk_prs_")
        return tk_mod.show_priority(cid, uid, _i, _p)
    if data.startswith("tk_pr_"):
        return tk_mod.show_priority(cid, uid, num("tk_pr_"))
    if data.startswith("tk_rt_"):
        _v, _i = two("tk_rt_")
        return tk_mod.rate_ticket(cid, uid, _i, _v)
    if data.startswith("tk_rate_"):
        return tk_mod.rate_ticket(cid, uid, num("tk_rate_"))
    # ═══ 📥 فاز ۱۷-ج — صندوق دریافت ═══
    if data == "ib_list":
        return tk_mod.show_inbox(cid, uid, 0, 0)
    if data.startswith("ib_p_"):
        _r = data[5:]
        _pg, _, _un = _r.partition("_")
        return tk_mod.show_inbox(cid, uid,
                                 int(_pg) if _pg.isdigit() else 0,
                                 1 if _un == "1" else 0)
    if data.startswith("ib_v_"):
        return tk_mod.view_inbox_msg(cid, uid, num("ib_v_"))
    if data.startswith("ib_r_"):
        return tk_mod.start_inbox_reply(cid, uid, num("ib_r_"))
    if data.startswith("ib_d_"):
        return tk_mod.delete_inbox_msg(cid, uid, num("ib_d_"))
    if data == "ib_allread":
        return tk_mod.mark_all_read(cid, uid)

    # ═══ ⚙️ پارامترهای پروفایل ═══
    if data == "pf_params":
        return admin_mod.show_profile_params(cid, uid)
    if data == "admin_profile_params":
        return admin_mod.show_profile_params(cid, uid)
    if data == "pf_reset":
        return admin_mod.reset_profile_params(cid, uid)
    # ➕ فاز ۱۸-الف — افزودن/حذف پارامتر سفارشی
    # ✏️ فاز ۳۸ — ویرایش متن پرسش و افزودن پارامتر دلخواه
    #    ⚠️ ترتیب مهم است: «pfnm_» باید قبل از «pfnew_» بیاید
    #       چون هر دو با «pfn» شروع می‌شوند.
    if data.startswith("pfnm_"):
        return admin_mod.start_new_media(cid, uid, data[len("pfnm_"):])
    if data.startswith("pfnew_"):
        return admin_mod.start_new_param(cid, uid, data[len("pfnew_"):])
    if data.startswith("pfqr_"):
        return admin_mod.reset_param_text(cid, uid, data[len("pfqr_"):])
    if data.startswith("pfq_"):
        return admin_mod.start_param_text(cid, uid, data[len("pfq_"):])
    if data.startswith("pfv_"):
        return admin_mod.show_param_edit(cid, uid, data[len("pfv_"):])
    if data == "pfadd":
        return admin_mod.show_add_param(cid, uid)
    if data == "pfcat":
        return admin_mod.show_add_param(cid, uid, "_list")
    if data.startswith("pfcat_"):
        return admin_mod.show_add_param(cid, uid, data[len("pfcat_"):])
    if data.startswith("pfadd_"):
        return admin_mod.add_param(cid, uid, data[len("pfadd_"):])
    if data.startswith("pfdel_"):
        return admin_mod.del_param(cid, uid, data[len("pfdel_"):])
    if data.startswith("pfo_"):
        return admin_mod.toggle_profile_field(cid, uid, data[4:])
    if data.startswith("pfr_"):
        return admin_mod.toggle_profile_required(cid, uid, data[4:])

    if data == "tk_admin":
        return tk_mod.show_admin_tickets(cid, uid, 0, "open")
    if data == "tk_stats":
        return tk_mod.show_stats(cid, uid)
    if data.startswith("tk_p_"):
        _r = data[5:]
        _pg, _, _fl = _r.partition("_")
        return tk_mod.show_admin_tickets(cid, uid,
                                         int(_pg) if _pg.isdigit() else 0,
                                         _fl or "open")

    # ---- Import ----
    if data == "import_cancel":
        clear_state(uid)
        return send(cid, "❌ لغو شد", kb_remove())
    if data == "import_start":
        return imp_mod.run_import(cid, uid, update_existing=False)
    if data == "import_update":
        return imp_mod.run_import(cid, uid, update_existing=True)

    log(f"⚠️ callback ناشناخته: {data}")
    if get_setting("debug_mode", "0") == "1":
        send(cid, f"🐞 دکمه بدون هندلر:\n{data}")


# ==================== لایک خودکار ====================
def auto_like(msg, uid):
    """
    👍 روی هر پیام کاربر عادی (نه ادمین) لایک بگذار.
    طبق درخواست: «از این به بعد کاربر نه ادمین، فقط کاربر هر پیامی داد لایک بزن»
    """
    if not AUTO_REACT_ENABLED:
        return
    if not AUTO_REACT_ADMINS and is_admin(uid):
        return
    mid = msg.get("message_id")
    cid = (msg.get("chat") or {}).get("id")
    if not mid or not cid:
        return
    try:
        set_reaction(cid, mid, AUTO_REACT_EMOJI)
    except Exception as e:
        log(f"⚠️ ری‌اکشن: {e}")


# ==================== MESSAGE ROUTER ====================
def process_message(msg):
    user = msg.get("from") or {}
    uid = user.get("id")
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    text = (msg.get("text") or "").strip()

    if uid is None or cid is None:
        return

    chat_type = chat.get("type", "private")

    if text.startswith("/chatid"):
        return send(cid, (
            f"🆔 اطلاعات این چت:\n\n"
            f"chat_id: {cid}\n"
            f"نوع: {chat_type}\n"
            f"عنوان: {chat.get('title') or '-'}\n\n"
            f"💡 این آیدی را در «عضویت اجباری» ثبت کنید."
        ))

    if chat_type != "private":
        return

    log_text = "[shared form input]" if get_state_name(uid) == shared_form_flow_mod.STATE else (
        text[:60] if text else "[media]"
    )
    log(f"📨 {user.get('first_name')} ({uid}): {log_text}")

    # پیام متنی: چیزی برای ویرایش نیست → پیام جدید
    clear_context(cid)
    # ⚠️ ولی نقش کاربر باید ست شود وگرنه kb_remove() منوی اشتباه می‌دهد
    _adm, _full = _menu_flags(uid)
    set_context(cid, None, from_callback=False,
                is_admin=_adm, is_full=_full)

    if uid != SUPER_ADMIN_ID and is_blocked(uid):
        return send(cid, get_setting("msg_blocked", "🚫 دسترسی شما مسدود شده است."))

    # حالت‌های رد محلیِ قدیمی نباید به هندلرهای SQLite برسند.
    legacy_review_state = get_state_name(uid)
    if legacy_review_state == profile_mod.STATE_REJECT:
        clear_state(uid)
        send(cid, "مسیر رد قدیمی غیرفعال است؛ هیچ تغییری در SQLite ثبت نشد. کارتابل مشترک باز می‌شود.", kb_remove())
        return _show_shared_review_inbox(cid, uid, "profile_review")
    if legacy_review_state == "rcp_reject":
        clear_state(uid)
        send(cid, "مسیر رد فیش قدیمی غیرفعال است؛ هیچ تغییری در SQLite ثبت نشد. کارتابل مشترک باز می‌شود.", kb_remove())
        return _show_shared_review_inbox(cid, uid, "receipt_review")

    # 👍 لایک خودکار روی پیام کاربران عادی
    auto_like(msg, uid)

    # ---- پرداخت موفق ----
    if "successful_payment" in msg:
        return ev_mod.handle_successful_payment(msg)

    if "contact" in msg:
        active_state = get_state_name(uid)
        if active_state == shared_form_flow_mod.STATE:
            contact = msg.get("contact") or {}
            contact_owner = contact.get("user_id")
            if contact_owner not in (None, uid):
                return send(cid, "لطفاً شمارهٔ خودتان را ارسال کنید یا آن را به‌صورت متن بنویسید.")
            return shared_form_flow_mod.handle_input(cid, uid, str(contact.get("phone_number") or ""))
        # اگر وسط پر کردن فرم محلی قدیمی است و سوال «موبایل» پرسیده شده
        if active_state == fill_mod.STATE_FILL:
            if fill_mod.handle_contact(msg):
                return
        return handle_contact(msg)

    state_name = get_state_name(uid)

    # موقعیت مکانی (حضور و غیاب / فرم)
    if "location" in msg:
        if state_name == shared_form_flow_mod.STATE:
            return shared_form_flow_mod.handle_location(cid, uid, msg.get("location") or {})
        if state_name == att_mod.STATE_ATT_LOC:
            return att_mod.handle_location(msg)
        if state_name == att_mod.STATE_ATT_SETLOC:
            return att_mod.handle_session_location(msg)
        if state_name == fill_mod.STATE_FILL:
            return fill_mod.handle_location(msg)
        return send(cid, "💡 برای ثبت حضور، از «✋ حضور و غیاب» اقدام کنید.")

    if "photo" in msg:
        if state_name == shared_form_flow_mod.STATE:
            return send(cid, "این پرسش پیوست نمی‌پذیرد؛ متن یا گزینه‌های همین پرسش را بفرستید.")
        if state_name == profile_mod.STATE_PHOTO:
            return profile_mod.handle_photo(msg)
        # 📸 فاز ۳۸ — عکس در جریان تکمیل پروفایل
        #    (مرحلهٔ رسانه‌ای؛ عکس پروفایل یا پارامتر سفارشی)
        if state_name == profile_mod.STATE_FORM:
            if profile_mod.handle_form_photo(msg):
                return
            return send(cid, "💡 در این مرحله متن بنویسید،"
                             " یا با «رد کردن» جلو بروید.")
        if state_name == ev_mod.STATE_EV_CREATE:
            return ev_mod.handle_create_input(msg)
        if state_name == pay_mod.STATE_RECEIPT:
            return pay_mod.handle_receipt(msg)
        if state_name == att_mod.STATE_ATT_EXCUSE:
            return att_mod.handle_excuse(msg)
        if state_name == admin_mod.STATE_BROADCAST:
            return admin_mod.handle_broadcast_text(msg)
        if state_name == fb_mod.STATE_FB_EDIT:
            if str(get_state_data(uid).get("key") or "").startswith("media_"):
                return fb_mod.handle_media_photo(msg)
        if state_name == fb_mod.STATE_FB_FIELD:
            if get_state_data(uid).get("key") == "media":
                return ff_mod.handle_field_photo(msg)
        if state_name == fill_mod.STATE_FILL:
            return fill_mod.handle_media(msg)
        if state_name == ads_mod.STATE_AD_MEDIA:
            return ads_mod.handle_media(msg)
        if state_name == cg_mod.STATE_CT_ASSET:
            return cg_mod.handle_asset(msg)
        if state_name == ftk_mod.STATE_TK_ASSET:
            return ftk_mod.handle_asset(msg)
        if state_name == cg_mod.STATE_CT_UPLOAD:
            return cg_mod.handle_upload(msg)
        if state_name == tk_mod.STATE_TK_NEW:
            return tk_mod.handle_new_photo(msg)
        return send(cid, "💡 برای تغییر عکس پروفایل، از «👤 پروفایل من» اقدام کنید.")

    if "document" in msg:
        if state_name == shared_form_flow_mod.STATE:
            return send(cid, "این پرسش پیوست نمی‌پذیرد؛ متن یا گزینه‌های همین پرسش را بفرستید.")
        # 📥 STATE_CONFIRM (confirm_import) با دکمه ادامه می‌یابد نه متن
        #    (import_start / import_update / import_cancel)
        #    اگر کاربر متن بفرستد، fallback پایین راهنمایی‌اش می‌کند.
        if state_name == imp_mod.STATE_CONFIRM:
            if text == BTN_BACK:
                clear_state(uid)
                return admin_mod.show_users_menu(cid, uid)
            return send(cid, (
                "💡 لطفاً یکی از دکمه‌های بالا را بزنید:\n"
                "«فقط ثبت جدیدها» یا «ثبت + به‌روزرسانی» یا «انصراف»"
            ))
        if state_name == ads_mod.STATE_AD_MEDIA:
            return ads_mod.handle_media(msg)
        if state_name == cg_mod.STATE_CT_ASSET:
            return cg_mod.handle_asset(msg)
        if state_name == ftk_mod.STATE_TK_ASSET:
            return ftk_mod.handle_asset(msg)
        if state_name == cg_mod.STATE_CT_UPLOAD:
            return cg_mod.handle_upload(msg)
        # 🏛️ فاز ۳۶ — اکسل گیرندگان مرکز صدور
        if state_name == "cc_excel":
            return cc_mod.handle_document(msg)
        # 🎟️ فاز ۳۲ — اکسل صدور گروهی (سازگاری عقب‌رو)
        if state_name == "cb_wait_file":
            return cb_mod.handle_document(msg)
        if state_name == imp_mod.STATE_WAIT_FILE:
            return imp_mod.handle_import_file(msg)
        if state_name == fill_mod.STATE_FILL:
            return fill_mod.handle_media(msg)
        return send(cid, "💡 برای ورود اطلاعات از اکسل، ابتدا /import را بزنید.")

    if ("video" in msg or "voice" in msg or "audio" in msg):
        if state_name == shared_form_flow_mod.STATE:
            return send(cid, "این پرسش پیوست نمی‌پذیرد؛ متن یا گزینه‌های همین پرسش را بفرستید.")
        if state_name == fill_mod.STATE_FILL:
            return fill_mod.handle_media(msg)

    # ═══════════════════════════════════════════════════
    # 🔴 دستورات فرار — قبل از هر state چک می‌شوند
    # کاربر هرگز نباید در هیچ مرحله‌ای گیر بیفتد
    # ═══════════════════════════════════════════════════
    ESCAPE = {"/start", "/menu", "/cancel", "/لغو", "/home", "/خانه",
              "🏠 منوی اصلی", "🔙 منوی اصلی", "منوی اصلی", "لغو", "انصراف"}

    if text in ESCAPE or text.startswith("/start"):
        if state_name == shared_form_flow_mod.STATE:
            if text in {"/cancel", "/لغو", "لغو", "انصراف"}:
                return shared_form_flow_mod.cancel(cid, uid)
            shared_form_flow_mod.abandon(uid)
        clear_state(uid)
        clear_context(cid)
        if text.startswith("/start"):
            return handle_start(msg)
        # ⚠️ پیام اضافه «برگشتید» حذف شد — منوی اصلی خودش کافی است
        # force_kb: کاربر صراحتاً منو خواسته، پس حتماً کیبورد را بده
        return show_main_menu(cid, user, force_kb=True)

    if (state_name == shared_form_flow_mod.STATE and text.startswith("/")
            and text not in {"/skip"}):
        shared_form_flow_mod.abandon(uid)
        state_name = None

    # ═══════════════════════════════════════════════════
    # 🎯 دکمه‌های منوی اصلی (پایین صفحه)
    # این‌ها همیشه کار می‌کنند — حتی وسط یک مرحله
    # ═══════════════════════════════════════════════════
    if text in MAIN_MENU_BUTTONS:
        # اگر وسط فرم/ویزارد بود، از آن خارج شو
        if state_name and text != BTN_HOME:
            if state_name == shared_form_flow_mod.STATE:
                shared_form_flow_mod.abandon(uid)
            clear_state(uid)

        _adm2, _full2 = _menu_flags(uid)

        # ═══ دکمه‌های منوی مدیریتی (فاز ۱۳) ═══
        if text == BTN_ADMIN:
            if not is_admin(uid):
                return send(cid, "❌ دسترسی ندارید")
            # اگر ادمین کامل در «نمای کاربر» بود، برگردانش
            if in_user_view(uid):
                set_user_view(uid, False)
                show_main_menu(cid, user, force_kb=True)
            return admin_mod.show_admin_panel(cid, uid)

        if text == BTN_USER_VIEW:
            if not is_admin(uid):
                return send(cid, "❌ دسترسی ندارید")
            set_user_view(uid, True)
            return show_main_menu(cid, user, force_kb=True, as_user=True)

        if _full2:
            # 🎉 «رویدادها» برای ادمین کامل = پنل ادمینِ رویدادها
            if text == BTN_EVENTS:
                return ev_mod.show_admin_events(cid, uid, 0)
            if text == BTN_ADM_USERS:
                return admin_mod.show_users_menu(cid, uid)
            if text == BTN_ADM_FORMS:
                return fb_mod.show_panel(cid, uid)
            if text == BTN_ADM_REPORTS:
                return shared_reports_mod.show_dashboard(cid, uid)
            if text == BTN_ADM_SETTINGS:
                return set_mod.show_settings(cid, uid)

        # ═══ دکمه‌های منوی کاربر ═══
        if text == BTN_EVENTS:
            return ev_mod.show_user_events(cid, uid, 0)
        if text == BTN_FORMS:
            return fill_mod.show_public_forms(cid, uid, 0)
        if text == BTN_PROFILE:
            if not get_user(uid):
                return send(cid, "⚠️ ابتدا /start را بزنید")
            return profile_mod.show_profile(cid, uid)
        if text == BTN_ATTEND:
            return att_mod.user_attendance_menu(cid, uid)
        if text == BTN_INVITE:
            return set_mod.show_referral(cid, uid)
        if text == BTN_NOTIF:
            return set_mod.show_notifications(cid, uid)
        if text == BTN_SUPPORT:
            return set_mod.show_support(cid, uid)

        # دکمه‌های مدیریتی که کاربر عادی نباید ببیند
        # (اگر کیبورد قدیمی روی گوشی مانده باشد)
        if text in (BTN_ADM_USERS, BTN_ADM_FORMS,
                    BTN_ADM_REPORTS, BTN_ADM_SETTINGS):
            if not is_admin(uid):
                return send(cid, "❌ دسترسی ندارید")
            if text == BTN_ADM_USERS:
                return admin_mod.show_users_menu(cid, uid)
            if text == BTN_ADM_FORMS:
                return fb_mod.show_panel(cid, uid)
            if text == BTN_ADM_REPORTS:
                return shared_reports_mod.show_dashboard(cid, uid)
            return set_mod.show_settings(cid, uid)

    # ---- دستورات ----
    if text == "/import":
        return imp_mod.handle_import_command(msg)
    if text == "/me":
        if not get_user(uid):
            return send(cid, "⚠️ ابتدا /start را بزنید")
        return profile_mod.show_profile(cid, uid)
    if text == "/id":
        return send(cid, f"🆔 آیدی عددی شما در بله:\n{uid}")
    if text == "/events":
        return ev_mod.show_user_events(cid, uid, 0)
    if text == "/attendance":
        return att_mod.user_attendance_menu(cid, uid)
    if text == "/admin":
        if is_admin(uid):
            return admin_mod.show_admin_panel(cid, uid)
        return send(cid, "❌ دسترسی ندارید")
    if text == "/settings":
        if is_admin(uid):
            return set_mod.show_settings(cid, uid)
        return send(cid, "❌ دسترسی ندارید")
    if text.startswith("/debug"):
        if not is_admin(uid):
            return send(cid, "❌ دسترسی ندارید")
        from database import set_setting
        arg = text.replace("/debug", "").strip().lower()
        if arg in ("on", "1", "روشن"):
            set_setting("debug_mode", "1", "حالت عیب‌یابی", "system", uid)
            return send(cid, (
                "🐞 حالت عیب‌یابی روشن شد\n\n"
                "از این به بعد:\n"
                "• دکمه‌های بدون هندلر گزارش می‌شوند\n"
                "• خطاهای API نمایش داده می‌شوند\n\n"
                "خاموش کردن: /debug off"
            ))
        if arg in ("off", "0", "خاموش"):
            set_setting("debug_mode", "0", "حالت عیب‌یابی", "system", uid)
            return send(cid, "✅ حالت عیب‌یابی خاموش شد")
        cur = get_setting("debug_mode", "0")
        return send(cid, (
            f"🐞 حالت عیب‌یابی: {'روشن' if cur == '1' else 'خاموش'}\n\n"
            f"/debug on — روشن\n/debug off — خاموش"
        ))

    if text == "/status":
        if not is_admin(uid):
            return send(cid, "❌ دسترسی ندارید")
        import guard as _g
        from bale_api import _unsupported as _uns
        fp, nf, sz = _g.code_fingerprint()
        up = "—"
        if STATS.get("started"):
            secs = int(time.time() - STATS["started"])
            h, m = secs // 3600, (secs % 3600) // 60
            up = f"{h} ساعت {m} دقیقه" if h else f"{m} دقیقه"
        dis = "، ".join(_uns.keys()) if _uns else "هیچ"
        return send(cid, (
            f"📊 وضعیت ربات\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🔖 امضای کد: {fp}\n"
            f"📦 نسخه: {VERSION}\n"
            f"⏱️ آپتایم: {up}\n\n"
            f"📥 آپدیت‌های دریافتی: {STATS['updates']}\n"
            f"├── 📨 پیام: {STATS['messages']}\n"
            f"├── 🔘 دکمه: {STATS['callbacks']}\n"
            f"└── ❌ خطا: {STATS['errors']}\n\n"
            f"🆔 آخرین update_id: {STATS['last_update_id']}\n"
            f"🚫 متدهای غیرفعال: {dis}\n\n"
            f"💡 اگر «آپدیت‌های دریافتی» بالا نمی‌رود،\n"
            f"   یعنی ربات پیام‌ها را دریافت نمی‌کند\n"
            f"   (احتمالاً نمونه دیگری در حال اجراست)"
        ))

    if text == "/paytest":
        if is_admin(uid):
            return set_mod.payment_test_menu(cid, uid)
        return send(cid, "❌ دسترسی ندارید")

    if text == "/testotp":
        if is_admin(uid):
            return set_mod.show_otp_settings(cid, uid)
        return send(cid, "❌ دسترسی ندارید")
    if text == "/help":
        return send(cid, (
            f"📖 راهنمای {brand()}\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"/start — شروع و منوی اصلی\n"
            f"/events — رویدادهای فعال\n"
            f"/me — مشاهده پروفایل\n"
            f"/id — آیدی عددی شما\n"
            f"/cancel — لغو عملیات فعلی\n"
            f"/help — همین راهنما\n\n"
            f"👨‍💼 ادمین:\n"
            f"/admin — پنل ادمین\n"
            f"/settings — تنظیمات\n"
            f"/testotp — تست رمز یکبار مصرف\n"
            f"/import — ورود کاربران از اکسل\n"
            f"/chatid — آیدی گروه (داخل گروه بزنید)"
        ))

    # ---- state ها ----
    if state_name:
        if state_name == "waiting_phone_otp":
            return handle_phone_otp(msg)
        if state_name == "waiting_otp":
            return handle_otp(msg)
        if state_name == profile_mod.STATE_FORM:
            return profile_mod.handle_form_input(msg)
        if state_name == shared_workflows_mod.STATE_REJECT:
            return shared_workflows_mod.handle_reject_reason(msg)
        if state_name == profile_mod.STATE_REJECT:
            clear_state(uid)
            send(cid, "مسیر رد قدیمی غیرفعال است؛ کارتابل مشترک باز می‌شود.", kb_remove())
            return _show_shared_review_inbox(cid, uid, "profile_review")
        # ✏️ فاز ۳۸ — ویرایش متن پرسش / افزودن پارامتر
        if state_name in (admin_mod.STATE_PF_TEXT,
                          admin_mod.STATE_PF_NEW):
            return admin_mod.handle_param_text(msg)
        if state_name == admin_mod.STATE_SEARCH:
            return admin_mod.handle_search(msg)
        if state_name == admin_mod.STATE_ADD_CHANNEL:
            return admin_mod.handle_add_channel(msg)
        if state_name == admin_mod.STATE_CH_LINK:
            return admin_mod.handle_channel_link(msg)
        if state_name == admin_mod.STATE_BROADCAST:
            return admin_mod.handle_broadcast_text(msg)
        if state_name == ev_mod.STATE_EV_CREATE:
            return ev_mod.handle_create_input(msg)
        if state_name == ev_mod.STATE_EV_ADV:
            return ev_mod.handle_adv_input(msg)
        if state_name == ev_mod.STATE_EV_PWD:
            return ev_mod.handle_password(msg)
        if state_name == ev_mod.STATE_EV_DISC:
            return ev_mod.handle_add_discount(msg)
        if state_name == ev_mod.STATE_EV_APPLY_DISC:
            return ev_mod.handle_apply_discount(msg)
        if state_name == set_mod.STATE_EDIT_TEXT:
            return set_mod.handle_edit_text(msg)
        if state_name == set_mod.STATE_TEST_OTP:
            return set_mod.handle_otp_test(msg)
        if state_name == set_mod.STATE_INQUIRE:
            return set_mod.handle_inquire(msg)
        if state_name == admin_mod.STATE_ADD_USER:
            return admin_mod.handle_add_user(msg)
        if state_name == admin_mod.STATE_EDIT_PROFILE:
            return admin_mod.handle_edit_profile(msg)
        if state_name == tk_mod.STATE_INBOX_REPLY:
            return tk_mod.handle_inbox_reply(msg)
        if state_name == pay_mod.STATE_CARD_ADD:
            return pay_mod.handle_add_card(msg)
        if state_name == pay_mod.STATE_GW_ADD:
            return pay_mod.handle_add_gateway(msg)
        if state_name == pay_mod.STATE_TEXT_EDIT:
            return pay_mod.handle_edit_payment_text(msg)
        if state_name == pay_mod.STATE_PAY_NUM:
            return pay_mod.handle_pay_num(msg)
        if state_name == pay_mod.STATE_PAY_FEE:
            return pay_mod.handle_fee_input(msg)
        if state_name == ads_mod.STATE_AD_NEW:
            return ads_mod.handle_new(msg)
        if state_name == ads_mod.STATE_AD_EDIT:
            _d = get_state_data(uid)
            if _d.get("setting"):
                return ads_mod.handle_setting(msg)
            if _d.get("field") == "_when":
                return ads_mod.handle_when(msg)
            return ads_mod.handle_edit(msg)
        if state_name == ads_mod.STATE_AD_MEDIA:
            return ads_mod.handle_media(msg)
        if state_name == cg_mod.STATE_CT_SET:
            return cg_mod.handle_setting(msg)
        if state_name == ads_mod.STATE_AD_MEDIA:
            return ads_mod.handle_media(msg)
        if state_name == cg_mod.STATE_CT_ASSET:
            return cg_mod.handle_asset(msg)
        if state_name == ftk_mod.STATE_TK_ASSET:
            return ftk_mod.handle_asset(msg)
        if state_name == cg_mod.STATE_CT_NAME:
            return cg_mod.handle_name(msg)
        if state_name == cg_mod.STATE_CT_BOX:
            return cg_mod.handle_box(msg)
        if state_name == cg_mod.STATE_CT_UPLOAD:
            return cg_mod.handle_upload(msg)
        if state_name == ab_mod.STATE_AB_TEXT:
            return ab_mod.handle_edit_text(msg)
        if state_name == ab_mod.STATE_AB_IDENT:
            return ab_mod.handle_identity(msg)
        if state_name == ab_mod.STATE_AB_LINK:
            return ab_mod.handle_add_link(msg)
        if state_name == ab_mod.STATE_AB_PERSON:
            return ab_mod.handle_add_person(msg)
        if state_name == pp_mod.STATE_PP_NEW:
            return pp_mod.handle_new(msg)
        if state_name == pp_mod.STATE_PP_EDIT:
            _d = get_state_data(uid)
            if _d.get("setting"):
                return pp_mod.handle_num_setting(msg)
            return pp_mod.handle_edit(msg)
        if state_name == fb_mod.STATE_FB_FEAT:
            return fb_mod.handle_feature_input(msg)
        if state_name == fb_mod.STATE_FB_CODE:
            return fb_mod.handle_access_code(msg)
        if state_name == pl_mod.STATE_PL_NEW:
            return pl_mod.handle_wizard(msg)
        if state_name == pl_mod.STATE_PL_EDIT:
            return pl_mod.handle_edit(msg)
        if state_name == pl_mod.STATE_PL_PAY:
            return pl_mod.handle_open_amount(msg)
        if state_name == lt_mod.STATE_LT_ADD:
            return lt_mod.handle_add_prize(msg)
        if state_name == lt_mod.STATE_LT_NUM:
            return lt_mod.handle_prize_num(msg)
        if state_name == lt_mod.STATE_LT_DATE:
            return lt_mod.handle_date(msg)
        if state_name == ev_mod.STATE_EV_NUM:
            return ev_mod.handle_num_edit(msg)
        if state_name == ev_mod.STATE_EV_QUICK:
            # این state فقط انتخاب فیلدها را نگه می‌دارد — ورودی متنی ندارد
            return send(cid, "👆 لطفاً از دکمه‌های بالا فیلدها را انتخاب کنید")
        if state_name == fill_mod.STATE_FF_MSG:
            return fill_mod.handle_contact_msg(msg)
        if state_name == att_mod.STATE_ATT_EXCUSE:
            return att_mod.handle_excuse(msg)
        if state_name == pay_mod.STATE_RECEIPT:
            return pay_mod.handle_receipt(msg)
        if state_name in (pay_mod.STATE_PICK_METHOD,
                          pay_mod.STATE_POINTS_CONFIRM):
            return send(cid, "👆 لطفاً یکی از دکمه‌های بالا را بزنید")
        if state_name == "rcp_reject":
            clear_state(uid)
            send(cid, "مسیر رد فیش قدیمی غیرفعال است؛ کارتابل مشترک باز می‌شود.", kb_remove())
            return _show_shared_review_inbox(cid, uid, "receipt_review")
        if state_name == att_mod.STATE_ATT_CODE:
            return att_mod.handle_code(msg)
        if state_name == att_mod.STATE_ATT_LOC:
            return att_mod.handle_location(msg)
        if state_name == att_mod.STATE_ATT_SETLOC:
            return att_mod.handle_session_location(msg)
        if state_name == att_mod.STATE_ATT_FIELD:
            return att_mod.handle_field(msg)
        if state_name == ci_mod.STATE_CI_PARAM:
            return ci_mod.handle_param(msg)
        if state_name == inf_mod.STATE_INFRA:
            return inf_mod.handle_edit(msg)
        if state_name == ftk_mod.STATE_TK_SET:
            return ftk_mod.handle_edit(msg)
        if state_name == ftk_mod.STATE_TK_ASSET:
            return ftk_mod.handle_asset(msg)
        if state_name == att_mod.STATE_CERT_EDIT:
            return att_mod.handle_cert_edit(msg)
        if state_name == "ev_code":
            if text == BTN_BACK:
                clear_state(uid)
                return ev_mod.show_user_events(cid, uid, 0)
            return ev_mod.register_by_code(cid, uid, text)
        if state_name == "contact_admin":
            if text == BTN_BACK:
                clear_state(uid)
                return set_mod.show_support(cid, uid)
            return forward_to_admins(cid, uid, text)
        if state_name == profile_mod.STATE_PREVIEW:
            if text == BTN_BACK:
                clear_state(uid)
                return show_main_menu(cid, user)
            return send(cid, "💡 لطفاً از دکمه‌های بالا استفاده کنید")
        if state_name == profile_mod.STATE_PHOTO:
            if text == BTN_BACK:
                clear_state(uid)
                return profile_mod.show_profile(cid, uid)
            return send(cid, "📸 لطفاً یک عکس ارسال کنید یا «🔙 بازگشت» را بزنید")
        if state_name == imp_mod.STATE_WAIT_FILE:
            if text == BTN_BACK:
                clear_state(uid)
                return admin_mod.show_admin_panel(cid, uid)
            return send(cid, "📎 لطفاً فایل اکسل را ارسال کنید")

        # ---- فرم‌ساز (ادمین) ----
        if state_name == fb_mod.STATE_FB_CREATE:
            return fb_mod.handle_create_input(msg)
        if state_name == fb_mod.STATE_FB_SEARCH:
            return fb_mod.handle_search(msg)
        if state_name == fb_mod.STATE_FB_TEXT:
            return fb_mod.handle_edit_text(msg)
        if state_name == fb_mod.STATE_FB_ADV:
            return fb_mod.handle_adv_input(msg)
        if state_name == fb_mod.STATE_FB_FIELD:
            return ff_mod.handle_field_input(msg)
        if state_name == fb_mod.STATE_FB_OPTION:
            return ff_mod.handle_option_input(msg)
        if state_name == fb_mod.STATE_FB_EDIT:
            key = get_state_data(uid).get("key") or ""
            if key == "price":
                return fb_mod.handle_price(msg)
            if key == "add_admin":
                return fb_mod.handle_add_form_admin(msg)
            if key == "add_tag":
                return fb_mod.handle_add_tag(msg)
            if key in ("resp_note", "resp_msg"):
                return frep_mod.handle_resp_input(msg)
            if key.startswith("media_"):
                return send(cid, "🖼️ لطفاً یک عکس ارسال کنید یا «🔙 بازگشت» را بزنید")
            return fb_mod.handle_edit_info(msg)

        # ---- 🎓 فاز ۳۲: گواهینامهٔ رویداد و صدور گروهی ----
        if state_name.startswith("evc_"):
            if evc_mod.handle_text(msg):
                return
        # 🔴 باگ رفع‌شده (فاز ۳۹) — «اسم طرح رو که میزنم جلو نمیره»:
        #    هندلر مرکز صدور فقط داخل شرط `startswith("cb_")`
        #    صدا زده می‌شد، ولی state های مرکز با «cc_» شروع
        #    می‌شوند (cc_title, cc_param, …). پس هیچ‌وقت اجرا
        #    نمی‌شد و ورودی متنی کاربر بی‌پاسخ می‌ماند.
        if state_name.startswith("cc_"):
            if cc_mod.handle_text(msg):
                return
        if state_name.startswith("cb_"):
            if cb_mod.handle_text(msg):
                return
        if state_name.startswith("ao_"):
            if aa_mod.handle_text(msg):
                return
        if state_name == "cv_edoc":
            if cv_mod.handle_admin_text(msg):
                return
        if state_name.startswith("cv_"):
            if cv_mod.handle_text(msg):
                return

        # ---- فرم گفتگومحور پایگاه مشترک ----
        if state_name == shared_form_flow_mod.STATE:
            return shared_form_flow_mod.handle_message(cid, uid, msg)

        # ---- پر کردن فرم محلی قدیمی ----
        if state_name == fill_mod.STATE_FILL:
            return fill_mod.handle_text(msg)

        # ---- مناسبت‌ها ----
        if state_name == club_mod.STATE_CLUB_ADD:
            return club_mod.handle_add(msg)
        if state_name == club_mod.STATE_CLUB_EDIT:
            return club_mod.handle_num_edit(msg)
        if state_name == tk_mod.STATE_TK_NEW:
            return tk_mod.handle_new(msg)
        if state_name == tk_mod.STATE_TK_REPLY:
            return tk_mod.handle_reply(msg)
        if state_name == "fin_search":
            return fin_mod.handle_search(msg)
        if state_name == oc_mod.STATE_OC_ADD:
            return oc_mod.handle_add(msg)
        if state_name == oc_mod.STATE_OC_EDIT:
            k = get_state_data(uid).get("key") or ""
            if k == "bpoints":
                return oc_mod.handle_bpoints(msg)
            if k == "text":
                return oc_mod.handle_edit_text(msg)
            return oc_mod.handle_edit(msg)

    if text == BTN_BACK:
        clear_state(uid)
        return show_main_menu(cid, user)

    db_user = get_user(uid)
    if uid != SUPER_ADMIN_ID and (not db_user or not db_user.get("is_authenticated")):
        return send(cid, "⚠️ ابتدا /start را بزنید و احراز هویت کنید")

    send(cid, "💬 لطفاً از دکمه‌های منو استفاده کنید.\n\n/start")


def forward_to_admins(cid, uid, text):
    """ارسال پیام کاربر به ادمین‌ها"""
    clear_state(uid)
    u = get_user(uid)
    nm = f"{(u or {}).get('first_name') or ''} {(u or {}).get('last_name') or ''}".strip()
    body = (
        f"💬 پیام از کاربر\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"👤 {nm or '-'}\n"
        f"📱 {(u or {}).get('mobile') or '-'}\n"
        f"🆔 {uid}\n\n"
        f"📄 پیام:\n{text[:1500]}"
    )
    rows = db_execute(
        "SELECT DISTINCT bale_user_id FROM users WHERE is_admin=1 AND bale_user_id IS NOT NULL",
        fetch="all") or []
    ids = {r["bale_user_id"] for r in rows if r.get("bale_user_id")}
    if SUPER_ADMIN_ID:
        ids.add(SUPER_ADMIN_ID)
    # 📥 فاز ۱۷-ج — ذخیره در صندوق دریافت (قبلاً فقط فوروارد می‌شد)
    try:
        tk_mod.save_inbox(uid, text)
    except Exception as e:
        log(f"⚠️ ذخیره صندوق: {e}")

    for aid in ids:
        send(aid, body)
    send(cid, "✅ پیام شما دریافت شد 💚\n\n"
              "به‌زودی پاسخ می‌گیرید.", kb_remove())
    log_action(uid, "contact_admin")


# ==================== MAIN LOOP ====================
STATS = {"updates": 0, "messages": 0, "callbacks": 0, "errors": 0,
         "last_update_id": 0, "started": None}


def process_update(update):
    STATS["updates"] += 1
    STATS["last_update_id"] = update.get("update_id", 0)
    if "message" in update:
        STATS["messages"] += 1
    elif "callback_query" in update:
        STATS["callbacks"] += 1
    try:
        if "message" in update:
            process_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
        elif "pre_checkout_query" in update:
            # ⚠️ باید ظرف ۱۰ ثانیه پاسخ داده شود
            ev_mod.handle_pre_checkout(update["pre_checkout_query"])
        elif "edited_message" in update:
            pass
    except Exception as e:
        STATS["errors"] += 1
        log(f"❌ خطا در پردازش آپدیت: {e}")
        log(traceback.format_exc()[:900])
        try:
            src = (update.get("message")
                   or (update.get("callback_query") or {}).get("message") or {})
            cid = (src.get("chat") or {}).get("id")
            if cid:
                send(cid, get_setting("msg_error", "⚠️ خطایی رخ داد. دوباره تلاش کنید."))
        except Exception:
            pass


def main():
    if os.getenv("NORA_BOT_ALLOW_LEGACY_SQLITE") != "1":
        print(
            "ربات اجرا نشد: اتصال به پایگاه مشترک هنوز کامل نیست؛ "
            "فعلاً اجرا را بسته‌ایم تا داده‌ها در پایگاه جداگانه ثبت نشوند."
        )
        return 2

    log("=" * 58)
    log(f"🤖 {brand()} — نسخه {VERSION}")
    log(f"🏢 {org_name()}")
    log("=" * 58)

    # ═══════════════════════════════════════════════
    # 🛡️ بررسی‌های حیاتی قبل از اجرا
    # ═══════════════════════════════════════════════

    # ۱) فایل‌های لازم
    missing = guard.check_files(log)
    if missing:
        log(f"❌ فایل‌های گمشده: {', '.join(missing)}")
        log("💡 همه فایل‌های پروژه را کپی کنید")
        return 1

    # ۲) تأیید نصب کد جدید
    feats = guard.check_new_features()
    not_installed = [k for k, v in feats.items() if not v]
    fp, nfiles, size = guard.code_fingerprint()
    log(f"🔖 امضای کد: {fp}  ({nfiles} فایل، {size//1024} KB)")
    if not_installed:
        log("")
        log("⛔ کد قدیمی تشخیص داده شد! این‌ها نصب نیستند:")
        for k in not_installed:
            log(f"   ❌ {k}")
        log("")
        log("💡 فایل‌های جدید را روی قدیمی‌ها کپی کنید (Replace/جایگزین)")
        log("   و پوشه __pycache__ را پاک کنید.")
        return 1
    log(f"✅ کد فاز ۷ کامل نصب است ({len(feats)} قابلیت)")

    # ۳) قفل تک‌نمونه — 🔴 جلوگیری از اجرای همزمان دو ربات
    okl, why = guard.acquire_lock(log)
    if not okl:
        log("")
        for line in why.split("\n"):
            log(line)
        return 1
    log("🔒 قفل تک‌نمونه گرفته شد")

    errors = check_config()
    if errors:
        guard.release_lock()
        for e in errors:
            log(f"❌ {e}")
        log("")
        log("💡 فایل .env را بسازید (از .env.example کپی کنید)")
        return 1

    # پیش از ساخت SQLite، هم دسترسی API و هم مالکیت سروری اپراتور تأیید شود.
    try:
        import shared_api as _shared_api
        _shared_api.require_owner_identity(SUPER_ADMIN_ID)
    except Exception as exc:
        guard.release_lock()
        code = getattr(exc, "code", "shared_api_unreachable")
        if code == "shared_owner_identity_required":
            log("❌ شناسهٔ اپراتور ربات در پایگاه مشترک نقش مالک ندارد.")
            log("💡 SUPER_ADMIN_ID ربات را با NORA_OWNER_BALE_USER_ID در backend هماهنگ کنید.")
        else:
            log(f"❌ اتصال به پایگاه مشترک برقرار نشد: {code}")
            log("💡 آدرس API، نسخهٔ پایگاه داده و کلید سرویس را بررسی کنید.")
        return 1

    init_db()
    ev_mod.init_event_tables()
    att_mod.init_attendance_tables()
    pay_mod.init_payment_tables()
    fb_mod.init_form_tables()
    oc_mod.init_occasion_tables()
    perm_mod.init_permission_tables()
    club_mod.init_club_tables()
    tk_mod.init_ticket_tables()
    lt_mod.init_lottery_tables()
    tk_mod.init_inbox_table()
    pl_mod.init_paylink_tables()
    pp_mod.init_payplan_tables()
    profile_mod.init_profile_extra()
    ab_mod.init_about_tables()
    cg_mod.init_cert_tables()
    aa_mod.init_tables()
    sv_mod.init_tables()
    cv_mod.init_tables()
    cc_mod.init_tables()          # 🏛️ فاز ۳۶ — مرکز صدور
    ads_mod.init_ads_tables()
    seed_default_settings()
    set_mod.seed_phase5_settings()
    ensure_super_admin(SUPER_ADMIN_ID)

    for w in config_warnings():
        log(f"⚠️ {w}")

    log("🔌 تست اتصال به بله...")
    me = get_me()
    if not me.get("ok"):
        guard.release_lock()
        log(f"❌ اتصال ناموفق: {me.get('description')}")
        log("💡 توکن را بررسی کنید یا فیلترشکن را خاموش کنید")
        return 1

    info = me.get("result") or {}
    log(f"✅ متصل شد: @{info.get('username')} ({info.get('first_name')})")

    # ۴) 🔴 حذف وبهوک — وگرنه هیچ پیامی دریافت نمی‌شود
    wok, wmsg = guard.ensure_polling_mode(log)
    if not wok:
        log(wmsg)
        log("⚠️ ربات ادامه می‌دهد ولی ممکن است پیامی نگیرد")
    log(f"📱 OTP سفیر: {'✅ فعال (bot_id=' + str(SAFIR_BOT_ID) + ')' if SAFIR_ENABLED else '⚠️ حالت تست'}")
    log(f"💳 پرداخت: {'✅ فعال' + (' (تست)' if PAYMENT_TEST_MODE else '') if PAYMENT_ENABLED else '❌ غیرفعال'}")
    log(f"👍 لایک خودکار: {'فعال ' + AUTO_REACT_EMOJI if AUTO_REACT_ENABLED else 'غیرفعال'}")

    users = db_scalar("SELECT COUNT(*) FROM users")
    evs = db_scalar("SELECT COUNT(*) FROM events")
    log(f"👥 کاربران: {users}  |  🎉 رویدادها: {evs}")

    startup = [
        f"🤖 {brand()} روشن شد",
        f"📦 نسخه {VERSION} — فاز ۵",
        "",
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"👥 کاربران: {users}",
        f"🎉 رویدادها: {evs}",
        "",
        "📊 وضعیت سرویس‌ها:",
        f"├── 📱 OTP سفیر: {'✅ فعال' if SAFIR_ENABLED else '⚠️ حالت تست'}",
        f"├── 💳 پرداخت: {'✅ فعال' + (' (تست)' if PAYMENT_TEST_MODE else '') if PAYMENT_ENABLED else '❌ غیرفعال'}",
        f"└── 👍 لایک خودکار: {'فعال' if AUTO_REACT_ENABLED else 'غیرفعال'}",
        "",
        "🆕 جدید در فاز ۵:",
        "• 🎉 رویدادها (۸ نوع کامل)",
        "• 💳 پرداخت کیف پول بله",
        "• 🎫 بلیت و لیست انتظار",
        "• 📢 اطلاع‌رسانی همگانی",
        "• 📝 متن‌های قابل تغییر از پنل",
        "• 📊 گزارش و خروجی اکسل",
    ]
    if SAFIR_ENABLED and SAFIR_BOT_ID == MAIN_BOT_ID:
        startup += ["", "⚠️ SAFIR_BOT_ID با بات اصلی یکی است — بررسی کنید"]

    send(SUPER_ADMIN_ID, "\n".join(startup))

    log("=" * 58)
    log("✅ ربات آماده است — برای توقف Ctrl+C")
    log("=" * 58)

    STATS["started"] = time.time()
    offset = None
    first = get_updates(offset=None, timeout=1)
    if first.get("ok") and first.get("result"):
        offset = first["result"][-1]["update_id"] + 1
        log(f"🧹 {len(first['result'])} آپدیت قدیمی نادیده گرفته شد")

    errs = 0
    last_cleanup = time.time()
    last_occasion = 0.0   # 🎂 بلافاصله بعد از استارت یک بار چک شود
    last_certclean = 0.0  # 🧹 پاکسازی فایل گواهینامه
    last_stat = time.time()
    last_shared_sync = 0.0

    while True:
        try:
            res = get_updates(offset=offset, timeout=25)

            if not res.get("ok"):
                errs += 1
                wait = min(5 * errs, 60)
                log(f"⚠️ getUpdates ناموفق ({errs}): {res.get('description')} — {wait}s")
                time.sleep(wait)
                continue

            errs = 0
            batch = res.get("result") or []
            if batch:
                log(f"📥 {len(batch)} آپدیت دریافت شد")
            for update in batch:
                offset = update["update_id"] + 1
                process_update(update)

            from config import SHARED_API_URL, SHARED_API_TOKEN
            if SHARED_API_URL and SHARED_API_TOKEN and time.time() - last_shared_sync > 30:
                last_shared_sync = time.time()
                shared_workflows_mod.sync_workflow_projections()
                shared_workflows_mod.deliver_pending_notifications()

            if time.time() - last_cleanup > 21600:
                cleanup_expired()
                last_cleanup = time.time()

            # 🎂 بررسی تولد و مناسبت‌ها (هر ساعت چک، روزی یک بار اجرا)
            if time.time() - last_occasion > 3600:
                last_occasion = time.time()
                try:
                    oc_mod.run_daily()
                except Exception as e:
                    log(f"⚠️ اجرای مناسبت‌ها: {e}")
                # 🎲 قرعه‌کشی‌های زمان‌بندی‌شده
                try:
                    lt_mod.check_scheduled()
                except Exception as e:
                    log(f"⚠️ قرعه‌کشی خودکار: {e}")
                # 📣 فاز ۲۰ — کمپین‌های تبلیغاتی زمان‌بندی‌شده
                try:
                    n_ad = ads_mod.check_scheduled()
                    if n_ad:
                        log(f"📣 {n_ad} کمپین زمان‌بندی‌شده اجرا شد")
                except Exception as e:
                    log(f"⚠️ کمپین زمان‌بندی‌شده: {e}")
                # 🔔 فاز ۱۸-د — یادآوری اقساط سررسیدشده
                #    🔴 این تابع نوشته شده بود ولی هرگز صدا زده نمی‌شد!
                try:
                    n_rem = pp_mod.check_due_reminders()
                    if n_rem:
                        log(f"🔔 {n_rem} یادآوری قسط ارسال شد")
                except Exception as e:
                    log(f"⚠️ یادآوری اقساط: {e}")
                # 📊 فاز ۳۳ — نظرسنجی خودکار بعد از رویداد
                #    🔴 ستون‌های survey_* بودند ولی هیچ‌جا خوانده
                #       نمی‌شدند — نظرسنجی هرگز فرستاده نمی‌شد.
                try:
                    n_sv = sv_mod.run_due()
                    if n_sv:
                        log(f"📊 نظرسنجی برای {n_sv} نفر فرستاده شد")
                    n_svr = sv_mod.run_reminders()
                    if n_svr:
                        log(f"🔁 {n_svr} یادآوری نظرسنجی")
                except Exception as e:
                    log(f"⚠️ نظرسنجی خودکار: {e}")
                # ⏰ فاز ۳۴ — هشدار انقضای گواهینامه
                try:
                    n_ex = cv_mod.warn_expiring()
                    if n_ex:
                        log(f"⏰ {n_ex} هشدار انقضای گواهینامه")
                except Exception as e:
                    log(f"⚠️ هشدار انقضا: {e}")

            # 🧹 فاز ۱۹-ب — پاکسازی فایل‌های منقضی گواهینامه
            if time.time() - last_certclean > 3600:
                last_certclean = time.time()
                try:
                    cg_mod.cleanup_files()
                except Exception as e:
                    log(f"⚠️ پاکسازی گواهینامه: {e}")

            # 💾 فاز ۱۸-د — بک‌آپ خودکار
            try:
                bp = auto_backup()
                if bp:
                    log("💾 بک‌آپ خودکار انجام شد")
            except Exception as e:
                log(f"⚠️ بک‌آپ خودکار: {e}")

            if time.time() - last_stat > 300:
                log(f"📊 آپدیت: {STATS['updates']} | پیام: {STATS['messages']}"
                    f" | دکمه: {STATS['callbacks']} | خطا: {STATS['errors']}")
                last_stat = time.time()

        except KeyboardInterrupt:
            log("⛔ توقف توسط کاربر")
            break
        except Exception as e:
            errs += 1
            log(f"❌ خطای حلقه اصلی: {e}")
            log(traceback.format_exc()[:600])
            time.sleep(min(5 * errs, 60))

    guard.release_lock()
    close_db()
    log("👋 خاموش شد")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        try:
            guard.release_lock()
        except Exception:
            pass
        close_db()
        print("\n👋 خاموش شد")
        sys.exit(0)
