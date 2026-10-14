"""
📝 مدیریت سوالات فرم (فیلدها) — فاز ۹

طبق ساختار دیجی‌فرم:
  • افزودن فیلد از کاتالوگ ۵۵+ نوع در ۱۵ دسته + جستجو
  • هر فیلد: عنوان، توضیح، راهنما، رسانه، اجباری، گزینه‌ها
  • منوی ⋮ : جابه‌جایی بالا/پایین، شرط، کپی، راهنما، حذف
  • شرط نمایش (روی همه انواع، نه فقط چند گزینه‌ای)
"""
import json

from database import db_execute, db_scalar, log
from auth import (
    set_state, get_state_data, clear_state, log_action, normalize_digits,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK, BTN_SKIP
from forms import (
    FIELD_TYPES, FIELD_CATS, OPTION_KINDS, FIELDS_PER_PAGE,
    STATE_FB_FIELD, STATE_FB_OPTION, POPULAR_FIELDS, FORM_TEMPLATES,
    REQUIRED_BY_DEFAULT, PRICED_KINDS, default_terms_for,
    get_form, get_fields, get_field, field_meta, field_label, parse_options,
    set_options, form_can_manage, touch_form,
    parse_items, set_items, item_label, item_is_full, fmt_amount,
)
from config import CURRENCY_LABEL

# عملگرهای شرط
CONDITION_OPS = {
    "eq":       {"name": "مساوی است با", "icon": "="},
    "ne":       {"name": "مساوی نیست با", "icon": "≠"},
    "contains": {"name": "شامل است", "icon": "⊃"},
    "ncontains": {"name": "شامل نیست", "icon": "⊅"},
    "gt":       {"name": "بزرگ‌تر از", "icon": ">"},
    "lt":       {"name": "کوچک‌تر از", "icon": "<"},
    "empty":    {"name": "خالی است", "icon": "∅"},
    "nempty":   {"name": "خالی نیست", "icon": "✔"},
}


def _guard_form(cid, uid, fid):
    form = get_form(fid)
    if not form:
        send(cid, "❌ فرم یافت نشد")
        return None
    if not form_can_manage(uid, form):
        send(cid, "❌ دسترسی ندارید")
        return None
    return form


# ==================== لیست سوالات ====================
def show_fields(cid, uid, fid, page=0):
    form = _guard_form(cid, uid, fid)
    if not form:
        return

    fields = get_fields(fid)
    if not fields:
        btns = []
        tpl = FORM_TEMPLATES.get(form.get("form_type")) or []
        if tpl:
            btns.append([{"text": f"🎁 افزودن {len(tpl)} سوال آماده",
                          "callback_data": f"fbtpl_{fid}"}])
        btns.append([{"text": "➕ افزودن سوال", "callback_data": f"fbfa_{fid}"}])
        btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}])
        return send_or_edit(cid, (
            f"📝 سوالات فرم «{form['title'][:30]}»\n"
            "━━━━━━━━━━━━━━\n\n"
            "📭 هنوز سوالی اضافه نشده.\n\n"
            "💡 با دکمه زیر اولین سوال را بسازید."
        ), {"inline_keyboard": btns})

    per = FIELDS_PER_PAGE
    pages = max(1, (len(fields) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = fields[page * per:(page + 1) * per]

    lines = [f"📝 سوالات فرم «{form['title'][:28]}»", "━━━━━━━━━━━━━━",
             f"📊 مجموع: {len(fields)} سوال", ""]
    btns = []
    for i, f in enumerate(chunk, start=page * per + 1):
        m = field_meta(f.get("field_type"))
        req = "⭐" if f.get("is_required") else "◽"
        cond = " ◇" if f.get("condition_field_id") else ""
        opts = ""
        if m.get("kind") in OPTION_KINDS:
            opts = f" ({len(parse_options(f))} گزینه)"
        lines.append(f"{req} {i}. {m['icon']} {field_label(f)[:42]}{opts}{cond}")
        btns.append([{"text": f"{i}. {m['icon']} {field_label(f)[:26]}",
                      "callback_data": f"fbfe_{f['id']}"}])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"fbfp_{page-1}_{fid}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"fbfp_{page+1}_{fid}"})
        btns.append(nav)

    lines += ["", "⭐ = اجباری | ◇ = دارای شرط"]

    # 🔴 مهم‌ترین راهنما: تا منتشر نشود کاربران فرم را نمی‌بینند
    active = (form.get("status") == "active")
    if active:
        lines += ["", "🟢 فرم منتشر شده — کاربران می‌توانند پر کنند"]
    else:
        lines += ["", "⚠️ فرم هنوز منتشر نشده!",
                  "کاربران تا زمانی که «📢 انتشار» را نزنید آن را نمی‌بینند."]

    btns.append([{"text": "➕ افزودن سوال", "callback_data": f"fbfa_{fid}"}])
    btns.append([{"text": "👁️ پیش‌نمایش", "callback_data": f"fbprev_{fid}"},
                 {"text": "🔀 مرتب‌سازی", "callback_data": f"fbsort_{fid}"}])
    if not active:
        btns.append([{"text": "📢 انتشار فرم (تا کاربران ببینند)",
                      "callback_data": f"fbpub_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== افزودن فیلد: انتخاب دسته ====================
def show_add_field(cid, uid, fid):
    """
    ➕ افزودن سوال — پرکاربردها مستقیم، مثل دیجی‌فرم.

    قبلاً کاربر مجبور بود اول دسته را باز کند (۳ لمس تا یک سوال ساده).
    حالا ۱۶ فیلد پرکاربرد یک‌لمسی‌اند.
    """
    form = _guard_form(cid, uid, fid)
    if not form:
        return

    btns = []
    row = []
    for key in POPULAR_FIELDS:
        m = FIELD_TYPES.get(key)
        if not m:
            continue
        row.append({"text": f"{m['icon']} {m['name']}",
                    "callback_data": f"fbn_{key}_{fid}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)

    btns.append([{"text": f"📚 همه دسته‌ها ({len(FIELD_TYPES)} نوع)",
                  "callback_data": f"fbcats_{fid}"}])
    btns.append([{"text": "🔍 جستجو", "callback_data": f"fbfs_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbf_{fid}"}])

    send_or_edit(cid, (
        "➕ افزودن سوال\n━━━━━━━━━━━━━━\n\n"
        "پرکاربردترین سوال‌ها — یکی را بزنید:\n\n"
        "💡 سوال بلافاصله اضافه می‌شود؛ بعد می‌توانید ویرایشش کنید."
    ), {"inline_keyboard": btns})


def show_all_cats(cid, uid, fid):
    """📚 همه دسته‌ها (برای فیلدهای کمتر پرکاربرد)"""
    form = _guard_form(cid, uid, fid)
    if not form:
        return
    btns = []
    row = []
    for key, icon, name in FIELD_CATS:
        n = sum(1 for v in FIELD_TYPES.values() if v.get("cat") == key)
        row.append({"text": f"{icon} {name} ({n})", "callback_data": f"fbc_{key}_{fid}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([{"text": "🔍 جستجو در فیلدها", "callback_data": f"fbfs_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfa_{fid}"}])

    send_or_edit(cid, (
        "📚 همه دسته‌ها\n━━━━━━━━━━━━━━\n\n"
        f"{len(FIELD_TYPES)} نوع فیلد در {len(FIELD_CATS)} دسته\n\n"
        "یک دسته را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def show_category(cid, uid, fid, cat):
    form = _guard_form(cid, uid, fid)
    if not form:
        return
    info = next((c for c in FIELD_CATS if c[0] == cat), None)
    if not info:
        return send(cid, "❌ دسته نامعتبر")
    _, icon, name = info

    items = [(k, v) for k, v in FIELD_TYPES.items() if v.get("cat") == cat]
    btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"fbn_{k}_{fid}"}]
            for k, v in items]
    btns.append([{"text": "🔙 دسته‌ها", "callback_data": f"fbfa_{fid}"}])

    send_or_edit(cid, (
        f"{icon} {name}\n━━━━━━━━━━━━━━\n\n"
        f"{len(items)} نوع فیلد — یکی را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def start_field_search(cid, uid, fid):
    form = _guard_form(cid, uid, fid)
    if not form:
        return
    set_state(uid, STATE_FB_FIELD, {"fid": fid, "mode": "search"}, merge=False)
    send(cid, (
        "🔍 جستجو در فیلدها\n━━━━━━━━━━━━━━\n\n"
        "نام فیلد مورد نظر را بنویسید:\n\n"
        "مثال: موبایل، تاریخ، تصویر"
    ), kb_cancel())


def handle_field_search(cid, uid, fid, query):
    q = (query or "").strip()
    if not q:
        return show_add_field(cid, uid, fid)
    ql = q.replace("‌", "").lower()
    hits = [(k, v) for k, v in FIELD_TYPES.items()
            if ql in v["name"].replace("‌", "").lower() or ql in k.lower()]

    if not hits:
        return send_or_edit(cid, (
            f"🔍 جستجو: {q}\n━━━━━━━━━━━━━━\n\n"
            "❌ فیلدی پیدا نشد.\n\n💡 از دسته‌بندی انتخاب کنید."
        ), {"inline_keyboard": [
            [{"text": "📚 دسته‌بندی فیلدها", "callback_data": f"fbfa_{fid}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"fbf_{fid}"}]]})

    btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"fbn_{k}_{fid}"}]
            for k, v in hits[:20]]
    btns.append([{"text": "📚 همه دسته‌ها", "callback_data": f"fbfa_{fid}"}])
    send_or_edit(cid, (
        f"🔍 نتیجه جستجو: {q}\n━━━━━━━━━━━━━━\n\n"
        f"{len(hits)} فیلد پیدا شد:"
    ), {"inline_keyboard": btns})


# ==================== ساخت فیلد ====================
def create_field(cid, uid, fid, ftype):
    """فیلد را با مقادیر پیش‌فرض می‌سازد و صفحه ویرایشش را باز می‌کند"""
    form = _guard_form(cid, uid, fid)
    if not form:
        return
    if ftype not in FIELD_TYPES:
        return send(cid, "❌ نوع فیلد نامعتبر")

    m = FIELD_TYPES[ftype]
    order = (db_scalar("SELECT COALESCE(MAX(field_order),0) FROM form_fields "
                       "WHERE form_id=?", (fid,)) or 0) + 1

    opts = m.get("opts")
    # پیش‌فرض هوشمند: فیلدهای هویتی و تأییدی اجباری‌اند
    req = 1 if (m.get("kind") == "confirm" or ftype in REQUIRED_BY_DEFAULT) else 0
    field_id = db_execute("""INSERT INTO form_fields
        (form_id, field_order, field_type, label, options, is_required,
         min_val, max_val, max_files, score, terms_text)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (fid, order, ftype, m.get("q", ""),
         json.dumps(opts, ensure_ascii=False) if opts else None,
         req, m.get("min"), m.get("max"), 1,
         1 if m.get("kind") == "quiz" else 0,
         default_terms_for(ftype, form.get("form_type"))))

    if not field_id:
        return send(cid, "❌ خطا در ساخت فیلد")
    touch_form(fid)
    log_action(uid, "field_add", {"fid": fid, "type": ftype})

    # 🎓 آیتم قیمت‌دار → مستقیم برو تعریف اسم و هزینه
    if m.get("kind") in PRICED_KINDS:
        send(cid, (
            f"✅ سوال «{m['icon']} {m['name']}» اضافه شد\n\n"
            f"🎓 حالا آیتم‌ها را با اسم و هزینه تعریف کنید:"
        ))
        return start_add_item(cid, uid, field_id)

    # 📜 قوانین: متن پیش‌فرض دارد، فقط خبر بده که قابل ویرایش است
    if m.get("has_terms"):
        send(cid, (
            f"✅ «{m['icon']} {m['name']}» اضافه شد  ⭐ اجباری\n\n"
            f"📜 متن پیش‌فرض قرار داده شد — می‌توانید ویرایشش کنید."
        ))
        return edit_field(cid, uid, field_id)

    # ⚡ فیلدهای گزینه‌دار بدون گزینه بلااستفاده‌اند → مستقیم برو گزینه‌ها
    if m.get("kind") in OPTION_KINDS and not opts:
        send(cid, (
            f"✅ سوال «{m['icon']} {m['name']}» اضافه شد\n\n"
            f"⚠️ این سوال گزینه لازم دارد — الان اضافه کنید:"
        ))
        return start_add_option(cid, uid, field_id, bulk=True)

    # ⚡ بقیه: برگرد به لیست تا سریع سوال بعدی را بزند (نه صفحه ویرایش)
    send(cid, f"✅ «{m['icon']} {m['name']}» اضافه شد"
              + ("  ⭐ اجباری" if req else ""))
    return show_fields(cid, uid, fid, 0)


# ==================== ویرایش یک فیلد ====================
def edit_field(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ سوال یافت نشد")
    form = _guard_form(cid, uid, f["form_id"])
    if not form:
        return

    m = field_meta(f.get("field_type"))
    fields = get_fields(f["form_id"])
    idx = next((i for i, x in enumerate(fields, 1) if x["id"] == f["id"]), 0)

    lines = [
        f"⚙️ سوال {idx}: {m['icon']} {m['name']}",
        "━━━━━━━━━━━━━━",
        "",
        f"❓ متن سوال:\n{field_label(f)}",
    ]
    if f.get("description"):
        lines.append(f"\n📄 توضیح: {f['description']}")
    if f.get("help_text"):
        lines.append(f"⚠️ راهنما: {f['help_text']}")
    if f.get("media_file_id"):
        lines.append("🖼️ رسانه: ✅ دارد")

    lines.append(f"\n{'⭐ اجباری' if f.get('is_required') else '◽ اختیاری'}")

    kind = m.get("kind")

    if m.get("has_terms"):
        tt = f.get("terms_text") or ""
        lines.append(f"\n📜 متن قوانین: "
                     + (f"✅ {len(tt)} کاراکتر" if tt else "⚠️ خالی — حتماً پر کنید"))

    if kind in PRICED_KINDS:
        items = parse_items(f)
        lines.append(f"\n🎓 آیتم‌ها ({len(items)}):")
        for i, it in enumerate(items[:10], 1):
            lines.append(f"   {i}. {item_label(it)}")
        if not items:
            lines.append("   ⚠️ هنوز آیتمی ندارد! (اسم + هزینه اضافه کنید)")
    elif kind in OPTION_KINDS:
        opts = parse_options(f)
        lines.append(f"\n📋 گزینه‌ها ({len(opts)}):")
        for i, o in enumerate(opts[:10], 1):
            mark = ""
            if kind == "quiz" and str(f.get("correct_option") or "") == str(i):
                mark = " ✅"
            lines.append(f"   {i}. {o}{mark}")
        if len(opts) > 10:
            lines.append(f"   … و {len(opts)-10} گزینه دیگر")
        if not opts:
            lines.append("   ⚠️ هنوز گزینه‌ای ندارد!")

    if kind == "quiz":
        lines.append(f"\n🎯 امتیاز: {f.get('score') or 0}")
        lines.append(f"✅ پاسخ صحیح: گزینه {f.get('correct_option') or '—'}")
    if kind in ("file", "photo", "video"):
        lines.append(f"\n📎 حداکثر تعداد فایل: {f.get('max_files') or 1}")
    if kind in ("text", "longtext", "number", "amount"):
        lo, hi = f.get("min_val"), f.get("max_val")
        if lo is not None or hi is not None:
            unit = "کاراکتر" if kind in ("text", "longtext") else "مقدار"
            lines.append(f"\n📏 محدوده ({unit}): {lo if lo is not None else '—'} "
                         f"تا {hi if hi is not None else '—'}")

    if f.get("condition_field_id"):
        cf = get_field(f["condition_field_id"])
        op = CONDITION_OPS.get(f.get("condition_operator") or "eq", {})
        lines.append(f"\n◇ شرط نمایش:\nاگر «{field_label(cf)[:28] if cf else '—'}» "
                     f"{op.get('name','')} «{f.get('condition_value') or ''}»")

    btns = [
        [{"text": "✏️ متن سوال", "callback_data": f"fbfl_{field_id}"}],
        [{"text": "📄 توضیح", "callback_data": f"fbfd_{field_id}"},
         {"text": "⚠️ راهنما", "callback_data": f"fbfh_{field_id}"}],
        [{"text": f"{'⭐ اجباری ✅' if f.get('is_required') else '◽ اختیاری'}",
          "callback_data": f"fbfreq_{field_id}"}],
    ]
    if m.get("has_terms"):
        btns.append([{"text": "📜 متن قوانین", "callback_data": f"fbtt_{field_id}"}])
    if kind in PRICED_KINDS:
        btns.append([{"text": "🎓 آیتم‌ها (اسم + هزینه)",
                      "callback_data": f"fbit_{field_id}"}])
    elif kind in OPTION_KINDS:
        btns.append([{"text": "📋 مدیریت گزینه‌ها", "callback_data": f"fbfo_{field_id}"}])
    if kind == "quiz":
        btns.append([{"text": "✅ پاسخ صحیح", "callback_data": f"fbfc_{field_id}"},
                     {"text": "🎯 امتیاز", "callback_data": f"fbfsc_{field_id}"}])
    if kind in ("text", "longtext", "number", "amount"):
        btns.append([{"text": "📏 حداقل/حداکثر", "callback_data": f"fbfmm_{field_id}"}])
    if kind in ("file", "photo", "video"):
        btns.append([{"text": "📎 تعداد فایل", "callback_data": f"fbfmf_{field_id}"}])

    btns.append([{"text": "🖼️ رسانه سوال", "callback_data": f"fbfmed_{field_id}"}])
    btns.append([{"text": "◇ شرط نمایش", "callback_data": f"fbfcond_{field_id}"}])
    btns.append([
        {"text": "⬆️ بالا", "callback_data": f"fbfup_{field_id}"},
        {"text": "⬇️ پایین", "callback_data": f"fbfdn_{field_id}"},
    ])
    btns.append([{"text": "📋 کپی سوال", "callback_data": f"fbfcp_{field_id}"},
                 {"text": "🗑️ حذف سوال", "callback_data": f"fbfdel_{field_id}"}])
    btns.append([{"text": "🔙 لیست سوالات", "callback_data": f"fbf_{f['form_id']}"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== ویرایش متن‌های فیلد ====================
FIELD_TEXT_KEYS = {
    "label":       ("✏️ متن سوال", "متن سوالی که به کاربر نمایش داده می‌شود:"),
    "description": ("📄 توضیح سوال", "توضیح تکمیلی زیر سوال:"),
    "help_text":   ("⚠️ راهنمای سوال", "متن راهنما برای کمک به کاربر:"),
}


def start_edit_field_text(cid, uid, field_id, key):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    if key not in FIELD_TEXT_KEYS:
        return send(cid, "❌ نامعتبر")
    title, prompt = FIELD_TEXT_KEYS[key]
    cur = f.get(key) or "—"
    set_state(uid, STATE_FB_FIELD,
              {"field_id": field_id, "key": key, "fid": f["form_id"]}, merge=False)
    send(cid, (
        f"{title}\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی:\n{cur}\n\n{prompt}\n\n"
        f"💡 «-» = خالی کردن"
    ), kb_cancel())


def start_field_number(cid, uid, field_id, key):
    """ورودی‌های عددی فیلد: امتیاز، تعداد فایل، حداقل/حداکثر، پاسخ صحیح"""
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    prompts = {
        "score": ("🎯 امتیاز سوال", f"امتیاز فعلی: {f.get('score') or 0}\n\nامتیاز جدید:"),
        "max_files": ("📎 حداکثر تعداد فایل",
                      f"فعلی: {f.get('max_files') or 1}\n\nعدد جدید (۱ تا ۱۰):"),
        "minmax": ("📏 حداقل و حداکثر",
                   f"فعلی: {f.get('min_val') if f.get('min_val') is not None else '—'} "
                   f"تا {f.get('max_val') if f.get('max_val') is not None else '—'}\n\n"
                   "دو عدد با خط تیره بنویسید.\n\nمثال: 3-50\n💡 «-» = حذف محدودیت"),
        "correct": ("✅ پاسخ صحیح",
                    "شماره گزینه صحیح را بنویسید.\n\n"
                    + "\n".join(f"{i}. {o}" for i, o in enumerate(parse_options(f), 1))),
    }
    if key not in prompts:
        return send(cid, "❌ نامعتبر")
    title, body = prompts[key]
    set_state(uid, STATE_FB_FIELD,
              {"field_id": field_id, "key": key, "fid": f["form_id"]}, merge=False)
    send(cid, f"{title}\n━━━━━━━━━━━━━━\n\n{body}", kb_cancel())


def start_field_media(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    has = bool(f.get("media_file_id"))
    if has:
        return send_or_edit(cid, (
            "🖼️ رسانه سوال\n━━━━━━━━━━━━━━\n\n"
            "این سوال یک عکس ضمیمه دارد."
        ), {"inline_keyboard": [
            [{"text": "🔄 تغییر عکس", "callback_data": f"fbfmedset_{field_id}"}],
            [{"text": "🗑️ حذف عکس", "callback_data": f"fbfmeddel_{field_id}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"fbfe_{field_id}"}]]})
    return set_field_media(cid, uid, field_id)


def set_field_media(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    set_state(uid, STATE_FB_FIELD,
              {"field_id": field_id, "key": "media", "fid": f["form_id"]}, merge=False)
    send(cid, (
        "🖼️ رسانه سوال\n━━━━━━━━━━━━━━\n\n"
        "عکسی که همراه این سوال نمایش داده شود را بفرستید:"
    ), kb_cancel())


def delete_field_media(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    db_execute("UPDATE form_fields SET media_file_id=NULL, media_type=NULL WHERE id=?",
               (field_id,))
    send(cid, "🗑️ رسانه حذف شد")
    return edit_field(cid, uid, field_id)


def handle_field_photo(message):
    """عکس ضمیمه سوال"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    data = get_state_data(uid)
    field_id = data.get("field_id")
    if data.get("key") != "media" or not field_id:
        return send(cid, "⚠️ حالت نامعتبر", kb_remove())
    photos = message.get("photo") or []
    if not photos:
        return send(cid, "⚠️ لطفاً یک عکس بفرستید", kb_cancel())
    db_execute("UPDATE form_fields SET media_file_id=?, media_type='photo' WHERE id=?",
               (photos[-1].get("file_id"), field_id))
    clear_state(uid)
    send(cid, "✅ رسانه ذخیره شد", kb_remove())
    return edit_field(cid, uid, field_id)


def handle_field_input(message):
    """روتر ورودی‌های متنی مربوط به فیلد"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    key = data.get("key")
    field_id = data.get("field_id")
    fid = data.get("fid")

    # جستجوی فیلد
    if data.get("mode") == "search":
        clear_state(uid)
        if text in (BTN_BACK, "🔙 بازگشت"):
            send(cid, "❌ لغو شد", kb_remove())
            return show_add_field(cid, uid, fid)
        send(cid, f"🔍 {text}", kb_remove())
        return handle_field_search(cid, uid, fid, text)

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return edit_field(cid, uid, field_id) if field_id else show_fields(cid, uid, fid)

    f = get_field(field_id) if field_id else None
    if not f:
        clear_state(uid)
        return send(cid, "⚠️ سوال یافت نشد", kb_remove())

    # ---- 🔢 سقف انتخاب چند مورد (فاز ۲۳) ----
    if key == "max_items":
        clear_state(uid)
        d = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
        n = int(d) if d else 0
        n = max(0, min(50, n))
        db_execute("UPDATE form_fields SET max_items=? WHERE id=?",
                   (n, field_id))
        touch_form(f["form_id"])
        send(cid, f"✅ سقف انتخاب: {n if n else 'نامحدود'}", kb_remove())
        return show_items(cid, uid, field_id)

    # ---- متن‌ها ----
    if key in FIELD_TEXT_KEYS:
        clear_state(uid)
        val = "" if text == "-" else text[:600]
        if key == "label" and not val:
            val = field_meta(f.get("field_type")).get("q", "")
        db_execute(f"UPDATE form_fields SET {key}=? WHERE id=?", (val, field_id))
        touch_form(f["form_id"])
        send(cid, "✅ ذخیره شد", kb_remove())
        return edit_field(cid, uid, field_id)

    # ---- متن قوانین ----
    if key == "terms_text":
        clear_state(uid)
        val = "" if text == "-" else text[:4000]
        db_execute("UPDATE form_fields SET terms_text=? WHERE id=?", (val, field_id))
        touch_form(f["form_id"])
        send(cid, "✅ متن قوانین ذخیره شد", kb_remove())
        return edit_field(cid, uid, field_id)

    num = normalize_digits(text)

    # ---- امتیاز ----
    if key == "score":
        d = "".join(ch for ch in num if ch.isdigit())
        if not d:
            return send(cid, "⚠️ عدد وارد کنید:", kb_cancel())
        clear_state(uid)
        db_execute("UPDATE form_fields SET score=? WHERE id=?", (int(d), field_id))
        send(cid, "✅ ذخیره شد", kb_remove())
        return edit_field(cid, uid, field_id)

    # ---- تعداد فایل ----
    if key == "max_files":
        d = "".join(ch for ch in num if ch.isdigit())
        if not d:
            return send(cid, "⚠️ عدد وارد کنید:", kb_cancel())
        n = max(1, min(10, int(d)))
        clear_state(uid)
        db_execute("UPDATE form_fields SET max_files=? WHERE id=?", (n, field_id))
        send(cid, f"✅ حداکثر {n} فایل", kb_remove())
        return edit_field(cid, uid, field_id)

    # ---- حداقل/حداکثر ----
    if key == "minmax":
        clear_state(uid)
        if text == "-":
            db_execute("UPDATE form_fields SET min_val=NULL, max_val=NULL WHERE id=?",
                       (field_id,))
            send(cid, "✅ محدودیت حذف شد", kb_remove())
            return edit_field(cid, uid, field_id)
        parts = num.replace("تا", "-").replace(" ", "").split("-")
        nums = [p for p in parts if p.isdigit()]
        if len(nums) < 2:
            send(cid, "⚠️ فرمت نامعتبر — مثال: 3-50", kb_remove())
            return edit_field(cid, uid, field_id)
        lo, hi = int(nums[0]), int(nums[1])
        if lo > hi:
            lo, hi = hi, lo
        db_execute("UPDATE form_fields SET min_val=?, max_val=? WHERE id=?",
                   (lo, hi, field_id))
        send(cid, f"✅ محدوده: {lo} تا {hi}", kb_remove())
        return edit_field(cid, uid, field_id)

    # ---- پاسخ صحیح آزمون ----
    if key == "correct":
        d = "".join(ch for ch in num if ch.isdigit())
        opts = parse_options(f)
        if not d or not (1 <= int(d) <= len(opts)):
            return send(cid, f"⚠️ عددی بین ۱ تا {len(opts)} وارد کنید:", kb_cancel())
        clear_state(uid)
        db_execute("UPDATE form_fields SET correct_option=? WHERE id=?", (d, field_id))
        send(cid, f"✅ پاسخ صحیح: گزینه {d}", kb_remove())
        return edit_field(cid, uid, field_id)

    # ---- مقدار شرط ----
    if key == "cond_value":
        clear_state(uid)
        db_execute("UPDATE form_fields SET condition_value=? WHERE id=?",
                   (text[:200], field_id))
        send(cid, "✅ شرط ذخیره شد", kb_remove())
        return show_condition(cid, uid, field_id)

    clear_state(uid)
    return send(cid, "⚠️ نامعتبر", kb_remove())


# ==================== اجباری / جابه‌جایی / کپی / حذف ====================
def toggle_required(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    db_execute("UPDATE form_fields SET is_required=? WHERE id=?",
               (0 if f.get("is_required") else 1, field_id))
    touch_form(f["form_id"])
    return edit_field(cid, uid, field_id)


def move_field(cid, uid, field_id, direction):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    fields = get_fields(f["form_id"])
    idx = next((i for i, x in enumerate(fields) if x["id"] == f["id"]), None)
    if idx is None:
        return edit_field(cid, uid, field_id)

    swap = idx - 1 if direction == "up" else idx + 1
    if swap < 0 or swap >= len(fields):
        send(cid, "⚠️ همین‌جا اول/آخر لیست است")
        return edit_field(cid, uid, field_id)

    a, b = fields[idx], fields[swap]
    # ترتیب‌ها را بازنویسی می‌کنیم تا حتی اگر مساوی باشند درست شود
    db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (swap + 1, a["id"]))
    db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (idx + 1, b["id"]))
    for i, x in enumerate(get_fields(f["form_id"]), 1):
        db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (i, x["id"]))
    touch_form(f["form_id"])
    return edit_field(cid, uid, field_id)


def copy_field(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    order = (db_scalar("SELECT COALESCE(MAX(field_order),0) FROM form_fields "
                       "WHERE form_id=?", (f["form_id"],)) or 0) + 1
    new_id = db_execute("""INSERT INTO form_fields
        (form_id, field_order, field_type, label, description, help_text,
         placeholder, media_file_id, media_type, options, correct_option, score,
         is_required, min_val, max_val, max_files, allowed_types, default_value,
         condition_field_id, condition_operator, condition_value)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f["form_id"], order, f["field_type"], f.get("label"), f.get("description"),
         f.get("help_text"), f.get("placeholder"), f.get("media_file_id"),
         f.get("media_type"), f.get("options"), f.get("correct_option"),
         f.get("score"), f.get("is_required"), f.get("min_val"), f.get("max_val"),
         f.get("max_files"), f.get("allowed_types"), f.get("default_value"),
         f.get("condition_field_id"), f.get("condition_operator"),
         f.get("condition_value")))
    touch_form(f["form_id"])
    send(cid, "📋 سوال کپی شد")
    return edit_field(cid, uid, new_id) if new_id else show_fields(cid, uid, f["form_id"])


def delete_field(cid, uid, field_id, confirmed=False):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    if not confirmed:
        n = db_scalar("SELECT COUNT(*) FROM form_answers WHERE field_id=?", (field_id,))
        return send_or_edit(cid, (
            f"🗑️ حذف سوال\n━━━━━━━━━━━━━━\n\n"
            f"❓ {field_label(f)[:80]}\n"
            f"📊 پاسخ‌های ثبت‌شده: {n}\n\n"
            f"⚠️ پاسخ‌های این سوال هم حذف می‌شوند."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"fbfdely_{field_id}"}],
            [{"text": "❌ انصراف", "callback_data": f"fbfe_{field_id}"}]]})

    fid = f["form_id"]
    db_execute("DELETE FROM form_answers WHERE field_id=?", (field_id,))
    # شرط‌هایی که به این فیلد ارجاع می‌دادند پاک شوند
    db_execute("UPDATE form_fields SET condition_field_id=NULL, condition_operator=NULL, "
               "condition_value=NULL WHERE condition_field_id=?", (field_id,))
    db_execute("DELETE FROM form_fields WHERE id=?", (field_id,))
    for i, x in enumerate(get_fields(fid), 1):
        db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (i, x["id"]))
    touch_form(fid)
    send(cid, "🗑️ سوال حذف شد")
    return show_fields(cid, uid, fid)


def show_sort(cid, uid, fid):
    """🔀 مرتب‌سازی سریع سوالات"""
    form = _guard_form(cid, uid, fid)
    if not form:
        return
    fields = get_fields(fid)
    if len(fields) < 2:
        send(cid, "⚠️ برای مرتب‌سازی حداقل ۲ سوال لازم است")
        return show_fields(cid, uid, fid)

    lines = ["🔀 مرتب‌سازی سوالات", "━━━━━━━━━━━━━━", "",
             "با فلش‌ها ترتیب را تغییر دهید:", ""]
    btns = []
    for i, f in enumerate(fields, 1):
        m = field_meta(f.get("field_type"))
        lines.append(f"{i}. {m['icon']} {field_label(f)[:38]}")
        row = []
        if i > 1:
            row.append({"text": f"⬆️ {i}", "callback_data": f"fbsu_{f['id']}"})
        if i < len(fields):
            row.append({"text": f"⬇️ {i}", "callback_data": f"fbsd_{f['id']}"})
        if row:
            btns.append(row)
    btns.append([{"text": "✅ پایان مرتب‌سازی", "callback_data": f"fbf_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def move_in_sort(cid, uid, field_id, direction):
    """جابه‌جایی در صفحه مرتب‌سازی (بازگشت به همان صفحه)"""
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    fields = get_fields(f["form_id"])
    idx = next((i for i, x in enumerate(fields) if x["id"] == f["id"]), None)
    if idx is None:
        return show_sort(cid, uid, f["form_id"])
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(fields):
        a, b = fields[idx], fields[swap]
        db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (swap + 1, a["id"]))
        db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (idx + 1, b["id"]))
        for i, x in enumerate(get_fields(f["form_id"]), 1):
            db_execute("UPDATE form_fields SET field_order=? WHERE id=?", (i, x["id"]))
    return show_sort(cid, uid, f["form_id"])


# ==================== مدیریت گزینه‌ها ====================
def show_options(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    m = field_meta(f.get("field_type"))
    if m.get("kind") not in OPTION_KINDS:
        send(cid, "⚠️ این نوع فیلد گزینه ندارد")
        return edit_field(cid, uid, field_id)

    opts = parse_options(f)
    lines = [f"📋 گزینه‌های «{field_label(f)[:34]}»", "━━━━━━━━━━━━━━", ""]
    btns = []
    if opts:
        for i, o in enumerate(opts, 1):
            mark = ""
            if m.get("kind") == "quiz" and str(f.get("correct_option") or "") == str(i):
                mark = " ✅"
            lines.append(f"{i}. {o}{mark}")
            row = [{"text": f"✏️ {i}", "callback_data": f"fboe_{i}_{field_id}"},
                   {"text": f"🗑️ {i}", "callback_data": f"fbod_{i}_{field_id}"}]
            if i > 1:
                row.append({"text": "⬆️", "callback_data": f"fbou_{i}_{field_id}"})
            btns.append(row)
    else:
        lines.append("📭 هنوز گزینه‌ای ندارد")

    lines += ["", f"📊 مجموع: {len(opts)} گزینه"]
    btns.append([{"text": "➕ افزودن گزینه", "callback_data": f"fboa_{field_id}"}])
    btns.append([{"text": "📥 افزودن گروهی", "callback_data": f"fbob_{field_id}"}])
    if opts:
        btns.append([{"text": "🗑️ حذف همه گزینه‌ها", "callback_data": f"fbocl_{field_id}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfe_{field_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== 🎓 آیتم‌های قیمت‌دار ====================
def show_items(cid, uid, field_id):
    """مدیریت آیتم‌های ثبت‌نام: اسم + هزینه + ظرفیت"""
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    m = field_meta(f.get("field_type"))
    if m.get("kind") not in PRICED_KINDS:
        send(cid, "⚠️ این نوع فیلد آیتم ندارد")
        return edit_field(cid, uid, field_id)

    items = parse_items(f)
    lines = [f"🎓 آیتم‌های «{field_label(f)[:34]}»", "━━━━━━━━━━━━━━", ""]
    btns = []
    if items:
        for i, it in enumerate(items, 1):
            lines.append(f"{i}. {it['title']}")
            p = int(it.get("price") or 0)
            lines.append(f"   💰 {fmt_amount(p) + ' ' + CURRENCY_LABEL if p else 'رایگان'}")
            cap = int(it.get("capacity") or 0)
            if cap:
                lines.append(f"   👥 ظرفیت: {it.get('booked', 0)}/{cap}"
                             + ("  🚫 تکمیل" if item_is_full(it) else ""))
            if it.get("desc"):
                lines.append(f"   📄 {it['desc'][:60]}")
            lines.append("")
            btns.append([
                {"text": f"✏️ {i}", "callback_data": f"fbie_{i}_{field_id}"},
                {"text": f"🗑️ {i}", "callback_data": f"fbid_{i}_{field_id}"},
            ])
    else:
        lines += ["📭 هنوز آیتمی ندارد.", "",
                  f"💡 مثال: «دوره فن بیان — 500000 — ۳۰ نفر»", ""]

    # 🆕 فاز ۲۳ — انتخاب چند مورد
    multi = bool(f.get("multi_item"))
    cap_n = int(f.get("max_items") or 0)
    lines += ["━━━━━━━━━━━━━━",
              f"{'☑️' if multi else '1️⃣'} حالت انتخاب: "
              + ("چند مورد با هم" if multi else "فقط یک مورد")]
    if multi:
        lines.append(f"🔢 سقف انتخاب: "
                     + (f"{cap_n} مورد" if cap_n else "بدون محدودیت"))
    lines += ["", "💡 هزینه موردهای انتخابی به مبلغ نهایی فرم",
              "   اضافه می‌شود."]

    btns.append([{"text": "➕ افزودن آیتم", "callback_data": f"fbia_{field_id}"}])
    btns.append([{"text": ("☑️ چند مورد: روشن" if multi
                           else "1️⃣ فقط یک مورد"),
                  "callback_data": f"fbimt_{field_id}"}])
    if multi:
        btns.append([{"text": f"🔢 سقف انتخاب: "
                              f"{cap_n if cap_n else 'نامحدود'}",
                      "callback_data": f"fbimx_{field_id}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfe_{field_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_multi_item(cid, uid, field_id):
    """
    ☑️ روشن/خاموش کردن انتخاب چندتایی.

    🎯 «توی ثبت‌نام و انتخاب موردهای هزینه‌دار، امکان انتخاب
       چند گزینه باشه»
    """
    try:
        field_id = int(field_id)
    except (TypeError, ValueError):
        return send(cid, "❌ نامعتبر")
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    cur = bool(f.get("multi_item"))
    db_execute("UPDATE form_fields SET multi_item=? WHERE id=?",
               (0 if cur else 1, field_id))
    send(cid, "1️⃣ فقط یک مورد قابل انتخاب است" if cur
              else "☑️ حالا کاربر می‌تواند چند مورد انتخاب کند 💚")
    return show_items(cid, uid, field_id)


def start_max_items(cid, uid, field_id):
    """🔢 سقف تعداد موردهای قابل انتخاب"""
    try:
        field_id = int(field_id)
    except (TypeError, ValueError):
        return send(cid, "❌ نامعتبر")
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    cur = int(f.get("max_items") or 0)
    set_state(uid, STATE_FB_FIELD, {"field_id": field_id,
                                    "key": "max_items"}, merge=False)
    send(cid, (
        f"🔢 سقف تعداد انتخاب\n━━━━━━━━━━━━━━\n\n"
        f"📄 فعلی: {cur if cur else 'بدون محدودیت'}\n\n"
        f"کاربر حداکثر چند مورد بتواند انتخاب کند؟\n\n"
        f"💡 عدد بفرستید — مثال: 3\n"
        f"💡 برای نامحدود، ۰ بفرستید"
    ), kb_cancel())


def start_add_item(cid, uid, field_id, index=None):
    """افزودن/ویرایش آیتم — همه‌چیز در یک پیام"""
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    cur = ""
    if index is not None:
        items = parse_items(f)
        i = int(index)
        if 1 <= i <= len(items):
            it = items[i - 1]
            cur = (f"\n📌 فعلی:\n{it['title']} | {it.get('price', 0)}"
                   f" | {it.get('capacity', 0)}\n")

    set_state(uid, STATE_FB_OPTION,
              {"field_id": field_id, "mode": "item",
               "index": int(index) if index is not None else None,
               "fid": f["form_id"]}, merge=False)
    send(cid, (
        f"{'✏️ ویرایش' if index is not None else '➕ افزودن'} آیتم\n"
        f"━━━━━━━━━━━━━━\n{cur}\n"
        f"در یک خط بنویسید:\n\n"
        f"اسم | هزینه | ظرفیت\n\n"
        f"مثال:\n"
        f"دوره فن بیان | 50000 | 30\n\n"
        f"💡 هزینه به {CURRENCY_LABEL}.\n"
        f"💡 ظرفیت ۰ یا خالی = نامحدود.\n"
        f"💡 برای رایگان: دوره آزاد | 0"
    ), kb_cancel())


def delete_item(cid, uid, field_id, index):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    items = parse_items(f)
    i = int(index)
    if 1 <= i <= len(items):
        items.pop(i - 1)
        set_items(field_id, items)
        touch_form(f["form_id"])
    return show_items(cid, uid, field_id)


# ==================== 📜 متن قوانین ====================
def start_terms_text(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    cur = f.get("terms_text") or "—"
    set_state(uid, STATE_FB_FIELD,
              {"field_id": field_id, "key": "terms_text", "fid": f["form_id"]},
              merge=False)
    send(cid, (
        f"📜 متن قوانین و مقررات\n━━━━━━━━━━━━━━\n\n"
        f"📌 متن فعلی:\n{cur[:600]}\n\n"
        f"متن کاملی که کاربر باید بخواند و تأیید کند را بنویسید:\n\n"
        f"💡 «-» = خالی کردن"
    ), kb_cancel())


def start_add_option(cid, uid, field_id, bulk=False):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    set_state(uid, STATE_FB_OPTION,
              {"field_id": field_id, "mode": "bulk" if bulk else "add",
               "fid": f["form_id"]}, merge=False)
    if bulk:
        return send(cid, (
            "📥 افزودن گروهی گزینه\n━━━━━━━━━━━━━━\n\n"
            "هر گزینه را در یک خط بنویسید:\n\n"
            "مثال:\nگزینه اول\nگزینه دوم\nگزینه سوم"
        ), kb_cancel())
    send(cid, (
        "➕ افزودن گزینه\n━━━━━━━━━━━━━━\n\n"
        "متن گزینه جدید را بنویسید:"
    ), kb_cancel())


def start_edit_option(cid, uid, field_id, index):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    opts = parse_options(f)
    i = int(index)
    if not (1 <= i <= len(opts)):
        return show_options(cid, uid, field_id)
    set_state(uid, STATE_FB_OPTION,
              {"field_id": field_id, "mode": "edit", "index": i,
               "fid": f["form_id"]}, merge=False)
    send(cid, (
        f"✏️ ویرایش گزینه {i}\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی: {opts[i-1]}\n\nمتن جدید:"
    ), kb_cancel())


def handle_option_input(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    field_id = data.get("field_id")
    mode = data.get("mode")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        if mode == "item":
            return show_items(cid, uid, field_id)
        return show_options(cid, uid, field_id)

    f = get_field(field_id)
    if not f:
        clear_state(uid)
        return send(cid, "⚠️ سوال یافت نشد", kb_remove())

    # ---- آیتم قیمت‌دار: «اسم | هزینه | ظرفیت» ----
    if mode == "item":
        parts = [p.strip() for p in text.replace("،", "|").split("|")]
        title = parts[0] if parts else ""
        if not title:
            return send(cid, "⚠️ اسم آیتم را بنویسید:", kb_cancel())

        def _num(x):
            d = "".join(ch for ch in normalize_digits(x or "") if ch.isdigit())
            return int(d) if d else 0

        # هزینه ریال است — عیناً ذخیره می‌شود (بدون تبدیل)
        from config import parse_money
        price = parse_money(parts[1]) if len(parts) > 1 else 0
        cap = _num(parts[2]) if len(parts) > 2 else 0

        if price:
            from config import check_amount
            ok, why = check_amount(price)
            if not ok:
                return send(cid, f"⛔ {why}\n\nدوباره بنویسید:", kb_cancel())

        items = parse_items(f)
        idx = data.get("index")
        if idx and 1 <= int(idx) <= len(items):
            keep = items[int(idx) - 1].get("booked", 0)
            items[int(idx) - 1] = {"title": title[:80], "price": price,
                                   "capacity": cap, "booked": keep, "desc": ""}
            msg_ok = "✅ آیتم ویرایش شد"
        else:
            items.append({"title": title[:80], "price": price,
                          "capacity": cap, "booked": 0, "desc": ""})
            msg_ok = "✅ آیتم اضافه شد"

        set_items(field_id, items)
        clear_state(uid)
        touch_form(f["form_id"])
        send(cid, f"{msg_ok}\n\n🎓 {title}\n"
                  f"💰 {fmt_amount(price) + ' ' + CURRENCY_LABEL if price else 'رایگان'}"
                  + (f"\n👥 ظرفیت: {cap}" if cap else "\n👥 ظرفیت: نامحدود"),
             kb_remove())
        return show_items(cid, uid, field_id)

    opts = parse_options(f)

    if mode == "bulk":
        new = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not new:
            return send(cid, "⚠️ حداقل یک خط بنویسید:", kb_cancel())
        opts.extend(o[:100] for o in new[:50])
        set_options(field_id, opts)
        clear_state(uid)
        touch_form(f["form_id"])
        send(cid, f"✅ {len(new)} گزینه اضافه شد", kb_remove())
        return show_options(cid, uid, field_id)

    if mode == "add":
        if not text:
            return send(cid, "⚠️ متن گزینه را بنویسید:", kb_cancel())
        opts.append(text[:100])
        set_options(field_id, opts)
        clear_state(uid)
        touch_form(f["form_id"])
        send(cid, "✅ گزینه اضافه شد", kb_remove())
        return show_options(cid, uid, field_id)

    if mode == "edit":
        i = int(data.get("index") or 0)
        if not (1 <= i <= len(opts)):
            clear_state(uid)
            return show_options(cid, uid, field_id)
        if not text:
            return send(cid, "⚠️ متن خالی است:", kb_cancel())
        opts[i - 1] = text[:100]
        set_options(field_id, opts)
        clear_state(uid)
        touch_form(f["form_id"])
        send(cid, "✅ ویرایش شد", kb_remove())
        return show_options(cid, uid, field_id)

    clear_state(uid)
    return send(cid, "⚠️ نامعتبر", kb_remove())


def delete_option(cid, uid, field_id, index):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    opts = parse_options(f)
    i = int(index)
    if 1 <= i <= len(opts):
        opts.pop(i - 1)
        set_options(field_id, opts)
        # اگر پاسخ صحیح آزمون به این گزینه بود، پاک شود
        cur = f.get("correct_option")
        if cur and str(cur).isdigit():
            c = int(cur)
            if c == i:
                db_execute("UPDATE form_fields SET correct_option=NULL WHERE id=?",
                           (field_id,))
            elif c > i:
                db_execute("UPDATE form_fields SET correct_option=? WHERE id=?",
                           (str(c - 1), field_id))
        touch_form(f["form_id"])
    return show_options(cid, uid, field_id)


def move_option_up(cid, uid, field_id, index):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    opts = parse_options(f)
    i = int(index)
    if 2 <= i <= len(opts):
        opts[i - 2], opts[i - 1] = opts[i - 1], opts[i - 2]
        set_options(field_id, opts)
        cur = f.get("correct_option")
        if cur and str(cur).isdigit():
            c = int(cur)
            if c == i:
                db_execute("UPDATE form_fields SET correct_option=? WHERE id=?",
                           (str(i - 1), field_id))
            elif c == i - 1:
                db_execute("UPDATE form_fields SET correct_option=? WHERE id=?",
                           (str(i), field_id))
        touch_form(f["form_id"])
    return show_options(cid, uid, field_id)


def clear_options(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    set_options(field_id, [])
    db_execute("UPDATE form_fields SET correct_option=NULL WHERE id=?", (field_id,))
    touch_form(f["form_id"])
    send(cid, "🗑️ همه گزینه‌ها حذف شد")
    return show_options(cid, uid, field_id)


# ==================== شرط نمایش ====================
def show_condition(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    fields = get_fields(f["form_id"])
    idx = next((i for i, x in enumerate(fields) if x["id"] == f["id"]), 0)
    before = fields[:idx]

    lines = ["◇ شرط نمایش سوال", "━━━━━━━━━━━━━━", "",
             f"❓ {field_label(f)[:60]}", ""]

    if f.get("condition_field_id"):
        cf = get_field(f["condition_field_id"])
        op = CONDITION_OPS.get(f.get("condition_operator") or "eq", {})
        lines += [
            "✅ شرط فعلی:",
            f"اگر «{field_label(cf)[:34] if cf else '—'}»",
            f"{op.get('icon','')} {op.get('name','')}",
            f"«{f.get('condition_value') or '(خالی)'}»",
            "",
            "این سوال فقط در این حالت نمایش داده می‌شود.",
        ]
    else:
        lines.append("❌ شرطی تعریف نشده — همیشه نمایش داده می‌شود.")

    if not before:
        lines += ["", "⚠️ برای تعریف شرط، باید حداقل یک سوال قبل از این سوال باشد."]
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"fbfe_{field_id}"}]]})

    btns = [[{"text": "🎯 انتخاب سوال مرجع", "callback_data": f"fbcf_{field_id}"}]]
    if f.get("condition_field_id"):
        btns.append([{"text": "⚙️ تغییر عملگر", "callback_data": f"fbco_{field_id}"}])
        btns.append([{"text": "✏️ تغییر مقدار", "callback_data": f"fbcv_{field_id}"}])
        btns.append([{"text": "🗑️ حذف شرط", "callback_data": f"fbcd_{field_id}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfe_{field_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_condition_field(cid, uid, field_id, ref_id=None):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    if ref_id is not None:
        db_execute("UPDATE form_fields SET condition_field_id=?, condition_operator=? "
                   "WHERE id=?",
                   (int(ref_id), f.get("condition_operator") or "eq", field_id))
        touch_form(f["form_id"])
        return show_condition(cid, uid, field_id)

    fields = get_fields(f["form_id"])
    idx = next((i for i, x in enumerate(fields) if x["id"] == f["id"]), 0)
    before = fields[:idx]
    if not before:
        return show_condition(cid, uid, field_id)

    btns = []
    for i, x in enumerate(before, 1):
        m = field_meta(x.get("field_type"))
        mark = "🔘" if x["id"] == f.get("condition_field_id") else "⚪"
        btns.append([{"text": f"{mark} {i}. {m['icon']} {field_label(x)[:28]}",
                      "callback_data": f"fbcfs_{x['id']}_{field_id}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfcond_{field_id}"}])
    send_or_edit(cid, (
        "🎯 سوال مرجع شرط\n━━━━━━━━━━━━━━\n\n"
        "این سوال بر اساس پاسخ کدام سوال نمایش داده شود؟"
    ), {"inline_keyboard": btns})


def pick_condition_op(cid, uid, field_id, op=None):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    if op is not None:
        if op not in CONDITION_OPS:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE form_fields SET condition_operator=? WHERE id=?",
                   (op, field_id))
        touch_form(f["form_id"])
        if op in ("empty", "nempty"):
            db_execute("UPDATE form_fields SET condition_value='' WHERE id=?", (field_id,))
            return show_condition(cid, uid, field_id)
        return start_condition_value(cid, uid, field_id)

    cur = f.get("condition_operator") or "eq"
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
              "callback_data": f"fbcos_{k}_{field_id}"}] for k, v in CONDITION_OPS.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbfcond_{field_id}"}])
    send_or_edit(cid, "⚙️ عملگر شرط را انتخاب کنید:", {"inline_keyboard": btns})


def start_condition_value(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return

    cf = get_field(f.get("condition_field_id")) if f.get("condition_field_id") else None
    hint = ""
    if cf:
        opts = parse_options(cf)
        if opts:
            hint = "\n\n📋 گزینه‌های سوال مرجع:\n" + "\n".join(f"• {o}" for o in opts[:10])

    set_state(uid, STATE_FB_FIELD,
              {"field_id": field_id, "key": "cond_value", "fid": f["form_id"]},
              merge=False)
    send(cid, (
        f"✏️ مقدار شرط\n━━━━━━━━━━━━━━\n\n"
        f"مقداری که پاسخ سوال مرجع باید با آن مقایسه شود:{hint}"
    ), kb_cancel())


def delete_condition(cid, uid, field_id):
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ یافت نشد")
    if not _guard_form(cid, uid, f["form_id"]):
        return
    db_execute("UPDATE form_fields SET condition_field_id=NULL, "
               "condition_operator=NULL, condition_value=NULL WHERE id=?", (field_id,))
    touch_form(f["form_id"])
    send(cid, "🗑️ شرط حذف شد")
    return show_condition(cid, uid, field_id)


# ==================== ارزیابی شرط (موتور فرم) ====================
def condition_met(field, answers):
    """
    آیا شرط نمایش این فیلد برقرار است؟
    answers: dict {field_id: value_string}
    """
    ref = field.get("condition_field_id")
    if not ref:
        return True
    op = field.get("condition_operator") or "eq"
    expect = str(field.get("condition_value") or "").strip()
    got = answers.get(ref)
    got_s = "" if got is None else str(got).strip()

    if op == "empty":
        return got_s == ""
    if op == "nempty":
        return got_s != ""
    if op == "eq":
        return got_s == expect
    if op == "ne":
        return got_s != expect
    if op == "contains":
        return expect in got_s
    if op == "ncontains":
        return expect not in got_s
    if op in ("gt", "lt"):
        try:
            a = float(normalize_digits(got_s))
            b = float(normalize_digits(expect))
        except (ValueError, TypeError):
            return False
        return a > b if op == "gt" else a < b
    return True


def visible_fields(form_id, answers):
    """فیلدهایی که با توجه به پاسخ‌های فعلی باید نمایش داده شوند"""
    out = []
    for f in get_fields(form_id):
        if condition_met(f, answers):
            out.append(f)
    return out
