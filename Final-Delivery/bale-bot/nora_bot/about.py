"""
ℹ️ درباره ما و پشتیبانی — فاز ۱۸-ب

درخواست کاربر:
  «قسمت پشتیبانی و درباره ما رو در منو کاربر خیلی بهتر کن، جامع و
   کاملش کن... درباره ما هم همکاری با ما بزار، بعد فرم همکاری با ما
   رو من بتونم بهش وصل کنم و بقیه چیز های درباره ما مثل شبکه های
   اجتماعی و گروه و معرفی اشخاص. البته همه این بخش ها در قسمت
   مرتبطش در پنل ادمین قابل فعالسازی و غیرفعالسازی و تنظیم باشد»

معماری:
  ℹ️ درباره ما          💬 پشتیبانی
  ├── 📖 معرفی           ├── 🎫 تیکت من
  ├── 🎯 اهداف           ├── ➕ تیکت جدید
  ├── 👥 تیم ما          ├── ❓ سوالات متداول
  ├── 🤝 همکاری با ما    ├── 💬 پیام مستقیم
  ├── 🌐 شبکه‌های اجتماعی ├── 📞 راه‌های تماس
  ├── 📞 تماس با ما      └── 🕐 ساعات پاسخگویی
  └── 📊 دستاوردها

هر بلوک مستقل روشن/خاموش می‌شود و متنش از پنل ادمین ویرایش‌پذیر است.
"""
import json

from config import bot_name, org_name, brand
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    set_state, get_state_data, clear_state, log_action,
    is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK

STATE_AB_TEXT = "ab_text"
STATE_AB_LINK = "ab_link"
STATE_AB_PERSON = "ab_person"

# ══════════════════════════════════════════════════════════
# 📦 بلوک‌های «درباره ما» — هرکدام مستقل قابل تنظیم
#    (کلید, آیکن, نام, کلید متن, پیش‌فرض روشن؟)
# ══════════════════════════════════════════════════════════
ABOUT_BLOCKS = [
    ("intro",    "📖", "معرفی ما",          "ab_intro",     1),
    ("mission",  "🎯", "اهداف و ماموریت",   "ab_mission",   1),
    ("team",     "👥", "تیم ما",            None,           1),
    ("join",     "🤝", "همکاری با ما",      "ab_join",      1),
    ("social",   "🌐", "شبکه‌های اجتماعی",  None,           1),
    ("contact",  "📞", "راه‌های تماس",      "ab_contact",   1),
    ("achieve",  "🏆", "دستاوردها",         "ab_achieve",   0),
    ("rules",    "📜", "قوانین و حریم خصوصی", "ab_rules",   0),
]

SUPPORT_BLOCKS = [
    ("ticket",   "🎫", "تیکت پشتیبانی",     None,           1),
    ("faq",      "❓", "سوالات متداول",     "msg_faq",      1),
    ("direct",   "💬", "پیام مستقیم به ما", None,           1),
    ("hours",    "🕐", "ساعات پاسخگویی",    "ab_hours",     1),
    ("guide",    "📚", "راهنمای استفاده",   "ab_guide",     0),
]

# شبکه‌های اجتماعی پشتیبانی‌شده
SOCIAL_KINDS = {
    "bale_channel": {"icon": "📢", "name": "کانال بله"},
    "bale_group":   {"icon": "👥", "name": "گروه بله"},
    "instagram":    {"icon": "📸", "name": "اینستاگرام"},
    "telegram":     {"icon": "✈️", "name": "تلگرام"},
    "whatsapp":     {"icon": "💚", "name": "واتساپ"},
    "website":      {"icon": "🌍", "name": "وب‌سایت"},
    "eitaa":        {"icon": "🟠", "name": "ایتا"},
    "rubika":       {"icon": "🟣", "name": "روبیکا"},
    "youtube":      {"icon": "▶️", "name": "یوتیوب"},
    "linkedin":     {"icon": "💼", "name": "لینکدین"},
    "email":        {"icon": "📧", "name": "ایمیل"},
    "phone":        {"icon": "☎️", "name": "تلفن"},
}

PEOPLE_SCHEMA = {
    "name": "TEXT",
    "role": "TEXT",
    "bio": "TEXT",
    "photo_file_id": "TEXT",
    "contact": "TEXT",
    "sort_order": "INTEGER DEFAULT 0",
    "is_active": "INTEGER DEFAULT 1",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

LINKS_SCHEMA = {
    "kind": "TEXT",
    "title": "TEXT",
    "url": "TEXT",
    "sort_order": "INTEGER DEFAULT 0",
    "is_active": "INTEGER DEFAULT 1",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_about_tables():
    from database import ensure_table
    ensure_table("about_people", PEOPLE_SCHEMA)
    ensure_table("about_links", LINKS_SCHEMA)
    seed_about_texts()
    log("✅ جدول‌های درباره ما آماده شد")


DEFAULT_TEXTS = [
    ("ab_intro", "📖 معرفی ما",
     "به خانواده {org} خوش آمدید 💚\n\n"
     "ما جمعی از دوستداران فرهنگ و اجتماع هستیم که با هم مسیر "
     "یادگیری و رشد را می‌پیماییم.\n\n"
     "اینجا جای شماست — برای آموختن، برای دوستی، برای همراهی."),
    ("ab_mission", "🎯 اهداف و ماموریت",
     "🎯 اهداف ما\n\n"
     "🌱 گسترش آگاهی و فرهنگ در جامعه\n"
     "🤝 ایجاد فضایی گرم برای هم‌افزایی\n"
     "📚 برگزاری دوره‌ها و رویدادهای اثرگذار\n"
     "💚 همراهی با کسانی که می‌خواهند رشد کنند\n\n"
     "باور داریم هر قدم کوچک، تغییری بزرگ می‌سازد."),
    ("ab_join", "🤝 همکاری با ما",
     "🤝 دست شما را به گرمی می‌فشاریم\n\n"
     "اگر دوست دارید کنار ما باشید — چه به‌عنوان مدرس، "
     "چه داوطلب، چه همراه — خوشحال می‌شویم.\n\n"
     "فرم زیر را پر کنید تا با شما تماس بگیریم 💚"),
    ("ab_contact", "📞 راه‌های تماس",
     "📞 در دسترس شماییم\n\n"
     "هر سوال، پیشنهاد یا انتقادی دارید بگویید.\n"
     "پیام‌های شما را با دقت می‌خوانیم 💚"),
    ("ab_hours", "🕐 ساعات پاسخگویی",
     "🕐 ساعات پاسخگویی\n\n"
     "شنبه تا چهارشنبه: ۹ صبح تا ۵ عصر\n"
     "پنجشنبه: ۹ صبح تا ۱ ظهر\n\n"
     "💡 پیام‌ها را بیرون از این ساعت‌ها هم دریافت می‌کنیم و "
     "در اولین فرصت پاسخ می‌دهیم."),
    ("ab_achieve", "🏆 دستاوردها",
     "🏆 مسیری که با هم پیموده‌ایم\n\n"
     "هر رویداد، هر لبخند، هر تجربه مشترک — دستاورد ماست."),
    ("ab_rules", "📜 قوانین و حریم خصوصی",
     "📜 قوانین و حریم خصوصی\n\n"
     "🔒 اطلاعات شما نزد ما امانت است و هرگز در اختیار "
     "شخص ثالث قرار نمی‌گیرد.\n\n"
     "🤝 با احترام متقابل، فضای گرمی برای همه می‌سازیم."),
    ("ab_guide", "📚 راهنمای استفاده",
     "📚 راهنمای ربات\n\n"
     "🎉 رویدادها — دیدن و ثبت‌نام در برنامه‌ها\n"
     "👤 پروفایل من — تکمیل اطلاعات و دیدن بلیت‌ها\n"
     "📝 فرم‌ها — پر کردن فرم‌های فعال\n"
     "💬 پشتیبانی — هر سوالی داشتید بپرسید\n\n"
     "اگر جایی گیر کردید، همین‌جا به ما بگویید 💚"),
]


def seed_about_texts():
    for key, title, default in DEFAULT_TEXTS:
        if not db_execute("SELECT key FROM settings WHERE key=?", (key,),
                          fetch="one"):
            set_setting(key, default, title, "about")
    # بلوک‌ها پیش‌فرض روشن/خاموش
    for key, _, _, _, on in ABOUT_BLOCKS + SUPPORT_BLOCKS:
        k = f"ab_on_{key}"
        if not db_execute("SELECT key FROM settings WHERE key=?", (k,),
                          fetch="one"):
            set_setting(k, str(on), f"نمایش بخش {key}", "about")


def block_on(key):
    return get_setting(f"ab_on_{key}", "1") == "1"


def _txt(key, default=""):
    """
    متن یک بلوک — با جایگزینی هویت پویا.

    🏷️ فاز ۱۸-ج: {bot} {org} {brand} در متن‌ها پشتیبانی می‌شوند تا
       با تغییر نام ربات در پنل، همه متن‌ها خودکار به‌روز شوند.
    """
    t = (get_setting(key, "") or default).strip()
    if not t:
        return t
    return (t.replace("{org}", org_name())
             .replace("{brand}", brand())
             .replace("{bot}", bot_name()))


def get_links(active_only=True):
    w = " WHERE is_active=1" if active_only else ""
    return db_execute(f"SELECT * FROM about_links{w} "
                      f"ORDER BY sort_order, id", fetch="all") or []


def get_people(active_only=True):
    w = " WHERE is_active=1" if active_only else ""
    return db_execute(f"SELECT * FROM about_people{w} "
                      f"ORDER BY sort_order, id", fetch="all") or []


def _section_forms(section_key):
    """فرم‌های متصل به یک بخش (مثل همکاری با ما)"""
    try:
        from forms import forms_for_section
        return forms_for_section(section_key)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════
# 👤 نمای کاربر
# ══════════════════════════════════════════════════════════
def _stats_line():
    """
    📊 آمار زنده — هر شاخص جداگانه از پنل قابل روشن/خاموش شدن.

    🎯 «تعداد نفرات و رویدادها رو تو پنل بتونم تنظیم کنم که نشون بده یا نه»
    """
    if get_setting("ab_show_stats", "1") != "1":
        return ""
    parts = []
    try:
        if get_setting("ab_stat_users", "1") == "1":
            n = db_scalar("SELECT COUNT(*) FROM users") or 0
            if n > 1:
                parts.append(f"👥 {n} همراه")
        if get_setting("ab_stat_events", "1") == "1":
            n = db_scalar("SELECT COUNT(*) FROM events "
                          "WHERE status='published'") or 0
            if n:
                parts.append(f"🎉 {n} رویداد")
        if get_setting("ab_stat_forms", "0") == "1":
            n = db_scalar("SELECT COUNT(*) FROM forms "
                          "WHERE status='active'") or 0
            if n:
                parts.append(f"📝 {n} فرم")
        if get_setting("ab_stat_certs", "0") == "1":
            n = db_scalar("SELECT COUNT(*) FROM certificates") or 0
            if n:
                parts.append(f"🎓 {n} گواهینامه")
    except Exception:
        return ""
    return "  ·  ".join(parts)


# 🎛️ چیدمان نمای کاربر — از پنل ادمین قابل تغییر
LAYOUTS = {
    "compact": {"icon": "📱", "name": "خلاصه (۲ دکمه)",
                "desc": "فقط «درباره ما» و «پشتیبانی» — تمیزترین"},
    "grouped": {"icon": "🗂️", "name": "گروهی (پیشنهادی)",
                "desc": "دسته‌بندی‌شده، نه شلوغ نه خلوت"},
    "full":    {"icon": "📋", "name": "کامل",
                "desc": "همه گزینه‌ها یکجا"},
}


def layout():
    v = get_setting("ab_layout", "grouped")
    return v if v in LAYOUTS else "grouped"


def _forms_buttons(limit=2):
    """دکمه فرم‌های متصل به بخش‌های پشتیبانی"""
    out = []
    for skey, icon in (("support", "📝"), ("feedback", "💡"),
                       ("donation", "❤️"), ("volunteer", "🙌"),
                       ("membership", "🎗️")):
        for f in _section_forms(skey)[:limit]:
            out.append([{"text": f"{icon} {f.get('title')}"[:34],
                         "callback_data": f"ffstart_{f['id']}"}])
    return out


def show_hub(cid, uid):
    """
    💬 صفحه اصلی: پشتیبانی و درباره ما

    🎯 فاز ۲۰: چیدمان مرتب و قابل انتخاب.
       قبلاً تا ۱۵ دکمه پشت‌سرهم می‌آمد و «پخش و پلا» بود.
    """
    lay = layout()
    lines = ["💬 پشتیبانی و درباره ما", "━━━━━━━━━━━━━━", "",
             f"💚 {org_name()}"]

    intro = _txt("ab_intro")
    if intro:
        lines += ["", intro.split("\n")[0][:130]]

    st = _stats_line()
    if st:
        lines += ["", st]

    # 🎫 اگر تیکت باز دارد، همین بالا ببیند
    open_n = 0
    try:
        open_n = db_scalar(
            "SELECT COUNT(*) FROM tickets WHERE bale_user_id=? "
            "AND status IN ('open','answered')", (uid,)) or 0
    except Exception:
        pass
    if open_n:
        lines += ["", f"🎫 شما {open_n} تیکت باز دارید"]

    lines += ["", "چطور می‌توانیم کمکتان کنیم؟"]

    # ═══ چیدمان خلاصه ═══
    if lay == "compact":
        btns = [[{"text": "ℹ️ درباره ما", "callback_data": "ab_about"},
                 {"text": "💬 پشتیبانی", "callback_data": "ab_support"}]]
        if block_on("join"):
            btns.append([{"text": "🤝 همکاری با ما",
                          "callback_data": "ab_join"}])
        btns.append([{"text": "🏠 منوی اصلی",
                      "callback_data": "back_main"}])
        return send_or_edit(cid, "\n".join(lines),
                            {"inline_keyboard": btns})

    # ═══ چیدمان گروهی (پیش‌فرض) ═══
    if lay == "grouped":
        btns = [[{"text": "ℹ️ درباره ما", "callback_data": "ab_about"},
                 {"text": "💬 پشتیبانی", "callback_data": "ab_support"}]]
        row = []
        if block_on("join"):
            row.append({"text": "🤝 همکاری با ما",
                        "callback_data": "ab_join"})
        if block_on("social") and get_links():
            row.append({"text": "🌐 شبکه‌ها", "callback_data": "ab_social"})
        if row:
            btns.append(row)
        # فرم‌های ویژه که ادمین وصل کرده
        btns += _forms_buttons(limit=1)[:2]
        btns.append([{"text": "🏠 منوی اصلی",
                      "callback_data": "back_main"}])
        return send_or_edit(cid, "\n".join(lines),
                            {"inline_keyboard": btns})

    # ═══ چیدمان کامل ═══
    btns = []
    about_row = []
    if block_on("intro"):
        about_row.append({"text": "ℹ️ درباره ما",
                          "callback_data": "ab_about"})
    if block_on("mission") and _txt("ab_mission"):
        about_row.append({"text": "🎯 اهداف ما",
                          "callback_data": "ab_mission"})
    if about_row:
        btns.append(about_row)

    row = []
    if block_on("team") and get_people():
        row.append({"text": "👥 تیم ما", "callback_data": "ab_team"})
    if block_on("join"):
        row.append({"text": "🤝 همکاری", "callback_data": "ab_join"})
    if row:
        btns.append(row)

    row = []
    if block_on("social") and get_links():
        row.append({"text": "🌐 شبکه‌ها", "callback_data": "ab_social"})
    if block_on("achieve") and _txt("ab_achieve"):
        row.append({"text": "🏆 دستاوردها", "callback_data": "ab_achieve"})
    if row:
        btns.append(row)

    sup = []
    if block_on("ticket"):
        sup.append({"text": "🎫 تیکت‌های من", "callback_data": "tk_my"})
        sup.append({"text": "➕ تیکت جدید", "callback_data": "tk_new"})
    if sup:
        btns.append(sup)
    if block_on("direct"):
        btns.append([{"text": "💬 پیام مستقیم به ما",
                      "callback_data": "u_contact"}])

    row = []
    if block_on("faq"):
        row.append({"text": "❓ سوالات متداول", "callback_data": "u_faq"})
    if block_on("guide") and _txt("ab_guide"):
        row.append({"text": "📚 راهنما", "callback_data": "ab_guide"})
    if row:
        btns.append(row)

    row = []
    if block_on("contact"):
        row.append({"text": "📞 تماس", "callback_data": "ab_contact"})
    if block_on("hours") and _txt("ab_hours"):
        row.append({"text": "🕐 ساعات", "callback_data": "ab_hours"})
    if row:
        btns.append(row)

    if block_on("rules") and _txt("ab_rules"):
        btns.append([{"text": "📜 قوانین و حریم خصوصی",
                      "callback_data": "ab_rules"}])

    btns += _forms_buttons(limit=2)
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_about(cid, uid):
    """ℹ️ درباره ما"""
    lines = [f"ℹ️ درباره {org_name()}", "━━━━━━━━━━━━━━", ""]
    intro = _txt("ab_intro")
    lines.append(intro if intro else brand())

    btns = []
    if block_on("mission") and _txt("ab_mission"):
        btns.append([{"text": "🎯 اهداف و ماموریت",
                      "callback_data": "ab_mission"}])
    if block_on("team") and get_people():
        btns.append([{"text": "👥 تیم ما", "callback_data": "ab_team"}])
    if block_on("join"):
        btns.append([{"text": "🤝 همکاری با ما", "callback_data": "ab_join"}])
    if block_on("social") and get_links():
        btns.append([{"text": "🌐 شبکه‌های اجتماعی",
                      "callback_data": "ab_social"}])
    if block_on("achieve") and _txt("ab_achieve"):
        btns.append([{"text": "🏆 دستاوردها", "callback_data": "ab_achieve"}])
    if block_on("contact"):
        btns.append([{"text": "📞 راه‌های تماس", "callback_data": "ab_contact"}])
    if block_on("rules") and _txt("ab_rules"):
        btns.append([{"text": "📜 قوانین و حریم خصوصی",
                      "callback_data": "ab_rules"}])

    # 📊 آمار زنده — هر شاخص از پنل قابل تنظیم
    st = _stats_line()
    if st:
        lines += ["", "━━━━━━━━━━━━━━", st]

    btns.append([{"text": "💬 پشتیبانی", "callback_data": "ab_support"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "u_support"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_text_block(cid, uid, key):
    """نمایش یک بلوک متنی ساده"""
    mapping = {b[0]: b[3] for b in ABOUT_BLOCKS + SUPPORT_BLOCKS if b[3]}
    sk = mapping.get(key)
    if not sk:
        return show_about(cid, uid)
    if not block_on(key):
        return send(cid, "ℹ️ این بخش فعلاً در دسترس نیست")
    txt = _txt(sk) or "—"
    back = "ab_support" if key in {b[0] for b in SUPPORT_BLOCKS} \
        else "ab_about"
    send_or_edit(cid, txt, {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": back}]]})


def show_team(cid, uid):
    """👥 تیم ما"""
    if not block_on("team"):
        return show_about(cid, uid)
    people = get_people()
    if not people:
        return send_or_edit(cid, "👥 تیم ما\n\n🌱 به‌زودی معرفی می‌شوند.",
                            {"inline_keyboard": [
                                [{"text": "🔙 بازگشت",
                                  "callback_data": "ab_about"}]]})
    lines = ["👥 تیم ما", "━━━━━━━━━━━━━━", ""]
    for p in people:
        lines.append(f"▫️ {p.get('name') or '—'}")
        if p.get("role"):
            lines.append(f"   {p['role']}")
        if p.get("bio"):
            lines.append(f"   {str(p['bio'])[:120]}")
        if p.get("contact"):
            lines.append(f"   📩 {p['contact']}")
        lines.append("")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "ab_about"}]]})


def show_social(cid, uid):
    """🌐 شبکه‌های اجتماعی"""
    if not block_on("social"):
        return show_about(cid, uid)
    links = get_links()
    if not links:
        return send_or_edit(cid, "🌐 به‌زودی اینجا می‌بینیدمان 💚",
                            {"inline_keyboard": [
                                [{"text": "🔙 بازگشت",
                                  "callback_data": "ab_about"}]]})
    lines = ["🌐 ما را دنبال کنید", "━━━━━━━━━━━━━━", "",
             "خوشحال می‌شویم آنجا هم کنارتان باشیم 💚", ""]
    btns = []
    for l in links:
        k = SOCIAL_KINDS.get(l.get("kind") or "website",
                             {"icon": "🔗", "name": "لینک"})
        title = l.get("title") or k["name"]
        url = (l.get("url") or "").strip()
        lines.append(f"{k['icon']} {title}")
        if url.startswith("http"):
            btns.append([{"text": f"{k['icon']} {title}"[:34], "url": url}])
        elif url:
            lines[-1] += f" — {url}"
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_about"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_join(cid, uid):
    """🤝 همکاری با ما — با فرم متصل"""
    if not block_on("join"):
        return show_about(cid, uid)
    txt = _txt("ab_join") or "🤝 همکاری با ما"
    forms = _section_forms("join_us")

    btns = []
    if forms:
        for f in forms[:5]:
            btns.append([{"text": f"📝 {f.get('title')}"[:34],
                          "callback_data": f"ffstart_{f['id']}"}])
    else:
        txt += ("\n\n💡 فعلاً فرم همکاری فعال نیست — "
                "می‌توانید مستقیم پیام بدهید.")
        btns.append([{"text": "💬 ارسال پیام", "callback_data": "u_contact"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_about"}])
    send_or_edit(cid, txt, {"inline_keyboard": btns})


def show_support(cid, uid):
    """💬 پشتیبانی"""
    lines = ["💬 پشتیبانی", "━━━━━━━━━━━━━━", "",
             "هر سوال یا مشکلی دارید، همین‌جا بگویید.",
             "با کمال میل کمکتان می‌کنیم 💚", ""]

    open_n = 0
    try:
        open_n = db_scalar("SELECT COUNT(*) FROM tickets WHERE bale_user_id=? "
                           "AND status IN ('open','answered')", (uid,)) or 0
    except Exception:
        pass
    if open_n:
        lines.append(f"🎫 شما {open_n} تیکت باز دارید")
        lines.append("")

    hours = _txt("ab_hours")
    if block_on("hours") and hours:
        lines.append(hours.split("\n\n")[0] if "\n\n" in hours else hours)

    btns = []
    if block_on("ticket"):
        btns.append([{"text": "🎫 تیکت‌های من", "callback_data": "tk_my"},
                     {"text": "➕ تیکت جدید", "callback_data": "tk_new"}])
    if block_on("direct"):
        btns.append([{"text": "💬 پیام مستقیم به ما",
                      "callback_data": "u_contact"}])

    row = []
    if block_on("faq"):
        row.append({"text": "❓ سوالات متداول", "callback_data": "u_faq"})
    if block_on("guide") and _txt("ab_guide"):
        row.append({"text": "📚 راهنما", "callback_data": "ab_guide"})
    if row:
        btns.append(row)

    row = []
    if block_on("hours") and hours:
        row.append({"text": "🕐 ساعات پاسخگویی",
                    "callback_data": "ab_hours"})
    if block_on("contact"):
        row.append({"text": "📞 تماس", "callback_data": "ab_contact"})
    if row:
        btns.append(row)

    # فرم‌های متصل به بخش پشتیبانی
    for _sk, _ic in (("support", "📝"), ("feedback", "💡")):
        for f in _section_forms(_sk)[:2]:
            btns.append([{"text": f"{_ic} {f.get('title')}"[:34],
                          "callback_data": f"ffstart_{f['id']}"}])

    btns.append([{"text": "ℹ️ درباره ما", "callback_data": "ab_about"},
                 {"text": "🔙 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_contact(cid, uid):
    """📞 راه‌های تماس"""
    if not block_on("contact"):
        return show_about(cid, uid)
    lines = [_txt("ab_contact") or "📞 راه‌های تماس", ""]
    btns = []
    for l in get_links():
        if l.get("kind") in ("phone", "email", "whatsapp"):
            k = SOCIAL_KINDS.get(l["kind"], {})
            lines.append(f"{k.get('icon','▫️')} {l.get('title') or ''} "
                         f"{l.get('url') or ''}")
    btns.append([{"text": "💬 ارسال پیام مستقیم",
                  "callback_data": "u_contact"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_about"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ⚙️ پنل ادمین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def show_admin(cid, uid):
    """⚙️ تنظیمات درباره ما و پشتیبانی"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    n_people = db_scalar("SELECT COUNT(*) FROM about_people "
                         "WHERE is_active=1") or 0
    n_links = db_scalar("SELECT COUNT(*) FROM about_links "
                        "WHERE is_active=1") or 0
    n_join = len(_section_forms("join_us"))

    lines = [
        "ℹ️ درباره ما و پشتیبانی", "━━━━━━━━━━━━━━", "",
        "هر بخش را می‌توانید روشن/خاموش و متنش را ویرایش کنید.", "",
        f"👥 اعضای تیم: {n_people}",
        f"🌐 لینک‌ها: {n_links}",
        f"🤝 فرم‌های همکاری متصل: {n_join}", "",
        "📌 وضعیت بخش‌ها:", "",
    ]
    btns = []
    for key, icon, name, skey, _ in ABOUT_BLOCKS:
        on = block_on(key)
        lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
        row = [{"text": f"{'✅' if on else '❌'} {icon} {name}"[:28],
                "callback_data": f"abt_{key}"}]
        if skey:
            row.append({"text": "✏️", "callback_data": f"abe_{key}"})
        btns.append(row)

    lines.append("")
    lines.append("💬 بخش‌های پشتیبانی:")
    for key, icon, name, skey, _ in SUPPORT_BLOCKS:
        on = block_on(key)
        lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
        row = [{"text": f"{'✅' if on else '❌'} {icon} {name}"[:28],
                "callback_data": f"abt_{key}"}]
        if skey:
            row.append({"text": "✏️", "callback_data": f"abe_{key}"})
        btns.append(row)

    btns.append([{"text": "👥 مدیریت تیم", "callback_data": "ab_people"},
                 {"text": "🌐 لینک‌ها", "callback_data": "ab_links"}])
    btns.append([{"text": "🤝 اتصال فرم همکاری",
                  "callback_data": "ab_joinform"}])
    btns.append([{"text": "📊 آمار نمایشی", "callback_data": "ab_stats"},
                 {"text": "🏷️ هویت ربات", "callback_data": "ab_identity"}])
    _l = LAYOUTS[layout()]
    btns.append([{"text": f"🎛️ چیدمان: {_l['icon']} {_l['name']}"[:34],
                  "callback_data": "ab_layout"}])
    btns.append([{"text": "⚡ روشن/خاموش گروهی",
                  "callback_data": "ab_bulk"}])
    btns.append([{"text": "👁️ پیش‌نمایش کاربر",
                  "callback_data": "ab_preview"}])
    btns.append([{"text": "🔙 پشتیبانی و باشگاه",
                  "callback_data": "admin_care"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# 📊 فاز ۱۸-ج — تنظیم آمار نمایشی
#
# 🎯 «تعداد نفرات و رویدادها رو تو پنل بتونم تنظیم کنم که نشون بده یا نه»
# ══════════════════════════════════════════════════════════
STAT_ITEMS = [
    ("users",  "👥", "تعداد کاربران", "ab_stat_users", "1"),
    ("events", "🎉", "تعداد رویدادها", "ab_stat_events", "1"),
    ("forms",  "📝", "تعداد فرم‌های فعال", "ab_stat_forms", "0"),
    ("certs",  "🎓", "تعداد گواهینامه‌ها", "ab_stat_certs", "0"),
]


def show_stats_admin(cid, uid):
    """📊 کدام آمار به کاربر نشان داده شود؟"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    master = get_setting("ab_show_stats", "1") == "1"
    lines = [
        "📊 آمار نمایشی در «درباره ما»", "━━━━━━━━━━━━━━", "",
        f"وضعیت کلی: {'🟢 روشن' if master else '🔴 خاموش'}", "",
        "تعیین کنید کدام عددها به کاربر نشان داده شود:", "",
    ]
    btns = [[{"text": f"📊 نمایش آمار: {'✅ روشن' if master else '❌ خاموش'}",
              "callback_data": "abt_stats"}]]

    if master:
        for key, icon, name, skey, dflt in STAT_ITEMS:
            on = get_setting(skey, dflt) == "1"
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} {name}"[:32],
                          "callback_data": f"abst_{key}"}])
        prev = _stats_line()
        lines += ["", "👁️ پیش‌نمایش:",
                  f"   {prev if prev else '— چیزی نمایش داده نمی‌شود —'}"]
    else:
        lines.append("💡 با روشن کردن، می‌توانید هر شاخص را جدا تنظیم کنید.")

    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_admin"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_stat(cid, uid, key):
    """روشن/خاموش کردن یک شاخص آماری"""
    if not _guard(cid, uid):
        return
    item = next((x for x in STAT_ITEMS if x[0] == key), None)
    if not item:
        return send(cid, "❌ نامعتبر")
    _, _, name, skey, dflt = item
    cur = get_setting(skey, dflt) == "1"
    set_setting(skey, "0" if cur else "1", f"نمایش {name}", "about", uid)
    return show_stats_admin(cid, uid)


# ══════════════════════════════════════════════════════════
# 🎛️ فاز ۲۰ — چیدمان نمای کاربر
# ══════════════════════════════════════════════════════════
def show_layout(cid, uid, pick=None):
    """🎛️ ادمین انتخاب می‌کند کاربر چطور ببیند"""
    if not _guard(cid, uid):
        return
    if pick:
        if pick not in LAYOUTS:
            return send(cid, "❌ نامعتبر")
        set_setting("ab_layout", pick, "چیدمان نمای کاربر", "about", uid)
        send(cid, f"✅ چیدمان: {LAYOUTS[pick]['name']}")
        return show_layout(cid, uid)

    cur = layout()
    lines = ["🎛️ چیدمان نمای کاربر", "━━━━━━━━━━━━━━", "",
             "کاربر صفحه «پشتیبانی و درباره ما» را چطور ببیند؟", ""]
    btns = []
    for k, v in LAYOUTS.items():
        mark = "🔘" if k == cur else "⚪"
        lines += [f"{mark} {v['icon']} {v['name']}", f"      {v['desc']}"]
        btns.append([{"text": f"{mark} {v['icon']} {v['name']}",
                      "callback_data": f"ablay_{k}"}])
    lines += ["", "💡 «گروهی» برای بیشتر ربات‌ها بهترین است."]
    btns.append([{"text": "👁️ ببین کاربر چه می‌بیند",
                  "callback_data": "ab_preview"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_admin"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_bulk(cid, uid, action=None):
    """⚡ روشن/خاموش کردن گروهی بخش‌ها"""
    if not _guard(cid, uid):
        return
    allk = [b[0] for b in ABOUT_BLOCKS + SUPPORT_BLOCKS]
    if action in ("on", "off"):
        for k in allk:
            set_setting(f"ab_on_{k}", "1" if action == "on" else "0",
                        f"نمایش {k}", "about", uid)
        send(cid, f"✅ همه بخش‌ها {'روشن' if action == 'on' else 'خاموش'} شد")
        return show_bulk(cid, uid)
    if action == "reset":
        for k, _i, _n, _s, dflt in ABOUT_BLOCKS + SUPPORT_BLOCKS:
            set_setting(f"ab_on_{k}", str(dflt), f"نمایش {k}",
                        "about", uid)
        send(cid, "♻️ به حالت پیش‌فرض برگشت")
        return show_bulk(cid, uid)

    on_n = sum(1 for k in allk if block_on(k))
    lines = ["⚡ روشن/خاموش گروهی", "━━━━━━━━━━━━━━", "",
             f"🟢 روشن: {on_n} از {len(allk)} بخش", "",
             "ℹ️ بخش‌های درباره ما:"]
    for k, ic, nm, _s, _d in ABOUT_BLOCKS:
        lines.append(f"   {'🟢' if block_on(k) else '⚪'} {ic} {nm}")
    lines += ["", "💬 بخش‌های پشتیبانی:"]
    for k, ic, nm, _s, _d in SUPPORT_BLOCKS:
        lines.append(f"   {'🟢' if block_on(k) else '⚪'} {ic} {nm}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🟢 همه روشن", "callback_data": "abbulk_on"},
         {"text": "⚪ همه خاموش", "callback_data": "abbulk_off"}],
        [{"text": "♻️ بازگشت به پیش‌فرض",
          "callback_data": "abbulk_reset"}],
        [{"text": "🔙 بازگشت", "callback_data": "ab_admin"}]]})


def toggle_block(cid, uid, key):
    if not _guard(cid, uid):
        return
    if key == "stats":
        cur = get_setting("ab_show_stats", "1")
        set_setting("ab_show_stats", "0" if cur == "1" else "1",
                    "نمایش آمار درباره ما", "about", uid)
        return show_admin(cid, uid)
    valid = {b[0] for b in ABOUT_BLOCKS + SUPPORT_BLOCKS}
    if key not in valid:
        return send(cid, "❌ نامعتبر")
    cur = block_on(key)
    set_setting(f"ab_on_{key}", "0" if cur else "1",
                f"نمایش بخش {key}", "about", uid)
    return show_admin(cid, uid)


def start_edit_text(cid, uid, key):
    if not _guard(cid, uid):
        return
    mapping = {b[0]: (b[1], b[2], b[3])
               for b in ABOUT_BLOCKS + SUPPORT_BLOCKS if b[3]}
    if key not in mapping:
        return send(cid, "❌ این بخش متن ویرایش‌پذیر ندارد")
    icon, name, skey = mapping[key]
    cur = _txt(skey)
    set_state(uid, STATE_AB_TEXT, {"key": key, "skey": skey}, merge=False)
    send(cid, (
        f"✏️ {icon} {name}\n━━━━━━━━━━━━━━\n\n"
        f"📄 متن فعلی:\n{cur[:600] or '—'}\n\n"
        f"متن جدید را بفرستید:\n\n"
        f"💡 برای بازگشت به پیش‌فرض، «پیش‌فرض» بنویسید."
    ), kb_cancel())


def handle_edit_text(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    key, skey = d.get("key"), d.get("skey")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_admin(cid, uid)
    if not skey:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "پیش‌فرض":
        dflt = next((d3 for k, _, d3 in DEFAULT_TEXTS if k == skey), "")
        set_setting(skey, dflt, "درباره ما", "about", uid)
        clear_state(uid)
        send(cid, "♻️ به متن پیش‌فرض برگشت", kb_remove())
        return show_admin(cid, uid)

    if len(raw) < 3:
        return send(cid, "⚠️ متن خیلی کوتاه است:", kb_cancel())

    set_setting(skey, raw[:3000], "درباره ما", "about", uid)
    clear_state(uid)
    log_action(uid, "about_text_edited", {"key": key})
    send(cid, "✅ متن ذخیره شد", kb_remove())
    return show_admin(cid, uid)


# ══════════════════════════════════════════════════════════
# 🏷️ فاز ۱۸-ج — هویت ربات
#
# 🎯 «هویت ربات هم من بتونم تنظیم کنم تو تنظیمات که مثلا کلا اسم
#     نورا باشه یا نباشه یا هرچیزی که من تنظیم میکنم تغییر کنه»
# ══════════════════════════════════════════════════════════
STATE_AB_IDENT = "ab_identity"

IDENT_FIELDS = {
    "bot_name": ("🤖", "نام ربات", "id_bot_name",
                 "نام جدید ربات را بنویسید:\n\nمثال: نورا\n\n"
                 "💡 برای برگشت به پیش‌فرض «پیش‌فرض» بنویسید."),
    "org_name": ("🏢", "نام مجموعه", "id_org_name",
                 "نام مجموعه را بنویسید:\n\n"
                 "مثال: گروه فرهنگی و اجتماعی خط زندگی"),
}


def show_identity(cid, uid):
    """🏷️ تنظیم هویت ربات"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    from config import (bot_name, org_name, brand, show_bot_name,
                        BOT_NAME_ENV, ORG_NAME_ENV)

    shown = show_bot_name()
    lines = [
        "🏷️ هویت ربات", "━━━━━━━━━━━━━━", "",
        f"🤖 نام ربات: {bot_name()}",
        f"🏢 نام مجموعه: {org_name()}",
        f"👁️ نمایش نام ربات: {'🟢 بله' if shown else '🔴 خیر'}",
        "", "━━━━━━━━━━━━━━", "👁️ کاربر این‌طور می‌بیند:", "",
        f"   🏠 {brand()}",
        f"   {org_name()}",
        "",
    ]
    if not shown:
        lines += ["💡 با خاموش بودن نمایش نام، همه‌جا فقط «ربات» "
                  "نوشته می‌شود.", ""]
    lines += ["📌 پیش‌فرض فایل .env:",
              f"   🤖 {BOT_NAME_ENV}",
              f"   🏢 {ORG_NAME_ENV}", "",
              "💡 در متن‌ها می‌توانید از {bot} · {org} · {brand} "
              "استفاده کنید."]

    btns = [
        [{"text": f"🤖 نام ربات: {bot_name()}"[:34],
          "callback_data": "abid_bot_name"}],
        [{"text": f"🏢 نام مجموعه: {org_name()}"[:34],
          "callback_data": "abid_org_name"}],
        [{"text": f"👁️ نمایش نام ربات: {'✅ بله' if shown else '❌ خیر'}",
          "callback_data": "abid_toggle"}],
        [{"text": "♻️ بازگشت به پیش‌فرض", "callback_data": "abid_reset"}],
        [{"text": "🔙 بازگشت", "callback_data": "ab_admin"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_identity_edit(cid, uid, field):
    if not _guard(cid, uid):
        return
    if field not in IDENT_FIELDS:
        return send(cid, "❌ نامعتبر")
    icon, name, skey, hint = IDENT_FIELDS[field]
    cur = (get_setting(skey, "") or "").strip()
    set_state(uid, STATE_AB_IDENT, {"field": field, "skey": skey},
              merge=False)
    send(cid, (f"✏️ {icon} {name}\n━━━━━━━━━━━━━━\n\n"
               f"📄 فعلی: {cur or '(پیش‌فرض)'}\n\n{hint}"), kb_cancel())


def handle_identity(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    skey = d.get("skey")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_identity(cid, uid)
    if not skey:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "پیش‌فرض":
        db_execute("DELETE FROM settings WHERE key=?", (skey,))
        from database import clear_settings_cache
        clear_settings_cache()
        clear_state(uid)
        send(cid, "♻️ به مقدار پیش‌فرض برگشت", kb_remove())
        return show_identity(cid, uid)

    if len(raw) < 2:
        return send(cid, "⚠️ حداقل ۲ حرف بنویسید:", kb_cancel())
    if len(raw) > 60:
        return send(cid, "⚠️ حداکثر ۶۰ حرف:", kb_cancel())

    set_setting(skey, raw, "هویت ربات", "identity", uid)
    clear_state(uid)
    log_action(uid, "identity_changed", {"key": skey})
    send(cid, f"✅ ذخیره شد: {raw}", kb_remove())
    return show_identity(cid, uid)


def toggle_identity(cid, uid):
    """روشن/خاموش کردن نمایش نام ربات"""
    if not _guard(cid, uid):
        return
    cur = get_setting("id_show_bot_name", "1") == "1"
    set_setting("id_show_bot_name", "0" if cur else "1",
                "نمایش نام ربات", "identity", uid)
    log_action(uid, "identity_changed", {"key": "show_bot_name"})
    return show_identity(cid, uid)


def reset_identity(cid, uid):
    """♻️ بازگشت هویت به مقادیر .env"""
    if not _guard(cid, uid):
        return
    for k in ("id_bot_name", "id_org_name", "id_show_bot_name"):
        db_execute("DELETE FROM settings WHERE key=?", (k,))
    from database import clear_settings_cache
    clear_settings_cache()
    send(cid, "♻️ هویت ربات به پیش‌فرض برگشت")
    return show_identity(cid, uid)


# ─────────────── 🌐 لینک‌ها ───────────────
def show_links_admin(cid, uid):
    if not _guard(cid, uid):
        return
    links = get_links(active_only=False)
    lines = ["🌐 شبکه‌های اجتماعی و لینک‌ها", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not links:
        lines.append("🌱 هنوز لینکی اضافه نکرده‌اید.")
    for l in links:
        k = SOCIAL_KINDS.get(l.get("kind") or "website",
                             {"icon": "🔗", "name": "لینک"})
        st = "🟢" if l.get("is_active") else "🔴"
        lines.append(f"{st} {k['icon']} {l.get('title') or k['name']} — "
                     f"{str(l.get('url') or '')[:40]}")
        btns.append([
            {"text": f"{st} {k['icon']} {l.get('title') or k['name']}"[:26],
             "callback_data": f"ablt_{l['id']}"},
            {"text": "🗑️", "callback_data": f"abld_{l['id']}"}])
    btns.append([{"text": "➕ افزودن لینک", "callback_data": "ablnew"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_admin"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_link(cid, uid, kind=None):
    if not _guard(cid, uid):
        return
    if not kind:
        btns = [[{"text": f"{v['icon']} {v['name']}",
                  "callback_data": f"ablnew_{k}"}]
                for k, v in SOCIAL_KINDS.items()]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_links"}])
        return send_or_edit(cid, "🌐 نوع لینک را انتخاب کنید:",
                            {"inline_keyboard": btns})
    if kind not in SOCIAL_KINDS:
        return send(cid, "❌ نامعتبر")
    k = SOCIAL_KINDS[kind]
    set_state(uid, STATE_AB_LINK, {"kind": kind}, merge=False)
    send(cid, (
        f"➕ {k['icon']} {k['name']}\n━━━━━━━━━━━━━━\n\n"
        f"در یک خط بنویسید:\n\n"
        f"عنوان | آدرس\n\n"
        f"مثال:\n"
        f"کانال خط زندگی | https://ble.ir/khatzendegi\n\n"
        f"💡 اگر فقط آدرس بنویسید، عنوان پیش‌فرض می‌شود."
    ), kb_cancel())


def handle_add_link(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    kind = d.get("kind")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_links_admin(cid, uid)
    if kind not in SOCIAL_KINDS:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) >= 2:
        title, url = parts[0], parts[1]
    else:
        title, url = SOCIAL_KINDS[kind]["name"], parts[0]
    if not url:
        return send(cid, "⚠️ آدرس را بنویسید:", kb_cancel())

    n = db_scalar("SELECT COALESCE(MAX(sort_order),0) FROM about_links") or 0
    db_execute("""INSERT INTO about_links (kind, title, url, sort_order)
        VALUES (?,?,?,?)""", (kind, title[:60], url[:300], n + 1))
    clear_state(uid)
    send(cid, f"✅ «{title[:40]}» اضافه شد", kb_remove())
    log_action(uid, "about_link_added", {"kind": kind})
    return show_links_admin(cid, uid)


def toggle_link(cid, uid, lid):
    if not _guard(cid, uid):
        return
    r = db_execute("SELECT is_active FROM about_links WHERE id=?", (lid,),
                   fetch="one")
    if not r:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE about_links SET is_active=? WHERE id=?",
               (0 if r.get("is_active") else 1, lid))
    return show_links_admin(cid, uid)


def delete_link(cid, uid, lid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM about_links WHERE id=?", (lid,))
    send(cid, "🗑️ حذف شد")
    return show_links_admin(cid, uid)


# ─────────────── 👥 تیم ───────────────
def show_people_admin(cid, uid):
    if not _guard(cid, uid):
        return
    people = get_people(active_only=False)
    lines = ["👥 مدیریت تیم", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not people:
        lines += ["🌱 هنوز کسی معرفی نشده.", "",
                  "با «➕ افزودن» اعضای تیم را معرفی کنید."]
    for p in people:
        st = "🟢" if p.get("is_active") else "🔴"
        lines.append(f"{st} {p.get('name')} — {p.get('role') or '—'}")
        btns.append([
            {"text": f"{st} {p.get('name')}"[:26],
             "callback_data": f"abpt_{p['id']}"},
            {"text": "🗑️", "callback_data": f"abpd_{p['id']}"}])
    btns.append([{"text": "➕ افزودن عضو", "callback_data": "abpnew"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ab_admin"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_person(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_AB_PERSON, {}, merge=False)
    send(cid, (
        "➕ افزودن عضو تیم\n━━━━━━━━━━━━━━\n\n"
        "در یک خط بنویسید:\n\n"
        "نام | سمت | معرفی کوتاه | راه ارتباط\n\n"
        "مثال:\n"
        "علی محمدی | مدیر آموزش | ۱۰ سال سابقه تدریس | @ali\n\n"
        "💡 فقط «نام» اجباری است، بقیه اختیاری."
    ), kb_cancel())


def handle_add_person(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_people_admin(cid, uid)

    parts = [p.strip() for p in raw.split("|")]
    name = parts[0] if parts else ""
    if len(name) < 2:
        return send(cid, "⚠️ نام را بنویسید:", kb_cancel())

    n = db_scalar("SELECT COALESCE(MAX(sort_order),0) FROM about_people") or 0
    db_execute("""INSERT INTO about_people
        (name, role, bio, contact, sort_order)
        VALUES (?,?,?,?,?)""",
        (name[:60],
         parts[1][:60] if len(parts) > 1 else "",
         parts[2][:300] if len(parts) > 2 else "",
         parts[3][:60] if len(parts) > 3 else "",
         n + 1))
    clear_state(uid)
    send(cid, f"✅ «{name[:40]}» اضافه شد", kb_remove())
    return show_people_admin(cid, uid)


def toggle_person(cid, uid, pid):
    if not _guard(cid, uid):
        return
    r = db_execute("SELECT is_active FROM about_people WHERE id=?", (pid,),
                   fetch="one")
    if not r:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE about_people SET is_active=? WHERE id=?",
               (0 if r.get("is_active") else 1, pid))
    return show_people_admin(cid, uid)


def delete_person(cid, uid, pid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM about_people WHERE id=?", (pid,))
    send(cid, "🗑️ حذف شد")
    return show_people_admin(cid, uid)


# ─────────────── 🤝 اتصال فرم همکاری ───────────────
def show_join_forms(cid, uid):
    """انتخاب اینکه کدام فرم به «همکاری با ما» وصل شود"""
    if not _guard(cid, uid):
        return
    from forms import FORM_SECTIONS

    lines = ["🤝 اتصال فرم به بخش‌های ربات", "━━━━━━━━━━━━━━", "",
             "هر فرم می‌تواند به یکی از بخش‌های ربات وصل شود.", "",
             "📌 وضعیت فعلی:", ""]
    for k, v in FORM_SECTIONS.items():
        fs = _section_forms(k)
        if fs:
            for f in fs:
                lines.append(f"{v['icon']} {v['name']} ← {f.get('title')}")
        else:
            lines.append(f"{v['icon']} {v['name']} — —")

    lines += ["", "💡 برای وصل کردن:",
              "فرم‌ساز › فرم مورد نظر › 🎨 جزئیات › 👁️ دسترسی",
              "› 🧩 متصل به بخش ربات"]

    btns = [[{"text": "📝 رفتن به فرم‌ساز", "callback_data": "fb_panel"}],
            [{"text": "🔙 بازگشت", "callback_data": "ab_admin"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})
