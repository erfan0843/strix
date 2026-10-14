"""
🧱 هزینه زیرساخت و خدمات — فاز ۲۴

درخواست کاربر (عیناً):
  «کلا رویداد با هزینه زیر ۲۰ هزار رو موقع ثبت نام به کاربر کلا
   رایگان نشون بده، مبالغ زیر ۲۰ هزار تو رویدادها هزینه زیرساخت و
   خدمات معرفی میشه که این آپشن و مبلغش و جزییاتش تو مالی و پرداخت
   قابل تغییر و تنظیم باشه»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 ایده

  رویدادی که مثلاً ۱۰٬۰۰۰ ریال هزینه دارد، عملاً «رایگان» است —
  آن مبلغ فقط هزینهٔ زیرساخت و خدمات است، نه بهای برنامه.

  پس به کاربر می‌گوییم:
      🎁 رایگان
      (فقط ۱۰٬۰۰۰ ریال هزینه زیرساخت و خدمات)

  💰 مبلغ واقعی دست‌نخورده می‌ماند — فقط «نحوهٔ معرفی» عوض
     می‌شود. هیچ‌جای حسابداری تغییر نمی‌کند.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ همه‌چیز از پنل قابل تنظیم است:
   • روشن/خاموش
   • سقف مبلغ (پیش‌فرض ۲۰٬۰۰۰ ریال)
   • عنوان («هزینه زیرساخت و خدمات»)
   • برچسب رایگان («🎁 رایگان»)
   • توضیح کامل برای کاربر
   • نمایش یا پنهان کردن خود عدد
   • اعمال روی فرم‌ساز هم یا فقط رویداد
"""
from database import db_execute, get_setting, set_setting, log

# (کلید, آیکن, عنوان, نوع, پیش‌فرض, راهنما)
INFRA_SETTINGS = [
    ("infra_on", "🧱", "معرفی به‌عنوان زیرساخت", "bool", "1",
     "مبالغ کم، «رایگان + هزینه زیرساخت» نشان داده شوند"),
    ("infra_max", "💰", "سقف مبلغ", "num", "20000",
     "مبالغ تا این عدد «زیرساخت» حساب می‌شوند (ریال)"),
    ("infra_title", "🏷️", "عنوان هزینه", "text",
     "هزینه زیرساخت و خدمات", "روی صورتحساب و فاکتور می‌نشیند"),
    ("infra_free_label", "🎁", "برچسب رایگان", "text", "🎁 رایگان",
     "چیزی که به‌جای مبلغ نشان داده می‌شود"),
    ("infra_show_amount", "🔢", "نمایش عدد در کنارش", "bool", "1",
     "«رایگان (فقط ۱۰٬۰۰۰ ریال هزینه زیرساخت)»"),
    ("infra_note", "📄", "توضیح برای کاربر", "text",
     "این مبلغ بابت هزینه‌های زیرساخت، درگاه پرداخت و خدمات "
     "پشتیبانی است — نه بهای خود برنامه.",
     "در صفحه رویداد و صورتحساب نمایش داده می‌شود"),
    ("infra_forms", "📝", "اعمال روی فرم‌ساز هم", "bool", "1",
     "فرم‌های کم‌هزینه هم همین‌طور معرفی شوند"),
]


def _row(key):
    for r in INFRA_SETTINGS:
        if r[0] == key:
            return r
    return None


def val(key, dflt=None):
    r = _row(key)
    return get_setting(key, dflt if dflt is not None
                       else (r[4] if r else ""))


def enabled():
    """🧱 آیا معرفی زیرساخت روشن است؟"""
    return val("infra_on", "1") == "1"


def threshold():
    """💰 سقف مبلغ زیرساخت (ریال)"""
    try:
        return max(0, int(val("infra_max", "20000") or 0))
    except (TypeError, ValueError):
        return 20000


def title():
    return (val("infra_title") or "هزینه زیرساخت و خدمات").strip()


def free_label():
    return (val("infra_free_label") or "🎁 رایگان").strip()


def note():
    return (val("infra_note") or "").strip()


def show_amount():
    return val("infra_show_amount", "1") == "1"


def applies_to_forms():
    return val("infra_forms", "1") == "1"


def is_infra(amount, for_form=False):
    """
    🧱 آیا این مبلغ «هزینه زیرساخت» حساب می‌شود؟

    شرط: روشن باشد · مبلغ مثبت باشد · از سقف بیشتر نباشد
    """
    if not enabled():
        return False
    if for_form and not applies_to_forms():
        return False
    try:
        a = int(amount or 0)
    except (TypeError, ValueError):
        return False
    t = threshold()
    return 0 < a <= t


def _fmt(a):
    try:
        from config import money
        return money(a)
    except Exception:
        return f"{int(a):,}"


def price_label(amount, for_form=False, with_note=False):
    """
    🏷️ برچسب نمایشی مبلغ.

    خروجی: (متن, آیا زیرساخت بود)

    🎯 «رویداد با هزینه زیر ۲۰ هزار رو موقع ثبت‌نام به کاربر
       کلا رایگان نشون بده»
    """
    if not is_infra(amount, for_form):
        return "", False
    txt = free_label()
    if show_amount():
        txt += f"\n   ({_fmt(amount)} {title()})"
    if with_note and note():
        txt += f"\n   💡 {note()}"
    return txt, True


def short_label(amount, for_form=False):
    """🏷️ نسخه یک‌خطی برای دکمه و فهرست"""
    if not is_infra(amount, for_form):
        return "", False
    if show_amount():
        return f"{free_label()} · {_fmt(amount)} {title()}", True
    return free_label(), True


def invoice_line(amount, for_form=False):
    """🧾 سطر صورتحساب — عنوان زیرساخت به‌جای «هزینه ثبت‌نام»"""
    if is_infra(amount, for_form):
        return title()
    return ""


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین
# ══════════════════════════════════════════════════════════
STATE_INFRA = "infra_set"


def _guard(cid, uid):
    from bale_api import send
    import permissions as perm
    if not perm.has_perm(uid, "fin_view"):
        send(cid, "🔒 این بخش فقط برای سوپرادمین است")
        return False
    return True


def show_panel(cid, uid):
    """🧱 پنل هزینه زیرساخت"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return

    on = enabled()
    lines = ["🧱 هزینه زیرساخت و خدمات", "━━━━━━━━━━━━━━", "",
             "مبالغ کم به‌جای «هزینه‌دار»، «رایگان» معرفی",
             "می‌شوند — چون واقعاً بهای برنامه نیستند.", ""]

    if on:
        lines += [f"🟢 روشن — مبالغ تا {_fmt(threshold())} ریال", "",
                  "👁️ کاربر این را می‌بیند:", ""]
        demo = min(threshold(), 10000) or threshold()
        lbl, _ = price_label(demo, with_note=True)
        for ln in (lbl or "").split("\n"):
            lines.append(f"   {ln}")
        lines.append("")
    else:
        lines += ["🔴 خاموش — مبالغ عیناً نشان داده می‌شوند", ""]

    lines += ["━━━━━━━━━━━━━━",
              "💰 مبلغ واقعی دست‌نخورده می‌ماند —",
              "   فقط نحوهٔ معرفی عوض می‌شود."]

    btns = []
    for key, icon, name, kind, dflt, hint in INFRA_SETTINGS:
        v = val(key)
        if kind == "bool":
            btns.append([{"text": f"{'✅' if v == '1' else '❌'} "
                                  f"{icon} {name}"[:36],
                          "callback_data": f"infb_{key}"}])
        else:
            shown = str(v)[:16] if str(v).strip() else "—"
            btns.append([{"text": f"{icon} {name}: {shown}"[:36],
                          "callback_data": f"infe_{key}"}])
    btns.append([{"text": "👁️ پیش‌نمایش کامل",
                  "callback_data": "inf_prev"}])
    btns.append([{"text": "🔙 پرداخت و مالی",
                  "callback_data": "set_payment"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle(cid, uid, key):
    from bale_api import send
    if not _guard(cid, uid):
        return
    r = _row(key)
    if not r or r[3] != "bool":
        return send(cid, "❌ نامعتبر")
    cur = val(key) == "1"
    set_setting(key, "0" if cur else "1", r[2], "payment", uid)
    return show_panel(cid, uid)


def start_edit(cid, uid, key):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    r = _row(key)
    if not r:
        return send(cid, "❌ نامعتبر")
    _, icon, name, kind, dflt, hint = r
    set_state(uid, STATE_INFRA, {"key": key}, merge=False)
    txt = [f"✏️ {icon} {name}", "━━━━━━━━━━━━━━", "",
           f"📄 فعلی: {val(key) or '—'}", ""]
    if hint:
        txt += [f"💡 {hint}", ""]
    if kind == "num":
        txt.append("عدد را به ریال بفرستید:")
    else:
        txt.append("متن جدید را بنویسید:")
    txt.append("💡 برای بازگشت به پیش‌فرض، «-» بفرستید")
    send(cid, "\n".join(txt), kb_cancel())


def handle_edit(message):
    from bale_api import send, kb_remove, BTN_BACK
    from auth import get_state_data, clear_state, normalize_digits
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    key = (get_state_data(uid) or {}).get("key")
    r = _row(key)

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)
    if not r:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "-":
        v = r[4]
    elif r[3] == "num":
        d = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not d:
            from bale_api import kb_cancel
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        v = str(int(d))
    else:
        v = raw[:300]

    set_setting(key, v, r[2], "payment", uid)
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {v[:60]}", kb_remove())
    return show_panel(cid, uid)


def show_preview(cid, uid):
    """👁️ پیش‌نمایش — کاربر دقیقاً چه می‌بیند"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    t = threshold()
    samples = [5000, 10000, t, t + 1, 150000]
    lines = ["👁️ پیش‌نمایش", "━━━━━━━━━━━━━━", "",
             f"🧱 سقف فعلی: {_fmt(t)} ریال", ""]
    for a in samples:
        lbl, is_i = price_label(a)
        if is_i:
            lines.append(f"💰 {_fmt(a)} ریال →")
            for ln in lbl.split("\n"):
                lines.append(f"      {ln}")
        else:
            lines.append(f"💰 {_fmt(a)} ریال →  💳 {_fmt(a)} ریال "
                         f"(عادی)")
        lines.append("")
    lines += ["━━━━━━━━━━━━━━",
              "🧾 در صورتحساب، عنوان سطر می‌شود:",
              f"   «{title()}»"]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 هزینه زیرساخت", "callback_data": "pay_infra"}]]})
