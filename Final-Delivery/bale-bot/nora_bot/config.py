"""
تنظیمات ربات نورا - نسخه 5.0
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent


# ==================== بارگذاری .env ====================
def _load_env():
    env_file = BASE_DIR / ".env"
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        return
    except ImportError:
        pass

    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        print(f"⚠️ خطا در خواندن .env: {e}")


_load_env()


def _int_env(name, default=0):
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        print(f"⚠️ مقدار {name} عدد نیست: {raw}")
        return default


def _bool_env(name, default=False):
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on", "بله")


# ==================== بله ====================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
SUPER_ADMIN_ID = _int_env("SUPER_ADMIN_ID", 0)

# 🏷️ هویت ربات — مقدار پایه از .env، ولی از پنل ادمین قابل تغییر است
#    (به bot_name() / org_name() در پایین همین فایل نگاه کنید)
BOT_NAME_ENV = os.getenv("BOT_NAME", "نورا")
ORG_NAME_ENV = os.getenv("ORG_NAME", "گروه فرهنگی و اجتماعی خط زندگی")
BOT_NAME = BOT_NAME_ENV
ORG_NAME = ORG_NAME_ENV
VERSION = "5.0"

API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
FILE_URL = f"https://tapi.bale.ai/file/bot{BOT_TOKEN}"

# قرارداد اتصال به API مشترک وب‌اپ؛ تا پیکربندی نشود، هیچ مسیر محلی جایگزین نمی‌شود.
SHARED_API_URL = (os.getenv("NORA_SHARED_API_URL") or "").strip().rstrip("/")
SHARED_API_TOKEN = (os.getenv("NORA_BOT_SERVICE_TOKEN") or "").strip()
SHARED_API_TIMEOUT_SECONDS = _int_env("NORA_SHARED_API_TIMEOUT_SECONDS", 8)


def shared_api_url_error(value):
    """کد خطای کوتاه اگر نشانی پایه‌ی API مشترک قابل‌استفاده نباشد، وگرنه رشته‌ی خالی.

    نشانی پایه فقط باید «مبدأ» باشد (طرح + میزبان، و در صورت نیاز درگاه).
    کلاینت‌ها خودشان مسیر ``/api/...`` را اضافه می‌کنند؛ پس نشانی‌ای که از قبل
    مسیر، query یا fragment دارد رد می‌شود تا درخواستِ نادرست ساخته نشود.
    مجوز به http فقط برای میزبان محلی داده می‌شود تا توسعه‌ی محلی ممکن بماند.
    """
    value = (value or "").strip()
    if not value:
        return "shared_api_url_missing"
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return "shared_api_url_invalid"
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    secure_scheme = parsed.scheme.lower() == "https"
    local_http = parsed.scheme.lower() == "http" and (parsed.hostname or "").lower() in local_hosts
    if (
        not (secure_scheme or local_http)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path.rstrip("/") != ""
        or parsed.query
        or parsed.fragment
    ):
        return "shared_api_url_invalid"
    return ""


def is_valid_webapp_url(value):
    """The Mini App uses the existing public site on a verified HTTPS origin."""
    if not isinstance(value, str) or not value or any(char.isspace() or ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme.lower() == "https"
        and parsed.netloc
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and "?" not in value
        and "#" not in value
        and parsed.hostname.lower() != "localhost"
    )


_WEBAPP_URL_RAW = (os.getenv("NORA_WEBAPP_URL") or "").strip()
NORA_WEBAPP_URL = _WEBAPP_URL_RAW.rstrip("/") if is_valid_webapp_url(_WEBAPP_URL_RAW) else ""
NORA_WEBAPP_URL_INVALID = bool(_WEBAPP_URL_RAW and not NORA_WEBAPP_URL)


def bot_id_from_token():

    """شناسه عددی بات اصلی (بخش قبل از دونقطه در توکن)"""
    if BOT_TOKEN and ":" in BOT_TOKEN:
        head = BOT_TOKEN.split(":", 1)[0]
        if head.isdigit():
            return int(head)
    return 0


MAIN_BOT_ID = bot_id_from_token()


# ══════════════════════════════════════════════════════════
# 🔗 لینک‌های عمیق — منبع حقیقت واحد
#
# 🎯 «بعدا شاید توکن و آیدی بات عوض کنم پس حواست به اون
#     موردم باشه — به سورس ای ان وی دقت کن تو لینکا»
#
# 🔴 مشکلی که رفع شد:
#    یوزرنیم ربات یک بار از API خوانده و در دیتابیس ذخیره
#    می‌شد. بعدش **هرگز** به‌روز نمی‌شد. یعنی اگر آیدی ربات
#    را عوض می‌کردید، همهٔ کیوآرکدها و لینک‌ها به آیدی قبلی
#    اشاره می‌کردند و کار نمی‌کردند.
#
# ✅ حالا سه لایه، به همین ترتیب:
#      ۱) BOT_USERNAME در .env    ← بالاترین اولویت
#      ۲) تنظیم bot_username در پنل
#      ۳) getMe از API (کش‌شده)
#
#    و مهم‌تر: اگر توکن عوض شود، کش خودکار باطل می‌شود
#    (چون کلید کش شامل شناسهٔ عددی توکن است).
# ══════════════════════════════════════════════════════════
BOT_USERNAME_ENV = (os.getenv("BOT_USERNAME", "") or "").strip().lstrip("@")

# 🌐 دامنهٔ پیام‌رسان — اگر روزی عوض شد، فقط همین یک خط
BALE_DOMAIN = (os.getenv("BALE_DOMAIN", "https://ble.ir")
               or "https://ble.ir").strip().rstrip("/")


def bot_username(ask_api=True):
    """
    🏷️ یوزرنیم ربات — بدون @

    ترتیب: .env ← تنظیم پنل (وابسته به توکن) ← getMe

    ask_api=False فقط منابع محلی را می‌خواند (بدون تماس شبکه).
    """
    if BOT_USERNAME_ENV:
        return BOT_USERNAME_ENV
    try:
        from database import get_setting
        # 🔑 کلید کش شامل شناسهٔ توکن است تا با عوض شدن توکن
        #    خودکار باطل شود
        key = f"bot_username_{MAIN_BOT_ID}" if MAIN_BOT_ID else "bot_username"
        v = (get_setting(key, "") or "").strip().lstrip("@")
        if v:
            return v
    except Exception:
        pass
    if ask_api:
        # 🌐 آخرین راه: از خود بله بپرس (نتیجه ذخیره می‌شود)
        try:
            from settings_admin import get_bot_username as _g
            return (_g() or "").strip().lstrip("@")
        except Exception:
            pass
    return ""


def deep_link(payload=""):
    """
    🔗 لینک عمیق کامل — با اسکن، ربات باز می‌شود.

    نمونه:
        deep_link("cert_A3F9")  →  https://ble.ir/mybot?start=cert_A3F9
        deep_link()             →  https://ble.ir/mybot

    اگر یوزرنیم معلوم نباشد، رشتهٔ خالی برمی‌گرداند تا
    فراخوان بتواند تصمیم بگیرد (نه لینک نصفه‌نیمه).
    """
    u = bot_username()
    if not u:
        return ""
    base = f"{BALE_DOMAIN}/{u}"
    return f"{base}?start={payload}" if payload else base


# ==================== سفیر — رمز یکبار مصرف ====================
# ⚠️ نکته حیاتی:
#   bot_id سفیر معمولاً با شناسه بات اصلی شما فرق دارد!
#   این همان باتی است که در پنل کسب‌وکار بله برای ارسال OTP ثبت کرده‌اید
#   و نامش پای پیام رمز یکبار مصرف نمایش داده می‌شود.
#   حتماً آن را دستی در .env بنویسید — هرگز از روی BOT_TOKEN حدس زده نمی‌شود.
SAFIR_API_KEY = (os.getenv("SAFIR_API_KEY") or "").strip()
SAFIR_BOT_ID = _int_env("SAFIR_BOT_ID", 0)
SAFIR_URL = os.getenv("SAFIR_URL", "https://safir.bale.ai/api/v3/send_message")

# بعضی نسخه‌های سفیر فیلد request_id را نمی‌پذیرند.
# اگر 1 باشد ارسال می‌شود؛ در صورت خطا خودکار بدون آن دوباره تلاش می‌شود.
SAFIR_SEND_REQUEST_ID = _bool_env("SAFIR_SEND_REQUEST_ID", True)

SAFIR_ENABLED = bool(SAFIR_API_KEY and SAFIR_BOT_ID)


# ==================== پرداخت کیف پول بله ====================
# توکن پرداخت کیف‌پولی از @botfather
# برای تست: WALLET-TEST-1111111111111111
PAYMENT_PROVIDER_TOKEN = (os.getenv("PAYMENT_PROVIDER_TOKEN") or "").strip()
PAYMENT_ENABLED = bool(PAYMENT_PROVIDER_TOKEN)
PAYMENT_TEST_MODE = PAYMENT_PROVIDER_TOKEN.upper().startswith("WALLET-TEST")
# ==================== 💱 واحد پول ====================
"""
🔴 قانون طلایی پول در ربات نورا — «همه‌جا ریال»

  • ادمین وارد می‌کند   →  ریال
  • دیتابیس ذخیره می‌کند →  ریال
  • کاربر می‌بیند        →  ریال
  • به درگاه بله می‌رود   →  ریال

⚠️ هیچ تبدیل واحدی در هیچ نقطه‌ای از کد وجود ندارد.
   عددی که ادمین می‌نویسد، همان عددی است که در دیتابیس می‌نشیند،
   همان عددی که به کاربر نشان داده می‌شود و همان عددی که به
   درگاه بله می‌رود. بنابراین «یک صفر اضافه/کم» غیرممکن است.

📌 چرا؟ درگاه بله فقط ریال می‌پذیرد. تا وقتی یک لایه تبدیل
   (تومان↔ریال) وسط بود، هر تابعی که یادش می‌رفت تبدیل کند
   یک صفر جابه‌جا می‌کرد. با حذف کامل تبدیل، این دسته باگ
   از ریشه از بین می‌رود.
"""
CURRENCY_LABEL = os.getenv("CURRENCY_LABEL", "ریال")

# 🔒 واحد پول قفل شده روی ریال — تغییرش ندهید
MONEY_UNIT = "rial"

# فقط برای مهاجرت یک‌باره تنظیمات قدیمی که تومان ذخیره شده بودند
RIAL_PER_TOMAN = 10


def money(rial, with_unit=True):
    """
    💰 نمایش مبلغ — ورودی ریال، خروجی ریال (بدون هیچ تبدیلی).

    این تنها تابع نمایش پول در کل ربات است؛ بقیه ماژول‌ها
    (events.fmt_money · payments.fmt · forms.fmt_amount) همگی
    به همین تابع وصل‌اند تا هرگز دو جای مختلف دو عدد نشان ندهند.

    مثال: money(5000000) → '5,000,000 ریال'
    """
    try:
        s = f"{int(rial or 0):,}"
    except (TypeError, ValueError):
        s = "0"
    return f"{s} {CURRENCY_LABEL}" if with_unit else s


def money_rial(rial, with_unit=True):
    """هم‌معنیِ money() — برای سازگاری با کدهای قدیمی"""
    return money(rial, with_unit)


def parse_money(text):
    """
    📥 مبلغی که ادمین وارد کرده → ریال (بدون تبدیل).

    عددی که تایپ می‌شود عیناً ذخیره می‌شود.
    """
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())
    if not digits:
        return 0
    try:
        return int(digits)
    except (TypeError, ValueError):
        return 0


def to_rial(value):
    """🔁 سازگاری — دیگر تبدیلی انجام نمی‌شود (همه‌چیز ریال است)"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_toman(value):
    """
    🔁 سازگاری — دیگر تبدیلی انجام نمی‌شود.

    ⚠️ منسوخ: از money() استفاده کنید. عدد را دست‌نخورده برمی‌گرداند
    تا اگر جایی از قلم افتاد، مبلغ اشتباه نمایش داده نشود.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


# 🛡️ محافظت‌های پرداخت واقعی
PAYMENT_MAX_AMOUNT = _int_env("PAYMENT_MAX_AMOUNT", 50_000_000)
PAYMENT_MIN_AMOUNT = _int_env("PAYMENT_MIN_AMOUNT", 10_000)
PAYMENT_TEST_AMOUNT = _int_env("PAYMENT_TEST_AMOUNT", 10_000)
PAYMENT_CONFIRM = _bool_env("PAYMENT_CONFIRM", True)


def check_amount(rial):
    """
    بررسی مبلغ قبل از ارسال فاکتور.
    خروجی: (ok, پیام خطا)
    🔴 با توکن واقعی، اشتباه تایپی = پول واقعی!
    """
    try:
        a = int(rial)
    except (TypeError, ValueError):
        return False, "مبلغ نامعتبر است"
    if a < PAYMENT_MIN_AMOUNT:
        return False, (f"مبلغ کمتر از حداقل مجاز است\n"
                       f"حداقل: {money(PAYMENT_MIN_AMOUNT)}")
    if a > PAYMENT_MAX_AMOUNT:
        return False, (f"⛔ مبلغ بیش از سقف مجاز!\n"
                       f"مبلغ وارد شده: {money(a)}\n"
                       f"سقف: {money(PAYMENT_MAX_AMOUNT)}\n\n"
                       f"💡 اگر عمدی است، PAYMENT_MAX_AMOUNT را در .env بالا ببرید")
    return True, ""


# ══════════════════════════════════════════════════════════
# 🏷️ فاز ۱۸-ج — هویت ربات قابل تنظیم از پنل ادمین
#
# 🎯 «هویت ربات هم من بتونم تنظیم کنم تو تنظیمات که مثلا کلا اسم
#     نورا باشه یا نباشه یا هرچیزی که من تنظیم میکنم تغییر کنه»
#
# ⚠️ چرا تابع و نه متغیر ساده؟
#    اگر مقدار را موقع import بخوانیم، بعد از تغییر در پنل باید ربات
#    ری‌استارت شود. با تابع، تغییر بلافاصله همه‌جا اعمال می‌شود.
#
# ⚠️ چرا import داخل تابع؟
#    database خودش از config می‌خواند → import حلقوی می‌شود.
# ══════════════════════════════════════════════════════════
def _identity(key, fallback):
    """خواندن یک مقدار هویتی از تنظیمات، با بازگشت امن به .env"""
    try:
        from database import get_setting
        v = (get_setting(key, "") or "").strip()
        if v:
            return v
    except Exception:
        pass
    return fallback


def bot_name():
    """🤖 نام ربات — از پنل ادمین قابل تغییر"""
    return _identity("id_bot_name", BOT_NAME_ENV)


def org_name():
    """🏢 نام مجموعه — از پنل ادمین قابل تغییر"""
    return _identity("id_org_name", ORG_NAME_ENV)


def show_bot_name():
    """
    آیا نام ربات در متن‌ها نمایش داده شود؟

    🎯 «مثلا کلا اسم نورا باشه یا نباشه»
    اگر خاموش باشد، عبارت «ربات نورا» به «ربات» تبدیل می‌شود.
    """
    try:
        from database import get_setting
        return get_setting("id_show_bot_name", "1") == "1"
    except Exception:
        return True


def brand(with_bot=True):
    """
    🏷️ برند نمایشی — همان چیزی که کاربر می‌بیند.

    مثال‌ها:
      نام روشن  → «ربات نورا»
      نام خاموش → «ربات»
    """
    if with_bot and show_bot_name():
        nm = bot_name()
        if nm:
            return f"ربات {nm}"
    return "ربات"


# ==================== ری‌اکشن (لایک خودکار) ====================
# روی هر پیام کاربر عادی (نه ادمین) خودکار 👍 گذاشته می‌شود
AUTO_REACT_ENABLED = _bool_env("AUTO_REACT_ENABLED", True)
AUTO_REACT_EMOJI = os.getenv("AUTO_REACT_EMOJI", "❤️")
# فقط برای کاربران عادی، نه ادمین‌ها
AUTO_REACT_ADMINS = _bool_env("AUTO_REACT_ADMINS", False)


# ==================== فرم رضایت‌سنجی ====================
ASK_REVIEW_ENABLED = _bool_env("ASK_REVIEW_ENABLED", True)
ASK_REVIEW_DELAY = _int_env("ASK_REVIEW_DELAY", 5)


# ==================== مسیرها ====================
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "nora.db"))
BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))
IMPORT_DIR = os.getenv("IMPORT_DIR", str(BASE_DIR / "imports"))
FILES_DIR = os.getenv("FILES_DIR", str(BASE_DIR / "files"))
PROFILES_DIR = os.getenv("PROFILES_DIR", str(BASE_DIR / "files" / "profiles"))
EVENTS_DIR = os.getenv("EVENTS_DIR", str(BASE_DIR / "files" / "events"))
LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))


# ==================== رفتار سیستم ====================
OTP_TTL_MINUTES = _int_env("OTP_TTL_MINUTES", 3)
OTP_MAX_ATTEMPTS = _int_env("OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_SECONDS = _int_env("OTP_RESEND_SECONDS", 90)
STATE_TTL_MINUTES = _int_env("STATE_TTL_MINUTES", 120)

MAX_BACKUPS = _int_env("MAX_BACKUPS", 20)

# ══════════════════════════════════════════════════════════
# 💾 فاز ۱۸-د — بک‌آپ خودکار
#
# 🎯 «اتوماتیک داره سیو میکنه دیگه؟ بکاپ بگیره و حافظش از بین
#     نره با هر آپدیت»
#
# 🔴 قبلاً فقط موقع استارت ربات بک‌آپ گرفته می‌شد. اگر ربات
#    هفته‌ها بالا می‌ماند، هیچ بک‌آپ تازه‌ای وجود نداشت.
# ══════════════════════════════════════════════════════════
# هر چند ساعت یک‌بار بک‌آپ خودکار؟ (۰ = خاموش)
AUTO_BACKUP_HOURS = _int_env("AUTO_BACKUP_HOURS", 6)

# چند بک‌آپ روزانه نگه داشته شود (جدا از MAX_BACKUPS)
KEEP_DAILY_BACKUPS = _int_env("KEEP_DAILY_BACKUPS", 7)
MAX_IMPORT_MB = _int_env("MAX_IMPORT_MB", 10)
USERS_PER_PAGE = _int_env("USERS_PER_PAGE", 5)
EVENTS_PER_PAGE = _int_env("EVENTS_PER_PAGE", 5)

STRICT_NATIONAL_ID = _bool_env("STRICT_NATIONAL_ID", False)
FORCE_JOIN_FAIL_OPEN = _bool_env("FORCE_JOIN_FAIL_OPEN", True)

# سرعت ارسال همگانی (پیام در ثانیه)
BROADCAST_RATE = _int_env("BROADCAST_RATE", 20)


def check_config():
    """بررسی تنظیمات — لیست خطاها"""
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN تنظیم نشده (فایل .env)")
    elif ":" not in BOT_TOKEN:
        errors.append("BOT_TOKEN فرمت درستی ندارد (باید مثل 123456789:xxxx باشد)")
    if not SUPER_ADMIN_ID:
        errors.append("SUPER_ADMIN_ID تنظیم نشده (آیدی عددی شما در بله)")
    if not SHARED_API_URL:
        errors.append("NORA_SHARED_API_URL تنظیم نشده؛ اتصال پایگاه مشترک لازم است")
    elif shared_api_url_error(SHARED_API_URL) == "shared_api_url_invalid":
        errors.append(
            "NORA_SHARED_API_URL فقط باید مبدأ باشد (مثل https://example.com) "
            "بدون /api؛ مسیر /api را خودِ ربات اضافه می‌کند"
        )
    if len(SHARED_API_TOKEN) < 32:
        errors.append("NORA_BOT_SERVICE_TOKEN تنظیم نشده یا کوتاه است")
    if NORA_WEBAPP_URL_INVALID:
        errors.append("NORA_WEBAPP_URL باید نشانی HTTPS معتبرِ وب‌اپ باشد")
    return errors


def config_warnings():
    """هشدارهای غیربحرانی"""
    w = []
    if SAFIR_API_KEY and not SAFIR_BOT_ID:
        w.append("SAFIR_API_KEY هست ولی SAFIR_BOT_ID تنظیم نشده → OTP کار نمی‌کند")
    if SAFIR_BOT_ID and not SAFIR_API_KEY:
        w.append("SAFIR_BOT_ID هست ولی SAFIR_API_KEY تنظیم نشده → OTP کار نمی‌کند")
    if SAFIR_ENABLED and SAFIR_BOT_ID == MAIN_BOT_ID:
        w.append(
            f"SAFIR_BOT_ID ({SAFIR_BOT_ID}) با شناسه بات اصلی یکی است. "
            "معمولاً بات OTP جداست — اگر کد ارسال نشد این را بررسی کنید."
        )
    if not PAYMENT_ENABLED:
        w.append("PAYMENT_PROVIDER_TOKEN تنظیم نشده → رویدادهای پولی غیرفعال است")
    elif PAYMENT_TEST_MODE:
        w.append("توکن پرداخت آزمایشی است (WALLET-TEST) → پولی جابه‌جا نمی‌شود")
    else:
        w.append("🔴 توکن پرداخت واقعی است — پرداخت‌ها واقعی خواهند بود! "
                 f"(سقف هر تراکنش: {PAYMENT_MAX_AMOUNT:,} {CURRENCY_LABEL})")
    return w
