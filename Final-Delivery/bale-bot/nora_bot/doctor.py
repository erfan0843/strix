"""
🩺 دکتر نورا — بررسی اتصال واقعی به سرورهای بله

این ابزار با سرور *واقعی* بله تماس می‌گیرد و می‌گوید دقیقاً چه چیزی
کار می‌کند و چه چیزی نه. برخلاف تست‌های شبیه‌سازی‌شده، اینجا
پاسخ واقعی سرور بررسی می‌شود.

اجرا:
    py doctor.py                      # بررسی پایه
    py doctor.py 09120000000          # + تست واقعی OTP روی این شماره

⚠️ برای تست OTP، یک کد واقعی به آن شماره ارسال می‌شود.
"""
import json
import os
import sys
import time

OK, WARN, ERR, INFO = [], [], [], []


def p(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(str(msg).encode("ascii", "ignore").decode(), flush=True)


def head(t):
    p("")
    p("─" * 58)
    p(t)
    p("─" * 58)


def ok(t, detail=""):
    OK.append(t)
    p(f"  ✅ {t}" + (f"  {detail}" if detail else ""))


def warn(t, detail=""):
    WARN.append((t, detail))
    p(f"  ⚠️  {t}" + (f"\n      {detail}" if detail else ""))


def err(t, detail=""):
    ERR.append((t, detail))
    p(f"  ❌ {t}" + (f"\n      {detail}" if detail else ""))


def info(t):
    INFO.append(t)
    p(f"  ℹ️  {t}")


p("=" * 58)
p("🩺 دکتر نورا — بررسی اتصال واقعی به بله")
p("=" * 58)


# ==================== ۱. تنظیمات ====================
head("۱) بررسی فایل تنظیمات (.env)")

try:
    import config
except Exception as e:
    err("خواندن config.py ناموفق", str(e))
    sys.exit(1)

if not config.BOT_TOKEN:
    err("BOT_TOKEN خالی است", "فایل .env را بسازید")
    sys.exit(1)
if ":" not in config.BOT_TOKEN:
    err("BOT_TOKEN فرمت درستی ندارد", "باید مثل 123456789:xxxx باشد")
    sys.exit(1)
ok("BOT_TOKEN موجود است", f"بات #{config.MAIN_BOT_ID}")

if not config.SUPER_ADMIN_ID:
    err("SUPER_ADMIN_ID خالی است", "آیدی عددی خود را در .env بنویسید")
else:
    ok("SUPER_ADMIN_ID", str(config.SUPER_ADMIN_ID))

# پکیج‌ها
for name, pkg, why in [
    ("requests", "requests", "اجباری — بدون آن ربات کار نمی‌کند"),
    ("openpyxl", "openpyxl", "برای ورود/خروجی اکسل"),
    ("Pillow", "PIL", "برای فشرده‌سازی عکس"),
]:
    try:
        __import__(pkg)
        ok(f"پکیج {name} نصب است")
    except ImportError:
        if pkg == "requests":
            err(f"پکیج {name} نصب نیست", f"py -m pip install {name}")
            sys.exit(1)
        warn(f"پکیج {name} نصب نیست", f"{why}\n      نصب: py -m pip install {name}")


# ==================== ۲. اتصال به بات ====================
head("۲) اتصال به سرور بله")

import bale_api  # noqa: E402

t0 = time.time()
me = bale_api.get_me()
dt = (time.time() - t0) * 1000

NET_OK = bool(me.get("ok"))
bot = me.get("result") or {}

if not NET_OK:
    d = str(me.get("description", ""))
    err("اتصال به بله ناموفق", d[:150])
    p("")
    p("  🔍 علت‌های احتمالی:")
    if "Max retries" in d or "timeout" in d.lower() or "Connection" in d:
        p("     • اینترنت قطع است یا سرور در دسترس نیست")
        p("     • فیلترشکن روشن است (برای بله باید خاموش باشد)")
        p("     • فایروال ویندوز مسیر را بسته")
    else:
        p("     • توکن اشتباه است یا revoke شده")
        p("     • توکن را از @botfather دوباره بگیرید")
    p("")
    p("  ⏭️  بقیه بررسی‌های آفلاین ادامه می‌یابد...")
else:
    ok("اتصال برقرار شد", f"@{bot.get('username')} — {dt:.0f}ms")
    info(f"نام بات: {bot.get('first_name')}")
    info(f"شناسه بات: {bot.get('id')}")
    if dt > 3000:
        warn("پاسخ سرور کند است", f"{dt:.0f}ms — روی VPS بهتر می‌شود")


# ==================== ۳. وبهوک ====================
head("۲.۵) 🛡️ بررسی نمونه‌های همزمان و کد")

try:
    import guard as _guard
    miss = _guard.check_files()
    if miss:
        err("فایل‌های گمشده", "، ".join(miss))
    else:
        ok("همه فایل‌های پروژه موجودند")

    feats = _guard.check_new_features()
    bad_f = [k for k, v in feats.items() if not v]
    fp_, nf_, sz_ = _guard.code_fingerprint()
    info(f"امضای کد: {fp_} ({nf_} فایل، {sz_//1024} KB)")
    if bad_f:
        err("کد قدیمی است — این‌ها نصب نیستند", "، ".join(bad_f)
            + "\n      💡 فایل‌های جدید را جایگزین کنید")
    else:
        ok(f"کد فاز ۷ کامل است ({len(feats)} قابلیت)")

    if _guard.LOCK_FILE.exists():
        try:
            raw = _guard.LOCK_FILE.read_text(encoding="utf-8").split("|")
            pid_ = raw[0]
            if _guard._pid_alive(pid_):
                err(f"🔴 ربات دیگری در حال اجراست (PID {pid_})",
                    "دو نمونه همزمان = آپدیت‌ها تقسیم می‌شوند\n"
                    "      ⇒ «دکمه‌ها تصادفاً کار نمی‌کنند»\n"
                    "      💡 stop.bat را اجرا کنید")
            else:
                warn("فایل قفل مانده ولی فرآیند مرده است",
                     "خودکار پاک می‌شود")
        except Exception:
            pass
    else:
        ok("هیچ نمونه دیگری در حال اجرا نیست")
except Exception as ex:
    info(f"بررسی محافظ ممکن نشد: {ex}")


head("۳) وضعیت وبهوک")

wh = bale_api.get_webhook_info() if NET_OK else {"ok": False}
if wh.get("ok"):
    url = (wh.get("result") or {}).get("url") or ""
    if url:
        err("🔴 وبهوک فعال است", f"{url}\n"
            "      ⇒ getUpdates هیچ آپدیتی نمی‌دهد!\n"
            "      ⇒ ربات بالا می‌آید ولی هیچ پیامی نمی‌گیرد\n"
            "      💡 در حال حذف خودکار...")
        _r = bale_api.delete_webhook()
        if _r.get("ok"):
            ok("وبهوک حذف شد", "حالا polling کار می‌کند")
        else:
            err("حذف ناموفق", str(_r.get("description")))
    else:
        ok("وبهوک خالی است", "polling بدون مشکل کار می‌کند")
else:
    info("بررسی وبهوک ممکن نشد (مهم نیست)")

if "--delete-webhook" in sys.argv:
    r = bale_api.delete_webhook()
    if r.get("ok"):
        ok("وبهوک حذف شد")
    else:
        err("حذف وبهوک ناموفق", str(r.get("description")))


# ==================== ۴. ارسال پیام ====================
head("۴) ارسال پیام به سوپرادمین")

ADMIN = config.SUPER_ADMIN_ID
test_msg_id = None

if not NET_OK:
    info("رد شد — اتصال شبکه برقرار نیست")
elif not ADMIN:
    err("بدون SUPER_ADMIN_ID نمی‌توان تست کرد")
else:
    r = bale_api.send(ADMIN, (
        "🩺 تست دکتر نورا\n"
        "━━━━━━━━━━━━━━\n\n"
        "اگر این پیام را می‌بینید، ارسال پیام سالم است."
    ))
    if r.get("ok"):
        test_msg_id = (r.get("result") or {}).get("message_id")
        ok("ارسال پیام موفق", f"message_id={test_msg_id}")
    else:
        d = str(r.get("description", ""))
        err("ارسال پیام ناموفق", d)
        if "chat not found" in d.lower():
            p("      💡 اول یک بار به ربات /start بدهید تا چت باز شود")


# ==================== ۵. پیام طولانی ====================
head("۵) پیام بلندتر از ۴۰۹۶ کاراکتر")

if NET_OK and ADMIN and test_msg_id:
    long_text = "🩺 تست پیام طولانی\n" + ("این یک خط تست است. " * 400)
    chunks = bale_api._split_text(long_text)
    r = bale_api.send(ADMIN, long_text)
    if r.get("ok"):
        ok("پیام طولانی ارسال شد", f"در {len(chunks)} تکه")
    else:
        err("ارسال پیام طولانی ناموفق", str(r.get("description")))


# ==================== ۶. کیبورد شیشه‌ای ====================
head("۶) کیبورد و دکمه‌ها")

if NET_OK and ADMIN:
    r = bale_api.send(ADMIN, "🩺 تست دکمه‌ها — روی هرکدام بزنید (بی‌خطر است)", {
        "inline_keyboard": [
            # 🔴 باگ رفع‌شده (فاز ۴۰): «doctor_test» هیچ هندلری
            #    در روتر نداشت — ادمین می‌زد و فقط ساعت‌شنی
            #    می‌چرخید. حالا به صفحهٔ سلامت ربات می‌رود که
            #    از قبل وجود دارد.
            [{"text": "🔘 دکمه callback", "callback_data": "ct_engine"}],
            [{"text": "🌐 دکمه لینک", "url": "https://ble.ir"}],
            [{"text": "📋 دکمه کپی متن", "copy_text": {"text": "NORA-TEST-123"}}],
        ]
    })
    if r.get("ok"):
        ok("کیبورد شیشه‌ای ارسال شد")
        info("اگر «دکمه کپی متن» را نمی‌بینید = کلاینت شما قدیمی است")
    else:
        d = str(r.get("description", ""))
        err("ارسال کیبورد ناموفق", d)
        if "copy_text" in d.lower():
            warn("copy_text پشتیبانی نمی‌شود", "دکمه کپی بلیت کار نخواهد کرد")
else:
    info("رد شد — اتصال شبکه برقرار نیست")



# ==================== ۶.۵ ویرایش پیام ====================
head("۶.۵) ✏️ ویرایش پیام — editMessageText")
p("  📌 اگر این کار نکند، منوها پیام جدید می‌فرستند (شلوغ ولی سالم)")

if NET_OK and ADMIN and test_msg_id:
    r = bale_api.api("editMessageText", {
        "chat_id": ADMIN, "message_id": test_msg_id,
        "text": "🩺 تست دکتر نورا\n━━━━━━━━━━━━━━\n\n✅ ویرایش پیام کار می‌کند!"
    }, retries=0)
    if r.get("ok"):
        ok("editMessageText کار می‌کند", "منوها در جا به‌روز می‌شوند 🎉")
    else:
        warn("ویرایش پیام کار نکرد", f"{r.get('description')}\n"
             "      ⇒ ربات به‌جای ویرایش، پیام جدید می‌فرستد (سالم ولی شلوغ)")
else:
    info("رد شد — اتصال شبکه برقرار نیست")


# ==================== ۶.۶ دکمه کپی ====================
head("۶.۶) 📋 دکمه copy_text")
p("  📌 اگر پشتیبانی نشود، ربات خودکار دکمه را حذف می‌کند")

if NET_OK and ADMIN:
    r = bale_api.api("sendMessage", {
        "chat_id": ADMIN, "text": "🩺 تست دکمه کپی",
        "reply_markup": {"inline_keyboard": [
            [{"text": "📋 کپی", "copy_text": {"text": "NORA-TEST"}}]]}
    }, retries=0)
    if r.get("ok"):
        ok("copy_text پشتیبانی می‌شود", "دکمه‌های کپی کد بلیت/لینک کار می‌کنند")
    else:
        warn("copy_text پشتیبانی نمی‌شود", f"{r.get('description')}\n"
             "      ⇒ ربات خودکار این دکمه‌ها را حذف می‌کند (بدون خطا)")
else:
    info("رد شد — اتصال شبکه برقرار نیست")


# ==================== ۷. ری‌اکشن (لایک) ====================
head("۷) ❤️ ری‌اکشن — setMessageReaction")
p("  📌 این متد در مستندات رسمی بله نیست — باید واقعی تست شود")
p(f"  ❤️ ایموجی تنظیم‌شده: {config.AUTO_REACT_EMOJI}")

if NET_OK and ADMIN and test_msg_id:
    r = bale_api.set_reaction_sync(ADMIN, test_msg_id)
    if r.get("ok"):
        ok("ری‌اکشن گذاشته شد!", "لایک خودکار کار می‌کند 🎉")
        info("پیام اول تست را ببینید — باید 👍 داشته باشد")
    else:
        d = str(r.get("description", "") or r)
        warn("ری‌اکشن کار نکرد", f"{d}\n"
             "      ⇒ بله فعلاً setMessageReaction ندارد.\n"
             "      ✅ ربات خودکار بعد از ۳ شکست خاموشش می‌کند\n"
             "         و دیگر هرگز کندی ایجاد نمی‌کند.\n"
             "      برای خاموش کردن دستی: AUTO_REACT_ENABLED=0")
else:
    info("رد شد (پیام تست ارسال نشده بود)")


# ==================== ۸. رضایت‌سنجی ====================
head("۸) 📝 askReview — فرم رضایت‌سنجی")

if NET_OK and ADMIN:
    r = bale_api.ask_review(ADMIN, 60)
    if r.get("ok"):
        ok("askReview پذیرفته شد", "تا ۶۰ ثانیه دیگر فرم نمایش داده می‌شود")
    else:
        warn("askReview کار نکرد", f"{r.get('description')}\n"
             "      ⇒ روی نسخه قدیمی کلاینت یا غیرفعال است.\n"
             "      خاموش کردن: ASK_REVIEW_ENABLED=0")
else:
    info("رد شد — اتصال شبکه برقرار نیست")


# ==================== ۹. sendChatAction ====================
head("۹) نمایش «در حال تایپ...»")

if NET_OK and ADMIN:
    r = bale_api.send_chat_action(ADMIN, "typing")
    if r.get("ok"):
        ok("sendChatAction کار می‌کند")
    else:
        warn("sendChatAction کار نکرد", str(r.get("description")))
else:
    info("رد شد — اتصال شبکه برقرار نیست")


# ==================== ۱۰. OTP سفیر ====================
head("۱۰) 📱 سرویس سفیر — رمز یکبار مصرف")

p(f"  🔑 کلید API: {'✅ ثبت شده' if config.SAFIR_API_KEY else '❌ خالی'}")
p(f"  🤖 bot_id سفیر: {config.SAFIR_BOT_ID or '❌ خالی'}")
p(f"  🆔 bot_id اصلی: {config.MAIN_BOT_ID}")
p("")

if not config.SAFIR_ENABLED:
    warn("سفیر غیرفعال است", "ربات در «حالت تست» کار می‌کند و کد را در چت نشان می‌دهد.\n"
         "      برای فعال‌سازی SAFIR_API_KEY و SAFIR_BOT_ID را در .env بنویسید.")
else:
    if config.SAFIR_BOT_ID == config.MAIN_BOT_ID:
        warn("bot_id سفیر با بات اصلی یکی است",
             "معمولاً بات رمز یکبار مصرف جداست — همین باعث خطا می‌شود")
    else:
        ok("bot_id سفیر جدا از بات اصلی است", "درست تنظیم شده")

    phone = None
    for a in sys.argv[1:]:
        if a.startswith("09") or a.startswith("+98") or a.startswith("98"):
            phone = a
            break

    if not phone:
        info("برای تست واقعی: py doctor.py 09120000000")
    else:
        from auth import normalize_mobile, to_intl_phone, generate_otp, send_otp_via_safir
        m = normalize_mobile(phone)
        if not m:
            err("شماره نامعتبر", phone)
        else:
            p(f"  📤 ارسال کد واقعی به {m} ({to_intl_phone(m)}) ...")
            code = generate_otp()
            t0 = time.time()
            res = send_otp_via_safir(m, code)
            dt = (time.time() - t0) * 1000

            if res.get("ok") and not res.get("test_mode"):
                ok("🎉 OTP واقعی ارسال شد!", f"{dt:.0f}ms — msg_id={res.get('message_id')}")
                info(f"کد ارسالی: {code}")
                info("در «بات رمز یکبار مصرف» بله چک کنید")
            elif res.get("test_mode"):
                warn("حالت تست", "کلید یا bot_id خالی است")
            else:
                err("ارسال OTP ناموفق", str(res.get("error")))
                if res.get("hint"):
                    p(f"      💡 {res['hint']}")
                p("")
                p("      🔍 چک‌لیست عیب‌یابی:")
                p("         ۱. bot_id باید شناسه «بات OTP» باشد نه بات اصلی")
                p("         ۲. کلید api-access-key از پنل کسب‌وکار معتبر باشد")
                p("         ۳. شماره در پنل کسب‌وکار مجاز شده باشد")
                p("         ۴. اعتبار پنل کسب‌وکار تمام نشده باشد")


# ==================== ۱۱. پرداخت ====================
head("۱۱) 💳 پرداخت کیف پول")

if not config.PAYMENT_ENABLED:
    warn("توکن پرداخت تنظیم نشده", "رویدادهای پولی کار نمی‌کنند.\n"
         "      برای تست: PAYMENT_PROVIDER_TOKEN=WALLET-TEST-1111111111111111")
else:
    if config.PAYMENT_TEST_MODE:
        ok("توکن آزمایشی است", "پولی جابه‌جا نمی‌شود — تست امن")
    else:
        warn("🔴 توکن پرداخت واقعی است",
             "پرداخت‌ها از کیف پول واقعی کم می‌شوند!\n"
             f"      🛡️ سقف هر تراکنش: {config.PAYMENT_MAX_AMOUNT:,} ریال\n"
             f"      🛡️ حداقل: {config.PAYMENT_MIN_AMOUNT:,} ریال\n"
             f"      🛡️ تأیید دومرحله‌ای: "
             f"{'فعال' if config.PAYMENT_CONFIRM else 'غیرفعال'}\n"
             f"      💡 برای تست امن: PAYMENT_PROVIDER_TOKEN=WALLET-TEST-1111111111111111")

    if NET_OK and ADMIN and "--test-invoice" in sys.argv:
        p("  📤 ارسال فاکتور تست ۱۰۰۰ ریالی...")
        r = bale_api.send_invoice(
            ADMIN, "تست دکتر نورا", "این یک فاکتور آزمایشی است",
            f"doctor_test_{int(time.time())}",
            config.PAYMENT_PROVIDER_TOKEN,
            [{"label": "تست", "amount": 1000}])
        if r.get("ok"):
            ok("sendInvoice کار می‌کند!", "فاکتور را در چت ببینید")
            info("اگر پرداخت کنید، ربات باید روشن باشد تا ثبت شود")
        else:
            err("sendInvoice ناموفق", str(r.get("description")))
    else:
        if config.PAYMENT_TEST_MODE:
            info("برای تست فاکتور: py doctor.py --test-invoice")
        else:
            info("برای تست از داخل ربات: /paytest (با تأیید دومرحله‌ای)")


# ==================== ۱۲. دیتابیس ====================
head("۱۲) دیتابیس و مهاجرت")

try:
    from database import (init_db, db_scalar, db_execute, seed_default_settings)
    import events as ev_mod
    import attendance as att_mod
    import settings_admin as set_mod

    # قبل از مهاجرت
    pre = {}
    for t in ("events", "users", "event_registrations"):
        r = db_execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (t,), fetch="one")
        if r:
            pre[t] = len(db_execute(f"PRAGMA table_info({t})", fetch="all") or [])

    broken_before = 0
    if db_execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_states'",
                  fetch="one"):
        broken_before = db_scalar(
            "SELECT COUNT(*) FROM user_states WHERE state IS NULL OR state=''")

    init_db()
    ev_mod.init_event_tables()
    att_mod.init_attendance_tables()
    seed_default_settings()
    set_mod.seed_phase5_settings()

    # بعد از مهاجرت
    for t, before in pre.items():
        after = len(db_execute(f"PRAGMA table_info({t})", fetch="all") or [])
        if after > before:
            ok(f"جدول {t} به‌روز شد", f"{before} → {after} ستون")
        else:
            ok(f"جدول {t} به‌روز است", f"{after} ستون")

    if broken_before:
        ok(f"{broken_before} وضعیت خراب پاکسازی شد",
           "این‌ها باعث می‌شدند ربات پیام‌ها را نشناسد")

    tables = [t["name"] for t in db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        fetch="all") or []]
    need = ["users", "events", "event_registrations", "transactions", "settings",
            "attendance_sessions", "attendance_records", "certificates",
            "profile_submissions", "force_join_channels", "otp_codes",
            "user_states", "user_actions", "import_history"]
    missing = [t for t in need if t not in tables]
    if missing:
        err("جدول‌های گمشده", "، ".join(missing))
    else:
        ok(f"همه {len(need)} جدول موجود است")

    # بررسی ستون‌های حیاتی events
    ev_cols = {c["name"] for c in db_execute("PRAGMA table_info(events)",
                                             fetch="all") or []}
    critical = ["capacity", "is_paid", "price", "privacy", "has_attendance",
                "has_certificate", "points_reward", "online_link",
                "location_type", "start_date"]
    miss_c = [c for c in critical if c not in ev_cols]
    if miss_c:
        err("ستون‌های حیاتی events گم شده", "، ".join(miss_c)
            + "\n      ⇒ ذخیره رویداد کار نخواهد کرد!")
    else:
        ok("همه ستون‌های حیاتی events موجود است")

    # تست عملی: آیا واقعاً می‌شود رویداد ساخت؟
    test_id = db_execute("""INSERT INTO events
        (title, event_type, location_type, start_date, status, capacity,
         is_paid, price, privacy, has_attendance, has_certificate,
         has_ticket, points_reward, created_by)
        VALUES ('__doctor_test__','meeting','online','1404/01/01','draft',
                10,0,0,'public',0,0,1,0,?)""", (ADMIN or 0,))
    if test_id:
        db_execute("DELETE FROM events WHERE id=?", (test_id,))
        ok("✍️ تست عملی: ساخت رویداد کار می‌کند")
    else:
        err("✍️ تست عملی: ساخت رویداد ناموفق",
            "دکمه «ذخیره و انتشار» کار نخواهد کرد")

    u = db_scalar("SELECT COUNT(*) FROM users")
    e = db_scalar("SELECT COUNT(*) FROM events")
    s_ = db_scalar("SELECT COUNT(*) FROM settings")
    a = db_scalar("SELECT COUNT(*) FROM attendance_sessions")
    c_ = db_scalar("SELECT COUNT(*) FROM certificates")
    info(f"کاربران: {u} | رویدادها: {e} | جلسات: {a} | گواهینامه: {c_} | متن‌ها: {s_}")

    import os as _os
    from config import DB_PATH as _DBP
    if _os.path.exists(_DBP):
        ok("فایل دیتابیس سالم", f"{_os.path.getsize(_DBP)/1024:.0f} KB")

except Exception as ex:
    import traceback
    err("خطای دیتابیس", str(ex)[:200])
    p(traceback.format_exc()[:400])


# ==================== ۱۳. عضویت اجباری ====================
head("۱۳) عضویت اجباری")

try:
    from auth import get_all_channels, channel_target
    chs = get_all_channels() if NET_OK else []
    if not NET_OK:
        info("رد شد — اتصال شبکه برقرار نیست")
    elif not chs:
        info("کانالی تعریف نشده — همه کاربران آزادانه وارد می‌شوند")
    else:
        for ch in chs:
            tgt = channel_target(ch)
            title = ch.get("channel_title") or tgt
            r = bale_api.get_chat(tgt)
            if r.get("ok"):
                ok(f"دسترسی به {title}")
                m = bale_api.get_chat_member(tgt, config.MAIN_BOT_ID)
                if m.get("ok"):
                    st = (m.get("result") or {}).get("status")
                    if st in ("administrator", "creator"):
                        ok(f"  ربات در {title} ادمین است")
                    else:
                        warn(f"ربات در {title} ادمین نیست",
                             f"وضعیت: {st} — نمی‌تواند عضویت را چک کند")
            else:
                err(f"دسترسی به {title} ندارد", str(r.get("description")))
            if ch.get("is_private") and not ch.get("invite_link"):
                warn(f"{title} لینک دعوت ندارد",
                     "کاربر نمی‌داند چطور عضو شود — از 🔗 در پنل ثبت کنید")
except Exception as ex:
    info(f"بررسی نشد: {ex}")


# ==================== ۱۳.۵ تست سرعت ====================
head("۱۳.۵) ⚡ تست سرعت پاسخ‌گویی")
p("  📌 اگر ربات کند باشد، کاربر فکر می‌کند دکمه‌ها کار نمی‌کنند")

if NET_OK and ADMIN:
    import time as _t
    t0 = _t.time()
    for _ in range(3):
        bale_api.api("getMe", retries=0, timeout=10)
    avg = (_t.time() - t0) / 3 * 1000
    if avg < 800:
        ok("سرعت پاسخ عالی", f"میانگین {avg:.0f}ms")
    elif avg < 2500:
        ok("سرعت پاسخ قابل قبول", f"میانگین {avg:.0f}ms")
    else:
        warn("پاسخ کند است", f"میانگین {avg:.0f}ms\n"
             "      روی VPS ایران بهتر می‌شود")
    info("متدهای غیرحیاتی (ری‌اکشن، answerCallback) در پس‌زمینه اجرا می‌شوند")
    info("⇒ حتی اگر کند باشند، ربات یخ نمی‌زند")
else:
    info("رد شد — اتصال شبکه برقرار نیست")


# ==================== ۱۳.۶ موتور گواهینامه ====================
head("۱۳.۶) 🖨️ موتور تبدیل گواهینامه")

try:
    import certgen as _cg
    _st = _cg.engine_status(force=True)

    if _st["docx"]:
        ok("خواندن فایل ورد (python-docx)")
    else:
        err("python-docx نصب نیست",
            "py -m pip install python-docx")

    if _st["libreoffice"]:
        ok("LibreOffice پیدا شد", _st.get("lo_path", ""))
        info("طرح فایل ورد عیناً حفظ می‌شود ✨")
    elif _st.get("word"):
        ok("Microsoft Word پیدا شد (pywin32)")
        info("طرح فایل ورد عیناً حفظ می‌شود ✨")
    else:
        _d = _cg.lo_diagnose()
        warn("LibreOffice و Word پیدا نشدند",
             f"{_d['checked']} مسیر بررسی شد — موتور داخلی فعال است")
        if _d["existing"]:
            info("این فایل‌ها بودند ولی اجرا نشدند:")
            for _p in _d["existing"][:3]:
                info(f"   {_p}")
            info("⇒ نصب ناقص است، دوباره نصب کنید")
        else:
            if os.name == "nt":
                info("💡 اگر مطمئنید نصب است: نصب‌کننده لیبره خودش را")
                info("   به PATH اضافه نمی‌کند. داخل ربات بروید به:")
                info("   تنظیمات › گواهینامه و بلیط › 🩺 موتور تبدیل")
                info("   و مسیر soffice.exe را دستی بدهید.")
            else:
                info("نصب: sudo apt install libreoffice-writer")

    if _st["png"]:
        ok("تبدیل به تصویر ممکن است")
    elif _st.get("png_builtin"):
        warn("تبدیل حرفه‌ای تصویر نیست", "موتور داخلی جایگزین می‌شود")

    if _st["qr"]:
        ok("کیوآرکد اعتبارسنجی")
    else:
        warn("qrcode نصب نیست", "py -m pip install qrcode")

    if _st["fa_shape"]:
        ok("فارسی‌نویسی روی تصویر")
    else:
        warn("فارسی‌نویسی ناقص",
             "py -m pip install arabic-reshaper python-bidi")
except Exception as _e:
    warn("بررسی موتور گواهینامه ناموفق", str(_e)[:120])


# ==================== ۱۳.۷ دفترکل امتیاز ====================
head("۱۳.۷) 🏅 دفترکل امتیاز (فقط گزارش؛ هیچ اصلاح خودکاری انجام نمی‌شود)")
try:
    import points_ledger as _pl

    _hr = _pl.health_report()
    _rep = _hr.get("report") or {}
    if not _rep.get("installed"):
        warn("جدول points_ledger وجود ندارد",
             "پس از توقف ربات و پشتیبان معتبر: migrate_points_opening_balance.py (dry-run → --apply --yes)")
    else:
        info(f"ردیف‌ها: {_rep.get('entries', 0)}  |  کاربران با دفترکل: {_rep.get('users_with_ledger', 0)}"
             f" از {_rep.get('users_nonzero', 0)} کاربر غیرصفر")
        _sync = _rep.get("sync") or {}
        info("همگام‌سازی سرور: " + "  ".join(f"{k}={v}" for k, v in _sync.items()))
        for _pr in _hr.get("problems") or []:
            err("دفترکل امتیاز: " + _pr, "اصلاح فقط با اسکریپت و تأیید صریح (rebaseline / guard-on)")
        for _wn in _hr.get("warnings") or []:
            warn("دفترکل امتیاز: " + _wn)
        if _hr.get("ok"):
            ok("شمارندهٔ امتیاز با دفترکل تطبیق دارد", "نگهبان total_points نصب است")
        _meta = _rep.get("meta") or {}
        if _meta.get("guard_disabled_at"):
            warn("نگهبان آگاهانه حذف شده (guard-off)", f"از {_meta['guard_disabled_at']}")
    if not getattr(config, "POINTS_MANUAL_ADJUST_MAX", 0):
        info("تعدیل دستی امتیاز غیرفعال است (POINTS_MANUAL_ADJUST_MAX تنظیم نشده) — رفتار پیش‌فرض و امن")
except Exception as _e:
    warn("بررسی دفترکل امتیاز ناموفق", type(_e).__name__)


# ==================== ۱۴. راهنمای عیب‌یابی ====================
head("۱۴) 🐞 ابزار عیب‌یابی داخل ربات")
info("دستور /debug on  → گزارش دکمه‌های بدون هندلر و خطاهای API")
info("دستور /debug off → خاموش کردن")
info("دستور /testotp   → تست رمز یکبار مصرف")
info("دستور /chatid    → گرفتن آیدی گروه (داخل گروه بزنید)")
info("دستور /paytest   → ابزار تست پرداخت 🆕")
info("دستور /menu      → فرار از هر حالتی 🆕")


# ==================== جمع‌بندی ====================
p("")
p("=" * 58)
p(f"✅ سالم: {len(OK)}    ⚠️ هشدار: {len(WARN)}    ❌ خطا: {len(ERR)}")
p("=" * 58)

if ERR:
    p("")
    p("❌ خطاهایی که باید رفع شوند:")
    for t, d in ERR:
        p(f"   • {t}")
        if d:
            p(f"     {d[:150]}")

if WARN:
    p("")
    p("⚠️ هشدارها (ربات کار می‌کند ولی بخشی محدود است):")
    for t, d in WARN:
        p(f"   • {t}")

p("")
if not ERR:
    p("🎉 ربات آماده اجراست:  py main.py")
else:
    p("🔧 اول خطاهای بالا را رفع کنید، بعد:  py main.py")
p("")

sys.exit(1 if ERR else 0)
