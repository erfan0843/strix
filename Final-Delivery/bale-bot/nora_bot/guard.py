"""
🛡️ محافظ اجرا — فاز ۷

سه مشکل بحرانی را که باعث می‌شوند «هیچ دکمه‌ای کار نکند» رفع می‌کند:

۱. 🔴 چند نمونه همزمان
   اگر ربات دو بار اجرا شود (مثلاً دو پنجره CMD یا یکی در پس‌زمینه
   مانده باشد)، هر دو getUpdates می‌زنند. بله هر آپدیت را فقط به
   *یکی* از آن‌ها می‌دهد ⇒ تصادفاً نصف دکمه‌ها کار نمی‌کنند.

۲. 🔴 وبهوک فعال
   اگر قبلاً setWebhook زده شده باشد، getUpdates هیچ آپدیتی برنمی‌گرداند.
   ربات بالا می‌آید و «متصل شد» می‌گوید ولی هیچ پیامی دریافت نمی‌کند.

۳. 🟠 کد قدیمی در کش
   پوشه __pycache__ قدیمی می‌تواند باعث اجرای نسخه قبلی شود.
"""
import os
import shutil
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
LOCK_FILE = BASE / ".bot.lock"


# ==================== ۱) قفل تک‌نمونه ====================
def _pid_alive(pid):
    """آیا این PID هنوز زنده است؟"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import subprocess
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=8)
            return str(pid) in (out.stdout or "")
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
    except Exception:
        return False


def acquire_lock(log_fn=print):
    """
    قفل تک‌نمونه.
    خروجی: (True, "") اگر گرفته شد، (False, پیام) اگر نمونه دیگری فعال است.
    """
    if LOCK_FILE.exists():
        try:
            raw = LOCK_FILE.read_text(encoding="utf-8").strip().split("|")
            old_pid = raw[0] if raw else ""
            started = raw[1] if len(raw) > 1 else "?"
        except Exception:
            old_pid, started = "", "?"

        if old_pid and _pid_alive(old_pid):
            return False, (
                f"⛔ ربات از قبل در حال اجراست!\n"
                f"   شناسه فرآیند: {old_pid}\n"
                f"   زمان شروع: {started}\n\n"
                f"   🔴 اگر دو نسخه همزمان اجرا شوند، آپدیت‌ها بین‌شان\n"
                f"      تقسیم می‌شود و «دکمه‌ها تصادفاً کار نمی‌کنند».\n\n"
                f"   💡 راه حل:\n"
                f"      • پنجره CMD قبلی را ببندید (Ctrl+C)\n"
                f"      • یا در ویندوز: taskkill /F /PID {old_pid}\n"
                f"      • یا فایل .bot.lock را پاک کنید"
            )
        # قفل مرده — پاکش کن
        try:
            LOCK_FILE.unlink()
            log_fn(f"🔓 قفل قدیمی (PID {old_pid}) پاک شد")
        except Exception:
            pass

    try:
        LOCK_FILE.write_text(
            f"{os.getpid()}|{time.strftime('%Y-%m-%d %H:%M:%S')}",
            encoding="utf-8")
    except Exception as e:
        log_fn(f"⚠️ ساخت قفل ناموفق: {e}")
    return True, ""


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


# ==================== ۲) پاکسازی کش ====================
def clear_pycache(log_fn=print):
    """حذف __pycache__ تا مطمئن شویم کد جدید اجرا می‌شود"""
    n = 0
    try:
        for d in BASE.rglob("__pycache__"):
            try:
                shutil.rmtree(d)
                n += 1
            except Exception:
                pass
    except Exception:
        pass
    if n:
        log_fn(f"🧹 {n} پوشه کش پاک شد")
    return n


# ==================== ۳) اثر انگشت نسخه ====================
def code_fingerprint():
    """
    امضای کوتاه از کد فعلی — برای اطمینان از اینکه
    فایل‌های جدید واقعاً جایگزین شده‌اند.
    """
    import hashlib
    # A display-only version fingerprint, not an authentication/integrity proof.
    h = hashlib.md5(usedforsecurity=False)
    files = sorted(BASE.glob("*.py"))
    total = 0
    for f in files:
        try:
            b = f.read_bytes()
            h.update(b)
            total += len(b)
        except Exception:
            pass
    return h.hexdigest()[:8], len(files), total


def check_files(log_fn=print):
    """بررسی وجود همه فایل‌های لازم"""
    need = ["main.py", "config.py", "database.py", "privacy.py", "bale_api.py", "auth.py",
            "profile.py", "events.py", "attendance.py", "admin.py",
            "import_excel.py", "settings_admin.py", "payments.py",
            "forms.py", "form_fields.py", "form_fill.py", "form_reports.py",
            "iran_data.py", "occasions.py", "permissions.py",
            "activity_log.py", "finance.py", "club.py", "tickets.py",
            "lottery.py", "reports.py", "paylink.py",
            "certgen.py", "certissue.py", "infra_fee.py", "ticket.py",
            "ads.py", "about.py", "payplan.py"]
    missing = [f for f in need if not (BASE / f).exists()]
    return missing


def check_new_features():
    """
    بررسی اینکه آیا کد جدید فاز ۷ واقعاً نصب شده است.
    اگر کاربر فایل‌ها را جایگزین نکرده باشد، اینجا معلوم می‌شود.
    """
    markers = {
        "صف پس‌زمینه (رفع یخ‌زدگی)": ("bale_api.py", "FIRE_AND_FORGET"),
        "دستورات فرار": ("main.py", "ESCAPE"),
        "منوی دائمی": ("bale_api.py", "kb_persistent"),
        "مهاجرت دیتابیس": ("database.py", "ensure_table"),
        "ویرایش هوشمند": ("bale_api.py", "set_context"),
        "ابزار تست پرداخت": ("settings_admin.py", "payment_test_menu"),
        "حضور و غیاب": ("attendance.py", "init_attendance_tables"),
        "دکمه بازگشت ویزارد": ("events.py", "wizard_back"),
        # ---- فاز ۹ ----
        "فرم‌ساز": ("forms.py", "init_form_tables"),
        "کاتالوگ فیلدها": ("form_fields.py", "CONDITION_OPS"),
        "موتور پر کردن فرم": ("form_fill.py", "STATE_FILL"),
        "گزارش فرم": ("form_reports.py", "analyze_field"),
        "تک‌منو (رفع منوی تکراری)": ("bale_api.py", "MAIN_MENU_BUTTONS"),
        # ---- فاز ۱۰ ----
        "واحد پول یکسان": ("config.py", "def money"),
        "پرکردن خودکار پروفایل": ("forms.py", "sync_profile_from_response"),
        "مناسبت‌ها و تبریک": ("occasions.py", "init_occasion_tables"),
        "روش تأیید شماره": ("forms.py", "PHONE_VERIFY_MODES"),
        # ---- فاز ۱۱ ----
        "دعوت اجباری رویداد": ("events.py", "check_eligibility"),
        "قابلیت‌های پیشرفته رویداد": ("events.py", "EV_TOGGLES"),
        "کدهای دعوت رویداد": ("events.py", "EVENT_CODES_SCHEMA"),
        "نمایش مبلغ اختیاری": ("forms.py", "show_price_upfront"),
        # ---- فاز ۱۱-ب ----
        "خطاب مودبانه": ("occasions.py", "polite_name"),
        "امتیاز شرطی": ("occasions.py", "check_point_rules"),
        "یادآوری پیشرفته": ("events.py", "REMINDER_SLOTS"),
        "نظرسنجی رویداد": ("events.py", "show_survey"),
        "کد تخفیف": ("events.py", "apply_discount"),
        "فرم ثبت‌نام رویداد": ("events.py", "create_reg_form"),
        # ---- فاز ۱۲ ----
        "لاگ فارسی": ("activity_log.py", "ACTION_FA"),
        "گزارش مالی": ("finance.py", "show_dashboard"),
        "نقش و دسترسی": ("permissions.py", "PERMISSIONS"),
        "امتیاز سخت‌گیرانه": ("occasions.py", "cap_points"),
        # ---- فاز ۱۲-ب ----
        "دستاوردها": ("club.py", "check_achievements"),
        "فروشگاه پاداش": ("club.py", "do_buy"),
        "جدول رتبه‌بندی": ("club.py", "show_leaderboard"),
        "تیکت پشتیبانی": ("tickets.py", "init_ticket_tables"),
        # ---- فاز ۱۳ ----
        "منوی خلوت ادمین": ("bale_api.py", "kb_notify_menu"),
        "منوی مدیریتی جدا": ("bale_api.py", "BTN_USER_VIEW"),
        "قفل مالی سوپرادمین": ("permissions.py", "can_section"),
        "پرداخت با امتیاز": ("payments.py", "points_quote"),
        "پرداخت در محل": ("payments.py", "start_onsite_payment"),
        "پرداخت چند روشی": ("payments.py", "show_method_choice"),
        # ---- فاز ۱۴ ----
        "قرعه‌کشی": ("lottery.py", "run_draw"),
        "جوایز قرعه‌کشی": ("lottery.py", "LOTTERY_SCHEMA"),
        "داشبورد ۹ گزارش": ("reports.py", "show_dashboard"),
        "دوره زمانی گزارش": ("reports.py", "PERIODS"),
        # ---- فاز ۱۵ ----
        "فرم تک‌مرحله‌ای پیش‌فرض": ("forms.py", "one_by_one"),
        "قفل نمایش مبلغ": ("events.py", "def show_price"),
        "دستیار ثبت‌نام رویداد": ("events.py", "REG_MODES"),
        "مرور تنظیمات رویداد": ("events.py", "REVIEW_TOGGLES"),
        "مرور تنظیمات فرم": ("forms.py", "FORM_REVIEW"),
        "گواهینامه و کارت فرم": ("form_fill.py", "send_id_card"),
        "غیبت مجاز": ("attendance.py", "EXCUSE_SCHEMA"),
        # ---- فاز ۱۶ ----
        "فرم سریع رویداد": ("events.py", "QUICK_FIELDS"),
        "۴ روش فرم ثبت‌نام": ("events.py", "REG_MODES"),
        "اتصال دوطرفه فرم": ("events.py", "_link_form"),
        "کارمزد درگاه": ("payments.py", "calc_fee"),
        # ---- فاز ۱۷ ----
        "کارمزد چندروشی": ("payments.py", "FEE_METHODS"),
        "پرداخت غیرمتمرکز": ("paylink.py", "init_paylink_tables"),
        "لینک پرداخت": ("paylink.py", "link_url"),
        "ویرایش پروفایل کاربر": ("admin.py", "PROFILE_EDIT_FIELDS"),
        "اطلاع‌رسانی به همه": ("admin.py", "_ALL_WHERE"),
        "وبهوک فرم": ("form_fill.py", "_fire_webhook"),
        "گردش کار": ("form_reports.py", "show_approvals"),
        # ---- فاز ۱۷-ج ----
        "واحد یکسان ریال": ("config.py", 'MONEY_UNIT = "rial"'),
        "پارامتر پروفایل": ("profile.py", "active_steps"),
        "صندوق دریافت": ("tickets.py", "show_inbox"),
        "مخفی‌سازی هزینه": ("events.py", "hide_cost_hint"),
        "متن OTP قابل ویرایش": ("settings_admin.py", "msg_otp_sent"),
        # ---- فاز ۱۸-الف ----
        "امکانات ویژه فرم": ("forms.py", "TYPE_FEATURES"),
        "زمان‌سنج آزمون": ("form_fill.py", "_check_deadline"),
        "ترتیب تصادفی سوال": ("form_fill.py", "_ordered_fields"),
        "دسترسی فرم": ("forms.py", "VISIBILITY"),
        "اتصال فرم به بخش": ("forms.py", "FORM_SECTIONS"),
        "پرداخت فرم‌ساز": ("payments.py", "def mark_paid"),
        "مقصد پرداخت": ("payments.py", "def pay_target"),
        "روش پرداخت جایگزین": ("payments.py", "best_available_method"),
        "پرداخت اقساطی": ("payplan.py", "PLAN_MODES"),
        "زمان‌بندی اقساط": ("payplan.py", "def split_amount"),
        "یادآوری قسط": ("payplan.py", "check_due_reminders"),
        "پارامتر سفارشی پروفایل": ("profile.py", "def custom_fields"),
        "افزودن پارامتر پروفایل": ("admin.py", "def add_param"),
        "دکمه سوال قبل": ("form_fill.py", "go_prev_question"),
        # ---- فاز ۱۸-ب ----
        "درباره ما": ("about.py", "ABOUT_BLOCKS"),
        "پشتیبانی جامع": ("about.py", "SUPPORT_BLOCKS"),
        "همکاری با ما": ("about.py", "def show_join"),
        "شبکه‌های اجتماعی": ("about.py", "SOCIAL_KINDS"),
        "معرفی تیم": ("about.py", "def show_team"),
        "هشدار فیلترشکن": ("payments.py", "VPN_WARN_METHODS"),
        "استثنای کارت و امتیاز": ("payments.py", "VPN_SKIP_METHODS"),
        # ---- فاز ۱۸-ج ----
        "هویت ربات پویا": ("config.py", "def bot_name"),
        "نمایش نام ربات": ("config.py", "def show_bot_name"),
        "پنل هویت": ("about.py", "def show_identity"),
        "آمار قابل تنظیم": ("about.py", "STAT_ITEMS"),
        "فهرست کامل پشتیبانی": ("about.py", "def _stats_line"),
        # ---- فاز ۱۸-د ----
        "بک‌آپ خودکار": ("database.py", "def auto_backup"),
        "صحت‌سنجی بک‌آپ": ("database.py", "def _verify_backup"),
        "بک‌آپ روزانه": ("database.py", "def _keep_daily"),
        "پنل بک‌آپ": ("admin.py", "def show_backup_panel"),
        "یادآوری اقساط فعال": ("main.py", "check_due_reminders()"),
        "امکانات ویژه در ویزارد": ("forms.py", "امکان ویژه دارد"),
        # ---- فاز ۱۹ — گواهینامه ----
        "قالب ورد گواهینامه": ("certgen.py", "def fill_docx"),
        "تشخیص پارامتر": ("certgen.py", "PLACEHOLDERS"),
        "تبدیل به PDF": ("certgen.py", "def docx_to_pdf"),
        "تبدیل به تصویر": ("certgen.py", "def pdf_to_png"),
        "کیوآر اعتبارسنجی": ("certgen.py", "def make_qr"),
        "قالب تصویری": ("certgen.py", "def render_on_image"),
        "اعتبارسنجی گواهینامه": ("main.py", "def verify_certificate"),
        "پنل قالب گواهینامه": ("certgen.py", "def show_panel"),
        # ---- فاز ۱۹-ب ----
        "پارامترهای ریز گواهینامه": ("certgen.py", "PH_GROUPS"),
        "چند امضا": ("certgen.py", "sign_img3"),
        "تصاویر گواهینامه": ("certgen.py", "def all_assets"),
        "اندازه تصاویر": ("certgen.py", "def image_mm"),
        "پاکسازی خودکار": ("certgen.py", "def cleanup_files"),
        "بازتولید گواهینامه": ("certgen.py", "def regenerate"),
        "تنظیمات گواهینامه و بلیط": ("certgen.py", "CERT_SETTINGS"),
        "خطاب خودکار": ("certgen.py", "gender_title"),
        # ---- فاز ۱۹-ج ----
        "تشخیص عکس کیوآر": ("certgen.py", "def looks_like_qr"),
        "PNG بدون لیبره‌آفیس": ("certgen.py", "def docx_to_png_fallback"),
        "موتور ورد ویندوز": ("certgen.py", "def _word_com_to_pdf"),
        "راهنمای نصب": ("certgen.py", "def install_guide"),
        # ---- فاز ۲۰ ----
        "پنل تبلیغات": ("ads.py", "AD_TYPES"),
        "کمپین A/B": ("ads.py", "def ab_winner"),
        "ردیابی کلیک": ("ads.py", "def click"),
        "لغو اشتراک تبلیغ": ("ads.py", "def set_optout"),
        "ساعت سکوت": ("ads.py", "def in_quiet_hours"),
        "سقف روزانه تبلیغ": ("ads.py", "def got_enough_today"),
        "کمپین زمان‌بندی‌شده": ("ads.py", "def check_scheduled"),
        "چیدمان نمای کاربر": ("about.py", "LAYOUTS"),
        "روشن/خاموش گروهی": ("about.py", "def show_bulk"),
        "هاب گواهینامه": ("certgen.py", "def show_hub"),
        "بلیط جامع": ("certgen.py", "def build_ticket_text"),
        # ---- فاز ۲۱ ----
        "تشخیص هوشمند لیبره": ("certgen.py", "def _lo_candidates"),
        "رجیستری ویندوز": ("certgen.py", "def _lo_from_registry"),
        "عیب‌یابی موتور": ("certgen.py", "def lo_diagnose"),
        "تست واقعی تبدیل": ("certgen.py", "def engine_test"),
        "PNG مستقیم لیبره": ("certgen.py", "def docx_to_png_lo"),
        "مسیر دستی لیبره": ("certgen.py", "cert_soffice_path"),
        # ---- فاز ۲۲ ----
        "مرکز صدور گواهینامه": ("certissue.py", "def show_hub"),
        "شرط دریافت گواهینامه": ("certissue.py", "CONDITIONS"),
        "انتخاب قالب رویداد": ("certissue.py", "def template_of"),
        "پارامتر گواهینامه رویداد": ("certissue.py", "EVENT_PARAMS"),
        "پیش‌نمایش گواهینامه": ("certissue.py", "def preview"),
        "ابطال گواهینامه": ("certissue.py", "def revoke"),
        "ارسال فایل گواهینامه": ("certissue.py", "def send_cert_files"),
        "غیبت موجه حساب شود": ("certissue.py", "def excused_counts"),
        "فهرست غایبان": ("attendance.py", "def show_absent"),
        "یادآوری به غایبان": ("attendance.py", "def remind_absent"),
        "چهار وضعیت حضور": ("attendance.py", "ATT_STATUS_FA"),
        "تغییر روش ثبت حضور": ("attendance.py", "def show_methods"),
        "تنظیمات جلسه": ("attendance.py", "SESSION_FIELDS"),
        "حاضر کردن همه": ("attendance.py", "def mark_all"),
        "آمار دقیق جلسه": ("attendance.py", "def session_stats"),
        # ---- فاز ۲۳ ----
        "صورتحساب یکپارچه": ("form_fill.py", "def build_invoice"),
        "تأیید قبل از پرداخت": ("form_fill.py", "def go_pay"),
        "انتخاب چند مورد": ("form_fill.py", "def toggle_item"),
        "تأیید چند مورد": ("form_fill.py", "def confirm_items"),
        "دسترسی بعد از ثبت": ("forms.py", "AFTER_SUBMIT"),
        "انصراف بدون حذف": ("form_fill.py", "def withdraw_response"),
        "قوانین هر نوع فرم": ("forms.py", "TERMS_BY_TYPE"),
        "انتشار فوری عمومی": ("forms.py", "def publish_form"),
        "اطلاع‌رسانی فرم": ("forms.py", "def notify_users"),
        "منوی مرتب رویداد": ("events.py", "def show_event_settings"),
        "بیشتر رویداد": ("events.py", "def show_event_more"),
        "راهنمای قدم بعدی": ("events.py", "def _next_step_tip"),
        # ---- فاز ۲۴ ----
        "تشخیص کیوآر رنگی": ("certgen.py", "def _trim_border"),
        "نام‌های کیوآر": ("certgen.py", "_FUZZY_ROOTS"),
        "ادامه پرداخت نیمه‌تمام": ("events.py", "def resume_payment"),
        "شروع دوباره ثبت‌نام": ("events.py", "def restart_registration"),
        "هزینه زیرساخت": ("infra_fee.py", "INFRA_SETTINGS"),
        "برچسب رایگان زیرساخت": ("infra_fee.py", "def price_label"),
        "پنل زیرساخت": ("infra_fee.py", "def show_panel"),
        # ---- فاز ۲۵ ----
        "کالبدشکافی قالب": ("certgen.py", "def diagnose_template"),
        "تست ساخت گواهینامه": ("certgen.py", "def test_build"),
        "PDF بدون تگ": ("certgen.py", "UseTaggedPDF"),
        "PDF به تصویر با لیبره": ("certgen.py", "def pdf_to_png_lo"),
        # ---- فاز ۲۶ ----
        "بلیط تصویری فرم": ("ticket.py", "def build_for_response"),
        "بلوک‌های بلیط": ("ticket.py", "BLOCKS"),
        "چیدمان بلیط": ("ticket.py", "def layout"),
        "پالت بلیط": ("ticket.py", "PALETTES"),
        "اندازه بلیط": ("ticket.py", "SIZES"),
        "لوگوی بلیط": ("ticket.py", "def show_assets"),
        "پس‌زمینه بلیط": ("ticket.py", "tkf_bgimg_mode"),
        "پیش‌نمایش بلیط": ("ticket.py", "def preview"),
        # ---- فاز ۲۷ ----
        "اعداد فارسی گواهینامه": ("certgen.py", "def fa_digits"),
        "تراز پاراگراف ورد": ("certgen.py", "def _par_align"),
        "سبک متن ورد": ("certgen.py", "def _run_style"),
        "تصویر درون پاراگراف": ("certgen.py", "def _par_images"),
        "پخش محتوا در صفحه": ("certgen.py", "cert_png_stretch"),
        # ---- فاز ۲۸ — فونت و نام ----
        "موتور RAQM بلیط": ("ticket.py", "def _has_raqm"),
        "رسم راست‌به‌چپ بلیط": ("ticket.py", "def _draw_txt"),
        "فونت پررنگ بلیط": ("ticket.py", "def _font"),
        "پاکسازی نام": ("ticket.py", "def clean_name"),
        "سبک نوشتن نام": ("ticket.py", "def styled_name"),
        "سبک‌های نام": ("ticket.py", "NAME_STYLES"),
        "متن و فونت بلیط": ("ticket.py", "def show_text"),
        "موتور RAQM گواهینامه": ("certgen.py", "def _has_raqm"),
        "رسم امن گواهینامه": ("certgen.py", "def _safe_text"),
        "جهت متن گواهینامه": ("certgen.py", "def fa_text_kw"),
        # ---- فاز ۲۹ — فضای سفید و کیوآر ----
        "برش حاشیهٔ سفید": ("certgen.py", "def trim_page_margin"),
        "کیوآر همیشه‌درج": ("certgen.py", "def _append_orphan_images"),
        "ابعاد صفحه در تشخیص": ("certgen.py", '"pw_mm"'),
        "تنظیم برش حاشیه": ("certgen.py", "cert_trim_margin"),
        "تنظیم تصویر اجباری": ("certgen.py", "cert_force_images"),
        # ---- فاز ۳۰ — تفکیک درآمد ----
        "تجمیع درآمد": ("finance.py", "def _agg"),
        "ریز کارمزد": ("finance.py", "def show_fees"),
        "تفکیک کامل درآمد": ("finance.py", "def show_breakdown"),
        "گزارش دوره‌ای": ("finance.py", "def show_period"),
        "تفکیک منبع درآمد": ("finance.py", "def _by_source"),
        "تفکیک روش پرداخت": ("finance.py", "def _by_method"),
        "جداسازی زیرساخت": ("finance.py", "def _infra_split"),
        # ---- فاز ۳۱ — لینک عمیق ----
        "لینک عمیق مرکزی": ("config.py", "def deep_link"),
        "یوزرنیم از env": ("config.py", "BOT_USERNAME_ENV"),
        "دامنه قابل تنظیم": ("config.py", "BALE_DOMAIN"),
        "کش وابسته به توکن": ("settings_admin.py", "def _uname_key"),
        # ---- فاز ۳۲ — کیوآر شناور و چند گواهینامه ----
        "کیوآر شناور": ("certgen.py", "def _add_floating_image"),
        "تنظیم پس‌زمینه": ("certgen.py", "def _fit_background"),
        "موقعیت تصویر": ("certgen.py", "FLOAT_POS"),
        "چند گواهینامه رویداد": ("eventcert.py", "def list_certs"),
        "شرط مستقل گواهینامه": ("eventcert.py", "def eligible"),
        "تبلیغ گواهینامه": ("eventcert.py", "def ad_lines"),
        "پنل کاربر گواهینامه": ("eventcert.py",
                                "def user_panel_lines"),
        "صدور گروهی اکسل": ("certbatch.py", "def parse_excel"),
        "لینک اشتراکی گواهینامه": ("certbatch.py", "def batch_link"),
        "تطبیق هویت دسته": ("certbatch.py", "def find_row"),
        "دریافت با لینک": ("certbatch.py", "def handle_claim"),
        # ---- فاز ۳۳ — فرم رویدادی · نظرسنجی · حضور آنلاین ----
        "دسترسی فرم رویداد": ("forms.py", "def event_form_gate"),
        "سطوح دسترسی رویداد": ("forms.py", "EV_ACCESS"),
        "جلسات خودکار": ("attendance_auto.py", "def ensure_sessions"),
        "تقویم شمسی جلسه": ("attendance_auto.py",
                            "def _jalali_add_days"),
        "روش‌های آنلاین": ("attendance_auto.py", "ONLINE_METHODS"),
        "رمز پویا": ("attendance_auto.py", "def rotating_code"),
        "لینک یک‌بارمصرف حضور": ("attendance_auto.py",
                                 "def issue_token"),
        "فراخوان حضور": ("attendance_auto.py", "def start_rollcall"),
        "ماندگاری جلسه": ("attendance_auto.py", "def total_seconds"),
        "موتور نظرسنجی": ("survey.py", "def send_survey"),
        "یادآوری نظرسنجی": ("survey.py", "def remind"),
        "تحلیل نظرسنجی": ("survey.py", "def analyze"),
        "شاخص NPS": ("survey.py", "def _nps"),
        "گزارش نظرسنجی": ("survey.py", "def show_report"),
        # ---- فاز ۳۴ — استعلام دولایه و اعتبار ----
        "شناسهٔ دولایه": ("certverify.py", "def build_full_code"),
        "کد فردی گواهینامه": ("certverify.py", "def new_person_code"),
        "ثبت شناسه": ("certverify.py", "def stamp"),
        "استعلام سه‌راهه": ("certverify.py", "def find"),
        "اعتبار زمانی": ("certverify.py", "def add_months"),
        "گزارش استعلام": ("certverify.py", "def report"),
        "هشدار انقضا": ("certverify.py", "def warn_expiring"),
        "تنظیم اعتبار": ("certgen.py", "cert_valid_months"),
        "شماره نامه قالب": ("certgen.py", '"doc_no"'),
        # ---- فاز ۳۵ — جای کیوآر و تک‌صفحه‌ماندن ----
        "لنگر صفحهٔ اول": ("certgen.py", "def _first_body_paragraph"),
        "نگهبان تک‌صفحه": ("certgen.py", "def _drop_trailing_blanks"),
        "جای کادر قالب": ("certgen.py", "def _textbox_anchor"),
        "پاکسازی جای‌نما": ("certgen.py", "def _strip_placeholder_text"),
        "تنظیم تک‌صفحه": ("certgen.py", "cert_one_page"),
        "تنظیم جای قالب": ("certgen.py", "cert_pos_from_tpl"),
        "پشتیبانی کادر VML": ("certgen.py", "urn:schemas-microsoft-com:vml"),
        "شمارندهٔ گواهینامه": ("certissue.py", "_brand_new"),
        # ---- فاز ۳۶ — مرکز صدور · شمسی · عکس ----
        "تاریخ شمسی یکپارچه": ("jalali.py", "def fmt"),
        "تبدیل شمسی↔میلادی": ("jalali.py", "def j2g"),
        "افزودن ماه شمسی": ("jalali.py", "def add_months"),
        "مرکز صدور": ("certcenter.py", "def create_issue"),
        "کشف پارامتر قالب": ("certcenter.py", "def template_fields"),
        "گیرنده از رویداد": ("certcenter.py", "def fill_from_event"),
        "گیرنده از دسته": ("certcenter.py", "def fill_from_segment"),
        "گیرنده از اکسل": ("certcenter.py", "def fill_from_rows"),
        "پیش‌نمایش تصادفی": ("certcenter.py", "def preview"),
        "انتشار طرح": ("certcenter.py", "def publish"),
        "ساخت تنبل": ("certcenter.py", "def build_one"),
        "صف دریافت کاربر": ("certcenter.py", "def pending_for"),
        "لینک دریافت": ("certcenter.py", "def claim_by_link"),
        "عکس پرسنلی": ("certphoto.py", "def photo_for"),
        "آدمک پیش‌فرض": ("certphoto.py", "def make_silhouette"),
        "شرط تأیید عکس": ("certphoto.py", "def photo_approved"),
        "رفع اکسل": ("certbatch.py", "get_file_info"),
        # ---- فاز ۳۷ — یکپارچگی همهٔ مسیرها ----
        "ارسال با شناسه": ("certissue.py",
                            "isinstance(cert, (int, float, str))"),
        "عکس مشترک": ("certphoto.py", "def attach"),
        "عکس در رویداد": ("certissue.py", "_cp.attach(mp, bale_uid"),
        "عکس در چند گواهینامه": ("eventcert.py", "_cp.attach(mp, uid"),
        "عکس در بازتولید": ("certgen.py", "_cp.attach(mp, cert_row"),
        "سریال در دیتابیس": ("eventcert.py",
                              "UPDATE certificates SET serial=?"),
        "شمارنده در اکسل": ("certbatch.py", "total_certificates="),
        "شمارنده در چند گواهینامه": ("eventcert.py", "total_certificates="),
        "شمارش زندهٔ پروفایل": ("profile.py",
                                 "COUNT(*) AS n FROM certificates"),
        "انقضا در فهرست": ("attendance.py", "منقضی شده در"),
        "میان‌بر رویداد": ("certcenter.py", "def from_event"),
        "شناسه در بازتولید": ("certgen.py",
                               '("verify_code", "person_code")'),
        "اعتبار پیش‌فرض ۲۴": ("certgen.py",
                               'get_setting("cert_valid_months", "24")'),
        # ---- فاز ۳۸ — پروفایل: عکس · رسانه · منوی مرتب ----
        "عکس یک پارامتر شد": ("profile.py", '"key": "profile_photo"'),
        "انواع رسانه": ("profile.py", "MEDIA_TYPES = {"),
        "تشخیص مرحلهٔ رسانه": ("profile.py", "def is_media_step"),
        "متن پرسش قابل تغییر": ("profile.py", "def prompt_of"),
        "ثبت متن پرسش": ("profile.py", "def set_prompt"),
        "نوع پارامتر": ("profile.py", "def field_type"),
        "عکس در فرم": ("profile.py", "def handle_form_photo"),
        "ذخیرهٔ مشترک عکس": ("profile.py", "def _save_photo_file"),
        "صفحهٔ پارامتر": ("admin.py", "def show_param_edit"),
        "ویرایش متن پرسش": ("admin.py", "def start_param_text"),
        "افزودن پرسش دلخواه": ("admin.py", "def start_new_param"),
        "افزودن پرسش رسانه‌ای": ("admin.py", "def start_new_media"),
        "پاک‌کردن کش تنظیم": ("admin.py", "def _forget_setting"),
        "منوی پروفایل مرتب": ("bale_api.py", "def kb_profile"),
        # ---- فاز ۳۹ — مرکز صدور بازطراحی‌شده ----
        "رفع باگ ورودی متن": ("main.py", 'state_name.startswith("cc_")'),
        "دستهٔ هر نفر": ("certcenter.py", "PER_PERSON = {"),
        "دستهٔ سیستمی": ("certcenter.py", "SYSTEM_KEYS = {"),
        "تشخیص دستهٔ پارامتر": ("certcenter.py", "def field_kind"),
        "پر کردن پشت‌سرهم": ("certcenter.py", "def wizard_start"),
        "افزودن دستی": ("certcenter.py", "def manual_input"),
        "جستجوی کاربران": ("certcenter.py", "def search_input"),
        "نمونهٔ اکسل": ("certcenter.py", "def send_sample_excel"),
        "چهار روش انتشار": ("certcenter.py", "PUBLISH_WAYS = {"),
        "خروجی یکجا": ("certcenter.py", "def export_all"),
        "قفل صدور خودسرویس": ("certissue.py",
                               "def self_issue_allowed"),
        "پیام رد صدور": ("certissue.py", "def deny_self_issue"),
        "قفل در حضور": ("attendance.py", "_ci.self_issue_allowed()"),
        "قفل در رویداد": ("eventcert.py", "self_issue_allowed"),
        "مرکز در مدیریت کاربران": ("bale_api.py",
                                    '"callback_data": "cc_home"'),
        # ---- فاز ۴۰ — رفع باگ‌های اسکن ----
        "امتیاز حضور خودکار": ("attendance_auto.py", "_award_points"),
        "امتیاز نظرسنجی": ("survey.py", "_award_points"),
        "نگهبان شناسه": ("main.py", "_NUM_ONLY_PREFIXES"),
        "پیام شناسهٔ نامعتبر": ("main.py", "def _bad_id"),
        "ابزار مشترک": ("helpers.py", "def guard_admin"),
        "تبدیل امن عدد": ("helpers.py", "def num_or"),
        "بستن حضور باز": ("attendance.py", "close_open_presence"),
        "پیشوند سریال": ("attendance.py", "cert_serial_prefix"),
        "کنترل خروجی": ("certgen.py", 'cert_out_png'),
        "لینک از تنظیمات": ("certcenter.py", 'get_setting("cc_link_on"'),
        "تأخیر اعلان": ("certcenter.py", "_t.sleep"),
        "ساخت فوری اختیاری": ("certcenter.py", "cc_lazy_build"),
        "لایهٔ دوم فرم": ("forms.py", "def show_advanced2"),
    }
    result = {}
    for name, (fname, marker) in markers.items():
        fp = BASE / fname
        try:
            result[name] = marker in fp.read_text(encoding="utf-8")
        except Exception:
            result[name] = False
    return result


# ==================== ۴) بررسی وبهوک ====================
def ensure_polling_mode(log_fn=print):
    """
    🔴 حیاتی: اگر وبهوک فعال باشد، getUpdates هیچ آپدیتی نمی‌دهد.
    این تابع خودکار وبهوک را حذف می‌کند.
    """
    try:
        from bale_api import get_webhook_info, delete_webhook
    except Exception:
        return True, "بررسی نشد"

    info = get_webhook_info()
    if not info.get("ok"):
        return True, "بررسی وبهوک ممکن نشد (احتمالاً مشکلی نیست)"

    url = (info.get("result") or {}).get("url") or ""
    if not url:
        return True, "وبهوک خالی است ✅"

    log_fn(f"⚠️ وبهوک فعال است: {url}")
    log_fn("🔧 در حال حذف خودکار (وگرنه هیچ پیامی دریافت نمی‌شود)...")
    r = delete_webhook()
    if r.get("ok"):
        log_fn("✅ وبهوک حذف شد — حالا polling کار می‌کند")
        return True, f"وبهوک {url} حذف شد"
    return False, (
        f"❌ حذف وبهوک ناموفق: {r.get('description')}\n"
        f"   تا وقتی وبهوک فعال است، ربات هیچ پیامی نمی‌گیرد!"
    )


# ==================== ۵) تشخیص رقیب ====================
def detect_competitor(log_fn=print, samples=3):
    """
    تشخیص اینکه آیا نمونه دیگری از ربات همین توکن را poll می‌کند.

    روش: چند بار getUpdates با timeout کوتاه می‌زنیم.
    اگر آپدیتی که دیدیم بلافاصله ناپدید شود، یعنی رقیبی هست.
    """
    try:
        from bale_api import get_updates
    except Exception:
        return False, "بررسی نشد"

    seen = set()
    dup = 0
    for _ in range(samples):
        r = get_updates(offset=None, timeout=1)
        if not r.get("ok"):
            continue
        for u in r.get("result") or []:
            uid = u.get("update_id")
            if uid in seen:
                dup += 1
            seen.add(uid)
        time.sleep(0.4)

    # اگر آپدیت‌ها بین دو نمونه تقسیم شوند، الگو نامنظم می‌شود
    if len(seen) > 0 and dup == 0 and samples > 1:
        return True, (
            "⚠️ احتمال وجود نمونه دیگری از ربات\n"
            "   آپدیت‌ها ناپایدار هستند"
        )
    return False, "رقیبی شناسایی نشد"
