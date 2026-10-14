"""
🎟️ صدور گروهی گواهینامه با اکسل و لینک اشتراکی — فاز ۳۲

درخواست کاربر (عیناً):
  «یه امکانی میخوام اضافه کنی اینه که برای یه تعدادی با فایل
   اکسل گواهینامه بزنی و من بتونم با لینک اشتراکش بزارم، طرفم
   بیاد ربات استارت بزنه پروفش تکمیل کنه و گواهیش بگیره با اون
   لینکه که من از بخش صدور گواهی گرفتم»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 جریان کار

  ادمین                          شرکت‌کننده
    │                                │
  اکسل می‌فرستد                      │
    │  (نام · موبایل · کدملی)        │
    ▼                                │
  دستهٔ گواهینامه ساخته می‌شود        │
    │                                │
  لینک می‌گیرد ────اشتراک────►  لینک را باز می‌کند
    │                                │
    │                          /start می‌خورد
    │                                ▼
    │                          پروفایل تکمیل
    │                                ▼
    │                          موبایلش در لیست؟
    │                                ▼
    └──────────────────────►   🎓 گواهینامه صادر

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 تطبیق هویت — سه روش (قابل انتخاب)
   📱 موبایل   · مطمئن‌ترین (تأییدشده با پیامک)
   🆔 کد ملی   · وقتی موبایل ندارید
   🎫 کد اختصاصی · هر نفر کد جدا می‌گیرد
"""
from privacy import user_error_message
import json
import re
import secrets
from datetime import datetime
from pathlib import Path

from config import FILES_DIR
from database import db_execute, db_scalar, get_setting, log
from bale_api import send, send_or_edit, send_document, kb_cancel

BATCH_DIR = Path(FILES_DIR) / "cert_batches"

# 🔐 روش‌های تطبیق هویت
MATCH_BY = {
    "mobile":      ("📱 شمارهٔ موبایل", "مطمئن‌ترین — با پیامک تأیید شده"),
    "national_id": ("🆔 کد ملی", "وقتی شماره ندارید"),
    "code":        ("🎫 کد اختصاصی", "هر نفر کد جدا می‌گیرد"),
}

# 📊 ستون‌های شناخته‌شدهٔ اکسل — با نام‌های محتمل
COLUMNS = {
    "full_name": ["نام", "نام و نام خانوادگی", "نام کامل", "نام‌ونام‌خانوادگی",
                  "name", "fullname", "full name", "اسم"],
    "mobile": ["موبایل", "شماره", "تلفن", "شماره موبایل", "همراه",
               "mobile", "phone", "tel"],
    "national_id": ["کدملی", "کد ملی", "شناسه ملی", "کد‌ملی",
                    "national_id", "nid", "melli"],
    "score": ["نمره", "امتیاز", "score", "grade"],
    "hours": ["ساعت", "مدت", "hours", "duration"],
    "grade": ["رتبه", "درجه", "rank"],
    "role": ["نقش", "سمت", "عنوان", "role", "title"],
}


def _norm_col(s):
    """نرمال‌سازی نام ستون برای مقایسه"""
    return re.sub(r"[\s\u200c_\-]+", "", str(s or "").strip().lower())


def detect_column(header):
    """🔍 این ستون اکسل کدام فیلد است؟"""
    h = _norm_col(header)
    if not h:
        return None
    for key, names in COLUMNS.items():
        for n in names:
            if _norm_col(n) == h:
                return key
    # 🔍 تطبیق نرم — فقط برای عنوان‌های به‌قدر کافی بلند
    #
    # 🔴 باگ رفع‌شده: بدون شرط طول، تک‌حرف‌ها فاجعه می‌ساختند:
    #    «ب» → mobile (چون «ب» در «موبایل» هست)
    #    «ج» → grade  (چون «ج» در «درجه» هست)
    #    نتیجه: ستون‌های بی‌ربط به‌عنوان موبایل خوانده می‌شدند.
    if len(h) < 3:
        return None
    for key, names in COLUMNS.items():
        for n in names:
            nn = _norm_col(n)
            if len(nn) < 3:
                continue
            if nn in h or h in nn:
                return key
    return None


def _digits(s):
    """ارقام فارسی/عربی → لاتین، فقط رقم نگه‌دار"""
    t = str(s or "").translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return re.sub(r"\D", "", t)


def norm_mobile(s):
    """📱 نرمال‌سازی موبایل به فرم ۰۹xxxxxxxxx"""
    d = _digits(s)
    if not d:
        return ""
    if d.startswith("0098"):
        d = "0" + d[4:]
    elif d.startswith("98") and len(d) == 12:
        d = "0" + d[2:]
    elif len(d) == 10 and d.startswith("9"):
        d = "0" + d
    return d if len(d) == 11 and d.startswith("09") else ""


def valid_nid(s):
    """🆔 اعتبارسنجی کد ملی با الگوریتم چک‌سام"""
    d = _digits(s)
    if len(d) != 10 or len(set(d)) == 1:
        return ""
    c = int(d[9])
    t = sum(int(d[i]) * (10 - i) for i in range(9)) % 11
    return d if (t < 2 and c == t) or (t >= 2 and c == 11 - t) else ""


# ══════════════════════════════════════════════════════════
# 📥 خواندن اکسل
# ══════════════════════════════════════════════════════════
def parse_excel(path):
    """
    📊 خواندن فایل اکسل و تشخیص خودکار ستون‌ها.

    خروجی: (ردیف‌ها، نقشهٔ ستون‌ها، خطاها)
    """
    try:
        import openpyxl
    except ImportError:
        return [], {}, ["openpyxl نصب نیست"]
    try:
        wb = openpyxl.load_workbook(str(path), data_only=True)
        ws = wb.active
    except Exception as e:
        return [], {}, [f"خواندن فایل ناموفق: {str(e)[:80]}"]

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], {}, ["فایل خالی است"]

    # 🔍 سطر عنوان را پیدا کن (اولین سطری که ستون شناخته‌شده دارد)
    head_i, cmap = 0, {}
    for i, r in enumerate(rows[:5]):
        m = {}
        for j, cell in enumerate(r):
            k = detect_column(cell)
            if k and k not in m:
                m[k] = j
        if "full_name" in m or ("mobile" in m or "national_id" in m):
            head_i, cmap = i, m
            break
    if not cmap:
        return [], {}, ["ستون «نام» یا «موبایل» پیدا نشد — "
                        "سطر اول باید عنوان ستون‌ها باشد"]

    # 🗂️ ستون‌های ناشناخته → extra
    known = set(cmap.values())
    extra_cols = {}
    for j, cell in enumerate(rows[head_i]):
        if j not in known and cell:
            extra_cols[j] = str(cell).strip()

    out, errs = [], []
    seen = set()
    for n, r in enumerate(rows[head_i + 1:], head_i + 2):
        if not any(x not in (None, "") for x in r):
            continue

        def _g(key):
            j = cmap.get(key)
            if j is None or j >= len(r):
                return ""
            v = r[j]
            return "" if v is None else str(v).strip()

        name = _g("full_name")
        mob = norm_mobile(_g("mobile"))
        nid = valid_nid(_g("national_id"))

        if not (name or mob or nid):
            continue
        if not name:
            errs.append(f"سطر {n}: نام خالی است")
            continue
        if _g("mobile") and not mob:
            errs.append(f"سطر {n}: موبایل «{_g('mobile')}» نامعتبر")
        if _g("national_id") and not nid:
            errs.append(f"سطر {n}: کد ملی «{_g('national_id')}» نامعتبر")

        dup = mob or nid or name
        if dup in seen:
            errs.append(f"سطر {n}: تکراری ({dup})")
            continue
        seen.add(dup)

        extra = {}
        for key in ("score", "hours", "grade", "role"):
            v = _g(key)
            if v:
                extra[key] = v
        for j, title in extra_cols.items():
            if j < len(r) and r[j] not in (None, ""):
                extra[title] = str(r[j]).strip()

        out.append({"full_name": name, "mobile": mob,
                    "national_id": nid, "extra": extra})

    return out, cmap, errs


def sample_excel(path=None):
    """📄 ساخت فایل نمونه برای ادمین"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return None
    p = Path(path or (BATCH_DIR / "نمونه-گواهینامه.xlsx"))
    p.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "لیست"
    ws.sheet_view.rightToLeft = True
    cols = ["نام و نام خانوادگی", "موبایل", "کد ملی", "نمره", "ساعت"]
    ws.append(cols)
    for i in range(1, len(cols) + 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4472C4")
        c.alignment = Alignment(horizontal="center")
        ws.column_dimensions[
            openpyxl.utils.get_column_letter(i)].width = 22
    ws.append(["علی رضایی", "09121234567", "0012345678", "18", "8"])
    ws.append(["مریم احمدی", "09129876543", "", "20", "8"])
    ws.freeze_panes = "A2"
    ws2 = wb.create_sheet("راهنما")
    ws2.sheet_view.rightToLeft = True
    for ln in [
        ["📋 راهنمای فایل"],
        [""],
        ["• سطر اول باید عنوان ستون‌ها باشد"],
        ["• «نام و نام خانوادگی» اجباری است"],
        ["• «موبایل» یا «کد ملی» — حداقل یکی لازم است"],
        ["• موبایل با ۰۹ شروع شود (۱۱ رقم)"],
        ["• ستون‌های اضافه هم خوانده می‌شوند و در"],
        ["  گواهینامه قابل استفاده‌اند"],
        [""],
        ["🔐 روش تطبیق را موقع ساخت دسته انتخاب می‌کنید"],
    ]:
        ws2.append(ln)
    ws2.column_dimensions["A"].width = 60
    wb.save(str(p))
    return str(p)


# ══════════════════════════════════════════════════════════
# 🎟️ دسته
# ══════════════════════════════════════════════════════════
def _new_code():
    for _ in range(20):
        c = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
        if not db_scalar("SELECT COUNT(*) FROM cert_batches WHERE code=?",
                         (c,)):
            return c
    return secrets.token_hex(5)


def create_batch(title, rows, template_id=None, event_id=None,
                 match_by="mobile", params=None, uid=None, **kw):
    """🎟️ ساخت دستهٔ تازه و ثبت ردیف‌ها"""
    code = _new_code()
    bid = db_execute(
        "INSERT INTO cert_batches (code, title, template_id, event_id, "
        "params, match_by, require_profile, expires_at, max_claims, "
        "total, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (code, title, template_id, event_id,
         json.dumps(params or {}, ensure_ascii=False), match_by,
         1 if kw.get("require_profile", True) else 0,
         kw.get("expires_at") or "", int(kw.get("max_claims") or 0),
         len(rows), uid))
    for r in rows:
        db_execute(
            "INSERT INTO cert_batch_rows (batch_id, full_name, mobile, "
            "national_id, claim_code, extra) VALUES (?,?,?,?,?,?)",
            (bid, r.get("full_name") or "", r.get("mobile") or "",
             r.get("national_id") or "",
             secrets.token_hex(3).upper() if match_by == "code" else "",
             json.dumps(r.get("extra") or {}, ensure_ascii=False)))
    log(f"🎟️ دستهٔ گواهینامه #{bid} با {len(rows)} نفر ساخته شد")
    return bid, code


def get_batch(bid=None, code=None):
    if code:
        return db_execute("SELECT * FROM cert_batches WHERE code=?",
                          (str(code),), fetch="one")
    return db_execute("SELECT * FROM cert_batches WHERE id=?",
                      (int(bid),), fetch="one")


def list_batches(limit=30):
    return db_execute("SELECT * FROM cert_batches WHERE is_active=1 "
                      "ORDER BY id DESC LIMIT ?", (int(limit),),
                      fetch="all") or []


def batch_rows(bid, status=None, limit=500):
    q = "SELECT * FROM cert_batch_rows WHERE batch_id=?"
    a = [int(bid)]
    if status:
        q += " AND status=?"
        a.append(status)
    q += " ORDER BY id LIMIT ?"
    a.append(int(limit))
    return db_execute(q, tuple(a), fetch="all") or []


def batch_stats(bid):
    """📊 آمار یک دسته"""
    def _c(st=None):
        q = "SELECT COUNT(*) FROM cert_batch_rows WHERE batch_id=?"
        a = [int(bid)]
        if st:
            q += " AND status=?"
            a.append(st)
        return db_scalar(q, tuple(a)) or 0
    total = _c()
    issued = _c("issued")
    return {"total": total, "issued": issued,
            "pending": total - issued,
            "pct": round(issued * 100.0 / total) if total else 0}


def batch_link(code):
    """🔗 لینک اشتراکی دسته"""
    try:
        from config import deep_link
        return deep_link(f"gc_{code}") or f"/start gc_{code}"
    except Exception:
        return f"/start gc_{code}"


def toggle_batch(bid, on=None):
    b = get_batch(bid)
    if not b:
        return
    v = (0 if b.get("is_active") else 1) if on is None else (1 if on else 0)
    db_execute("UPDATE cert_batches SET is_active=? WHERE id=?",
               (v, int(bid)))
    return v


def delete_batch(bid):
    db_execute("DELETE FROM cert_batch_rows WHERE batch_id=?", (int(bid),))
    db_execute("DELETE FROM cert_batches WHERE id=?", (int(bid),))


# ══════════════════════════════════════════════════════════
# 🔍 تطبیق کاربر با ردیف
# ══════════════════════════════════════════════════════════
def find_row(batch, user, claim_code=None):
    """
    🔍 کدام ردیف اکسل مال این کاربر است؟

    خروجی: (ردیف یا None، دلیل ناکامی)
    """
    bid = batch["id"]
    by = (batch.get("match_by") or "mobile").strip()

    if by == "code":
        if not claim_code:
            return None, "کد اختصاصی لازم است"
        r = db_execute(
            "SELECT * FROM cert_batch_rows WHERE batch_id=? AND "
            "UPPER(claim_code)=?", (bid, str(claim_code).upper()),
            fetch="one")
        return (r, "") if r else (None, "کد وارد‌شده در لیست نیست")

    if by == "national_id":
        nid = valid_nid(user.get("national_id"))
        if not nid:
            return None, "کد ملی در پروفایل شما ثبت نشده"
        r = db_execute(
            "SELECT * FROM cert_batch_rows WHERE batch_id=? AND "
            "national_id=?", (bid, nid), fetch="one")
        return (r, "") if r else (None, "کد ملی شما در این لیست نیست")

    mob = norm_mobile(user.get("mobile"))
    if not mob:
        return None, "شمارهٔ موبایل در پروفایل شما ثبت نشده"
    r = db_execute(
        "SELECT * FROM cert_batch_rows WHERE batch_id=? AND mobile=?",
        (bid, mob), fetch="one")
    return (r, "") if r else (None, "شمارهٔ شما در این لیست نیست")


def can_claim(batch):
    """⏱️ آیا این دسته هنوز فعال و در مهلت است؟"""
    if not batch:
        return False, "این لینک معتبر نیست"
    if not batch.get("is_active"):
        return False, "این لینک غیرفعال شده است"
    exp = (batch.get("expires_at") or "").strip()
    if exp:
        try:
            if datetime.now() > datetime.fromisoformat(exp):
                return False, "مهلت این لینک تمام شده است"
        except Exception:
            pass
    mx = int(batch.get("max_claims") or 0)
    if mx and int(batch.get("claimed") or 0) >= mx:
        return False, "ظرفیت این لینک تکمیل شده است"
    return True, ""


def mark_claimed(row_id, user_id, cert_id=None):
    """✅ ثبت دریافت"""
    db_execute(
        "UPDATE cert_batch_rows SET status='issued', claimed_by=?, "
        "cert_id=?, claimed_at=datetime('now') WHERE id=?",
        (int(user_id), cert_id, int(row_id)))
    r = db_execute("SELECT batch_id FROM cert_batch_rows WHERE id=?",
                   (int(row_id),), fetch="one")
    if r:
        db_execute("UPDATE cert_batches SET claimed=claimed+1 WHERE id=?",
                   (r["batch_id"],))


def build_mapping(batch, row, user):
    """🗂️ ساخت نقشهٔ پارامترها برای این نفر"""
    try:
        params = json.loads(batch.get("params") or "{}")
    except Exception:
        params = {}
    try:
        extra = json.loads(row.get("extra") or "{}")
    except Exception:
        extra = {}

    mp = dict(params)
    mp["name"] = row.get("full_name") or ""
    if row.get("national_id"):
        mp["national_id"] = row["national_id"]
    if row.get("mobile"):
        mp["mobile"] = row["mobile"]
    for k, v in extra.items():
        mp.setdefault(k, v)

    if batch.get("event_id"):
        try:
            ev = db_execute("SELECT * FROM events WHERE id=?",
                            (batch["event_id"],), fetch="one") or {}
            mp.setdefault("event", ev.get("title") or "")
            mp.setdefault("date", ev.get("start_date") or "")
        except Exception:
            pass
    return mp


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    """🛡️ بررسی ادمین — منطق مشترک در helpers"""
    from helpers import guard_admin
    return guard_admin(cid, uid)


def _fa(n):
    """🔢 ارقام فارسی — منطق مشترک در helpers"""
    from helpers import fa
    return fa(n)


def show_panel(cid, uid):
    """🎟️ مرکز صدور گروهی با اکسل"""
    if not _guard(cid, uid):
        return
    bs = list_batches()
    lines = ["🎟️ صدور گروهی با اکسل", "━━━━━━━━━━━━━━", "",
             "لیست اسامی را از اکسل بدهید، لینک بگیرید،",
             "و لینک را منتشر کنید. هرکس با آن لینک بیاید،",
             "پروفایلش را تکمیل کند و گواهینامه‌اش را بگیرد.", ""]

    if not bs:
        lines += ["📭 هنوز دسته‌ای نساخته‌اید.", ""]
    else:
        lines.append(f"📊 {_fa(len(bs))} دسته:")
        lines.append("")
        for b in bs[:8]:
            s = batch_stats(b["id"])
            on = "🟢" if b.get("is_active") else "⚪"
            lines.append(f"{on} {b.get('title') or 'بی‌نام'}")
            lines.append(f"      👥 {_fa(s['issued'])} از "
                         f"{_fa(s['total'])} ({_fa(s['pct'])}٪)")
            lines.append("")

    btns = [[{"text": "➕ دستهٔ تازه از اکسل",
              "callback_data": "cb_new"}]]
    for b in bs[:8]:
        s = batch_stats(b["id"])
        btns.append([{"text": f"{'🟢' if b.get('is_active') else '⚪'} "
                              f"{(b.get('title') or 'بی‌نام')[:20]} "
                              f"({_fa(s['issued'])}/{_fa(s['total'])})",
                      "callback_data": f"cb_v_{b['id']}"}])
    btns.append([{"text": "📄 دریافت فایل نمونه",
                  "callback_data": "cb_sample"}])
    btns.append([{"text": "🔙 گواهینامه و بلیط",
                  "callback_data": "ct_hub"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_batch(cid, uid, bid):
    """📋 جزئیات یک دسته"""
    if not _guard(cid, uid):
        return
    b = get_batch(bid)
    if not b:
        return send(cid, "❌ پیدا نشد")
    s = batch_stats(bid)
    link = batch_link(b["code"])
    by = MATCH_BY.get(b.get("match_by") or "mobile", ("—", ""))[0]

    lines = [f"🎟️ {b.get('title') or 'بی‌نام'}", "━━━━━━━━━━━━━━", "",
             f"👥 {_fa(s['total'])} نفر در لیست",
             f"✅ {_fa(s['issued'])} گرفته‌اند ({_fa(s['pct'])}٪)",
             f"⏳ {_fa(s['pending'])} باقی مانده", "",
             f"🔐 تطبیق با: {by}",
             f"{'🟢 فعال' if b.get('is_active') else '⚪ غیرفعال'}"]
    exp = (b.get("expires_at") or "").strip()
    if exp:
        lines.append(f"⏰ مهلت: {exp[:16]}")
    mx = int(b.get("max_claims") or 0)
    if mx:
        lines.append(f"🔢 سقف: {_fa(mx)} نفر")
    lines += ["", "🔗 لینک اشتراکی:", f"{link}", "",
              "💡 این لینک را منتشر کنید. هرکس بازش کند،",
              "   ربات راهنمایی‌اش می‌کند."]

    btns = [
        [{"text": "📤 ارسال لینک", "callback_data": f"cb_link_{bid}"}],
        [{"text": f"👥 لیست ({_fa(s['total'])})",
          "callback_data": f"cb_rows_{bid}_0"}],
        [{"text": "🔐 روش تطبیق", "callback_data": f"cb_by_{bid}"},
         {"text": "📄 قالب", "callback_data": f"cb_tpl_{bid}"}],
        [{"text": "⏰ مهلت", "callback_data": f"cbe_exp_{bid}"},
         {"text": "🔢 سقف", "callback_data": f"cbe_max_{bid}"}],
        [{"text": f"{'⚪ خاموش کن' if b.get('is_active') else '🟢 روشن کن'}",
          "callback_data": f"cb_tog_{bid}"}],
        [{"text": "📊 خروجی اکسل وضعیت",
          "callback_data": f"cb_exp_{bid}"}],
        [{"text": "🗑️ حذف دسته", "callback_data": f"cb_del_{bid}"}],
        [{"text": "🔙 صدور گروهی", "callback_data": "cb_home"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_new(cid, uid):
    """➕ شروع ساخت دسته — دریافت اکسل"""
    if not _guard(cid, uid):
        return
    from auth import set_state
    set_state(uid, "cb_wait_file", {})
    send(cid, (
        "📊 فایل اکسل را بفرستید\n━━━━━━━━━━━━━━\n\n"
        "ستون‌های لازم:\n"
        "   • نام و نام خانوادگی (اجباری)\n"
        "   • موبایل یا کد ملی (حداقل یکی)\n\n"
        "ستون‌های اختیاری:\n"
        "   • نمره · ساعت · رتبه · نقش\n"
        "   • هر ستون دیگری که بخواهید\n\n"
        "💡 سطر اول باید عنوان ستون‌ها باشد.\n"
        "📄 اگر نمونه می‌خواهید، «انصراف» بزنید و\n"
        "   «دریافت فایل نمونه» را انتخاب کنید."), kb_cancel())


def send_sample(cid, uid):
    """📄 ارسال فایل نمونه"""
    if not _guard(cid, uid):
        return
    p = sample_excel()
    if not p:
        return send(cid, "❌ openpyxl نصب نیست")
    send_document(cid, p, (
        "📄 فایل نمونه\n\n"
        "ستون‌ها را همین‌طور نگه دارید و ردیف‌ها را\n"
        "با اسامی خودتان پر کنید."))
    return show_panel(cid, uid)


def handle_document(message):
    """📥 دریافت فایل اکسل"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    from auth import (get_state_data, get_state_name,
                      clear_state, set_state)
    # 🔴 باگ رفع‌شده (فاز ۳۹): get_state_data فقط **دیکشنری**
    #    برمی‌گرداند، نه (نام، داده). این unpack غلط بود و
    #    ValueError می‌داد — یعنی هیچ ورودی متنی پردازش
    #    نمی‌شد. نام state را جدا می‌گیریم.
    st = get_state_name(uid)
    data = get_state_data(uid)
    if st != "cb_wait_file":
        return False

    doc = message.get("document") or {}
    fname = str(doc.get("file_name") or "").lower()
    if not fname.endswith((".xlsx", ".xlsm")):
        send(cid, "⚠️ فقط فایل اکسل (xlsx) قبول است")
        return True

    try:
        # 🔴 باگ رفع‌شده (فاز ۳۶) — «اکسل قبول نمیکنه»:
        #    اینجا `download_file(file_id, dest)` صدا زده می‌شد،
        #    ولی امضای واقعی تابع `download_file(file_path)` است
        #    و **محتوای بایتی** برمی‌گرداند، نه bool.
        #    نتیجه: TypeError → پیام «دریافت فایل: …» و هیچ
        #    فایلی هرگز خوانده نمی‌شد.
        #
        #    مسیر درست (مثل import_excel.py و events.py):
        #      getFile → file_path → download_file → write
        from bale_api import get_file_info, download_file
        fi = get_file_info(doc.get("file_id")) or {}
        fpath = (fi.get("result") or {}).get("file_path")
        if not fpath:
            send(cid, "❌ آدرس فایل از بله دریافت نشد — دوباره بفرستید")
            return True
        content = download_file(fpath)
        if not content:
            send(cid, "❌ دانلود فایل ناموفق بود — دوباره بفرستید")
            return True
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        dest = BATCH_DIR / f"in_{uid}_{secrets.token_hex(3)}.xlsx"
        dest.write_bytes(content)
    except Exception as e:
        log(f"⚠️ دریافت اکسل: {e}")
        send(cid, f"❌ دریافت فایل: {user_error_message(e)}")
        return True

    rows, cmap, errs = parse_excel(dest)
    if not rows:
        clear_state(uid)
        msg = "❌ هیچ ردیف معتبری پیدا نشد\n\n"
        if errs:
            msg += "\n".join(f"   • {e}" for e in errs[:8])
        send(cid, msg)
        return True

    set_state(uid, "cb_title", {"file": str(dest), "n": len(rows)})
    lines = ["✅ فایل خوانده شد", "━━━━━━━━━━━━━━", "",
             f"👥 {_fa(len(rows))} نفر معتبر"]
    found = [k for k in ("full_name", "mobile", "national_id",
                         "score") if k in cmap]
    fa = {"full_name": "نام", "mobile": "موبایل",
          "national_id": "کد ملی", "score": "نمره"}
    lines.append(f"🗂️ ستون‌ها: {' · '.join(fa.get(k, k) for k in found)}")
    if errs:
        lines += ["", f"⚠️ {_fa(len(errs))} هشدار:"]
        lines += [f"   • {e}" for e in errs[:5]]
        if len(errs) > 5:
            lines.append(f"   … و {_fa(len(errs)-5)} مورد دیگر")
    lines += ["", "━━━━━━━━━━━━━━", "",
              "📝 حالا یک عنوان برای این دسته بنویسید:", "",
              "مثال: «گواهینامهٔ کارگاه فن بیان — مهر ۱۴۰۴»"]
    send(cid, "\n".join(lines), kb_cancel())
    return True


def handle_text(message):
    """📝 ورودی متنی"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    from auth import (get_state_data, get_state_name,
                      clear_state, set_state)
    # 🔴 باگ رفع‌شده (فاز ۳۹): get_state_data فقط **دیکشنری**
    #    برمی‌گرداند، نه (نام، داده). این unpack غلط بود و
    #    ValueError می‌داد — یعنی هیچ ورودی متنی پردازش
    #    نمی‌شد. نام state را جدا می‌گیریم.
    st = get_state_name(uid)
    data = get_state_data(uid)
    if not st or not st.startswith("cb_"):
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel"):
        clear_state(uid)
        from bale_api import kb_remove
        send(cid, "✅ لغو شد", kb_remove())
        return True

    if st == "cb_wait_file":
        send(cid, "⚠️ لطفاً فایل اکسل بفرستید یا «انصراف» بزنید")
        return True

    if st == "cb_title":
        if len(txt) < 3:
            send(cid, "⚠️ عنوان خیلی کوتاه است")
            return True
        rows, _c, _e = parse_excel(data.get("file"))
        if not rows:
            clear_state(uid)
            send(cid, "❌ فایل دیگر در دسترس نیست")
            return True
        bid, code = create_batch(txt[:80], rows, uid=uid)
        clear_state(uid)
        from bale_api import kb_remove
        send(cid, "✅ دسته ساخته شد", kb_remove())
        show_batch(cid, uid, bid)
        return True

    if st == "cb_edit":
        bid = data.get("bid")
        field = data.get("field")
        if field == "max":
            try:
                # 🔴 باگ رفع‌شده (فاز ۴۰): normalize_digits در
                #    auth.py است نه config.py — ImportError باعث
                #    می‌شد ادمین عدد درست بنویسد ولی پیام
                #    «⚠️ یک عدد بنویسید» بگیرد.
                from auth import normalize_digits
                v = max(0, int(normalize_digits(txt)))
            except Exception:
                send(cid, "⚠️ یک عدد بنویسید")
                return True
            db_execute("UPDATE cert_batches SET max_claims=? WHERE id=?",
                       (v, int(bid)))
        elif field == "exp":
            db_execute("UPDATE cert_batches SET expires_at=? WHERE id=?",
                       (txt[:20], int(bid)))
        clear_state(uid)
        from bale_api import kb_remove
        send(cid, "✅ ذخیره شد", kb_remove())
        show_batch(cid, uid, bid)
        return True
    return False


def start_edit(cid, uid, field, bid):
    if not _guard(cid, uid):
        return
    from auth import set_state
    set_state(uid, "cb_edit", {"bid": int(bid), "field": field})
    if field == "max":
        send(cid, ("🔢 حداکثر چند نفر بتوانند بگیرند؟\n\n"
                   "۰ = بدون محدودیت"), kb_cancel())
    else:
        send(cid, ("⏰ مهلت را بنویسید:\n\n"
                   "قالب: ۱۴۰۴-۰۸-۱۵\n"
                   "خالی بگذارید = بدون مهلت"), kb_cancel())


def show_match(cid, uid, bid):
    """🔐 انتخاب روش تطبیق"""
    if not _guard(cid, uid):
        return
    b = get_batch(bid)
    if not b:
        return send(cid, "❌ پیدا نشد")
    cur = b.get("match_by") or "mobile"
    lines = ["🔐 روش تشخیص هویت", "━━━━━━━━━━━━━━", "",
             "وقتی کسی لینک را باز می‌کند، از کجا بفهمیم",
             "کدام ردیف اکسل مال اوست؟", ""]
    btns = []
    for k, (nm, desc) in MATCH_BY.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {nm}")
        lines.append(f"     {desc}")
        btns.append([{"text": f"{mark} {nm}",
                      "callback_data": f"cbB_{k}_{bid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cb_v_{bid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_match(cid, uid, by, bid):
    if not _guard(cid, uid):
        return
    if by not in MATCH_BY:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE cert_batches SET match_by=? WHERE id=?",
               (by, int(bid)))
    if by == "code":
        for r in batch_rows(bid):
            if not r.get("claim_code"):
                db_execute("UPDATE cert_batch_rows SET claim_code=? "
                           "WHERE id=?",
                           (secrets.token_hex(3).upper(), r["id"]))
    return show_match(cid, uid, bid)


def show_rows(cid, uid, bid, page=0):
    """👥 لیست اسامی"""
    if not _guard(cid, uid):
        return
    rows = batch_rows(bid)
    if not rows:
        return send(cid, "📭 لیست خالی است")
    per, page = 10, max(0, int(page or 0))
    pages = max(1, (len(rows) + per - 1) // per)
    page = min(page, pages - 1)
    chunk = rows[page * per:(page + 1) * per]
    b = get_batch(bid)
    by = b.get("match_by") or "mobile"

    lines = [f"👥 لیست — {b.get('title') or ''}", "━━━━━━━━━━━━━━", ""]
    for r in chunk:
        icon = "✅" if r.get("status") == "issued" else "⏳"
        lines.append(f"{icon} {r.get('full_name') or '—'}")
        if by == "code":
            lines.append(f"      🎫 {r.get('claim_code') or '—'}")
        elif by == "national_id":
            lines.append(f"      🆔 {r.get('national_id') or '—'}")
        else:
            lines.append(f"      📱 {r.get('mobile') or '—'}")
    btns = []
    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️",
                        "callback_data": f"cb_rows_{bid}_{page-1}"})
        nav.append({"text": f"{_fa(page+1)}/{_fa(pages)}",
                    "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️",
                        "callback_data": f"cb_rows_{bid}_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "🔙 دسته", "callback_data": f"cb_v_{bid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def send_link(cid, uid, bid):
    """📤 ارسال لینک برای اشتراک"""
    if not _guard(cid, uid):
        return
    b = get_batch(bid)
    if not b:
        return send(cid, "❌ پیدا نشد")
    link = batch_link(b["code"])
    by = MATCH_BY.get(b.get("match_by") or "mobile", ("—",))[0]
    txt = (f"🎓 {b.get('title') or 'گواهینامه'}\n\n"
           f"برای دریافت گواهینامه‌تان روی لینک زیر بزنید:\n\n"
           f"{link}\n\n"
           f"💡 بعد از باز شدن ربات، پروفایلتان را کامل کنید.\n"
           f"🔐 تشخیص هویت با {by} انجام می‌شود.")
    send(cid, "📤 متن آمادهٔ اشتراک‌گذاری:")
    send(cid, txt)
    return show_batch(cid, uid, bid)


def export_status(cid, uid, bid):
    """📊 خروجی اکسل وضعیت"""
    if not _guard(cid, uid):
        return
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست")
    b = get_batch(bid)
    # 🔴 باگ رفع‌شده (فاز ۴۰): اگر دسته حذف شده بود ولی دکمه‌اش
    #    در پیام قدیمی مانده بود، get_batch مقدار None می‌داد و
    #    خط بعد با AttributeError می‌مرد.
    if not b:
        return send(cid, "🌱 این دسته دیگر وجود ندارد",
                    {"inline_keyboard": [
                        [{"text": "🔙 مرکز صدور",
                          "callback_data": "cc_home"}]]})
    rows = batch_rows(bid)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "وضعیت"
    ws.sheet_view.rightToLeft = True
    cols = ["ردیف", "نام", "موبایل", "کد ملی", "کد اختصاصی",
            "وضعیت", "تاریخ دریافت"]
    ws.append(cols)
    for i in range(1, len(cols) + 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4472C4")
        ws.column_dimensions[
            openpyxl.utils.get_column_letter(i)].width = 20
    for n, r in enumerate(rows, 1):
        ws.append([n, r.get("full_name") or "", r.get("mobile") or "",
                   r.get("national_id") or "", r.get("claim_code") or "",
                   "دریافت شده" if r.get("status") == "issued"
                   else "در انتظار",
                   str(r.get("claimed_at") or "")[:19]])
    ws.freeze_panes = "A2"
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    p = BATCH_DIR / f"status_{bid}.xlsx"
    wb.save(str(p))
    s = batch_stats(bid)
    send_document(cid, str(p), (
        f"📊 وضعیت «{b.get('title') or ''}»\n\n"
        f"✅ {_fa(s['issued'])} از {_fa(s['total'])} دریافت کرده‌اند"))
    return show_batch(cid, uid, bid)


def toggle_active(cid, uid, bid):
    if not _guard(cid, uid):
        return
    toggle_batch(bid)
    return show_batch(cid, uid, bid)


def confirm_delete(cid, uid, bid):
    if not _guard(cid, uid):
        return
    b = get_batch(bid)
    if not b:
        return send(cid, "❌ پیدا نشد")
    s = batch_stats(bid)
    send_or_edit(cid, (
        f"🗑️ حذف «{b.get('title') or ''}»\n━━━━━━━━━━━━━━\n\n"
        f"👥 {_fa(s['total'])} نفر در لیست\n"
        f"✅ {_fa(s['issued'])} گواهینامه گرفته‌اند\n\n"
        f"⚠️ لینک از کار می‌افتد.\n"
        f"💚 گواهینامه‌های صادرشده پاک نمی‌شوند.\n\n"
        f"مطمئنید؟"), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن",
              "callback_data": f"cbD_{bid}"}],
            [{"text": "🔙 نه", "callback_data": f"cb_v_{bid}"}]]})


def do_delete(cid, uid, bid):
    if not _guard(cid, uid):
        return
    delete_batch(bid)
    send(cid, "🗑️ حذف شد")
    return show_panel(cid, uid)


def show_tpl(cid, uid, bid):
    """📄 انتخاب قالب دسته"""
    if not _guard(cid, uid):
        return
    b = get_batch(bid)
    if not b:
        return send(cid, "❌ پیدا نشد")
    try:
        tpls = db_execute(
            "SELECT * FROM cert_templates WHERE is_active=1 "
            "ORDER BY is_default DESC, id DESC", fetch="all") or []
    except Exception:
        tpls = []
    cur = b.get("template_id")
    lines = ["📄 قالب این دسته", "━━━━━━━━━━━━━━", ""]
    btns = [[{"text": f"{'🔘' if not cur else '▫️'} پیش‌فرض",
              "callback_data": f"cbT_0_{bid}"}]]
    for t in tpls:
        mark = "🔘" if cur == t["id"] else "▫️"
        lines.append(f"{mark} {t.get('name') or '—'}")
        btns.append([{"text": f"{mark} {(t.get('name') or '')[:26]}",
                      "callback_data": f"cbT_{t['id']}_{bid}"}])
    if not tpls:
        lines.append("📭 قالبی ثبت نشده")
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cb_v_{bid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_tpl(cid, uid, tid, bid):
    if not _guard(cid, uid):
        return
    db_execute("UPDATE cert_batches SET template_id=? WHERE id=?",
               (int(tid) or None, int(bid)))
    return show_batch(cid, uid, bid)


# ══════════════════════════════════════════════════════════
# 👤 سمت کاربر — دریافت با لینک
# ══════════════════════════════════════════════════════════
def handle_claim(cid, uid, code, user=None):
    """
    🎓 کاربر لینک را باز کرده — کل جریان دریافت.

    🎯 «طرفم بیاد ربات استارت بزنه پروفش تکمیل کنه و
        گواهیش بگیره»
    """
    b = get_batch(code=code)
    ok, why = can_claim(b)
    if not ok:
        return send(cid, f"🌱 {why}")

    if user is None:
        try:
            from auth import get_user
            user = get_user(uid) or {}
        except Exception:
            user = {}

    # 1️⃣ پروفایل کامل است؟
    if b.get("require_profile"):
        need = []
        by = b.get("match_by") or "mobile"
        if by == "mobile" and not norm_mobile(user.get("mobile")):
            need.append("📱 شمارهٔ موبایل")
        if by == "national_id" and not valid_nid(user.get("national_id")):
            need.append("🆔 کد ملی")
        if not (user.get("first_name") or user.get("full_name")):
            need.append("👤 نام و نام خانوادگی")
        if need:
            from auth import set_state
            set_state(uid, "cb_claim_wait", {"code": code})
            return send(cid, (
                f"🎓 {b.get('title') or 'گواهینامه'}\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"برای دریافت گواهینامه، این موارد لازم است:\n\n"
                + "\n".join(f"   • {x}" for x in need) +
                "\n\n💡 از «👤 پروفایل من» تکمیل کنید و\n"
                "   دوباره روی لینک بزنید."), {"inline_keyboard": [
                    [{"text": "👤 تکمیل پروفایل",
                      "callback_data": "profile_view"}]]})

    # 2️⃣ در لیست هست؟
    row, why = find_row(b, user)
    if not row:
        return send(cid, (
            f"🌱 {why}\n\n"
            f"اگر فکر می‌کنید اشتباهی شده، با برگزارکننده\n"
            f"تماس بگیرید."))

    # 3️⃣ قبلاً گرفته؟
    if row.get("status") == "issued" and row.get("cert_id"):
        try:
            from certissue import send_cert_files
            send(cid, "✅ گواهینامهٔ شما قبلاً صادر شده — دوباره می‌فرستم")
            return send_cert_files(cid, row["cert_id"])
        except Exception:
            return send(cid, "✅ قبلاً دریافت کرده‌اید")

    # 4️⃣ صدور
    return _issue_for_row(cid, uid, b, row, user)


def _issue_for_row(cid, uid, batch, row, user):
    """🎓 صدور واقعی گواهینامه برای یک ردیف"""
    send(cid, "⏳ در حال ساخت گواهینامه…")
    try:
        import certgen
        mp = build_mapping(batch, row, user)
        import attendance as _att
        serial = (_att.gen_serial() if hasattr(_att, "gen_serial")
                  else f"B{batch['id']}-{row['id']}")
        mp.setdefault("serial", serial)
        mp.setdefault("verify_url", certgen.verify_url(serial))

        tpl = None
        if batch.get("template_id"):
            tpl = certgen.get_template(batch["template_id"])
        tpl = tpl or certgen.get_template()

        cert_id = db_execute(
            "INSERT INTO certificates (bale_user_id, event_id, serial, "
            "template_id, source, created_at) "
            "VALUES (?,?,?,?,'batch',datetime('now'))",
            (int(uid), batch.get("event_id"), serial,
             (tpl or {}).get("id")))

        # 🔍 فاز ۳۴ — شناسهٔ دولایه و تاریخ اعتبار
        try:
            import certverify as _cv
            info = _cv.stamp(cert_id, batch.get("event_id"))
            if info.get("full_code"):
                mp["serial"] = info["full_code"]
                mp["verify_code"] = info["person_code"]
                mp["doc_no"] = info["doc_no"]
                mp["verify_url"] = _cv.verify_link(info["full_code"])
                if info.get("expires_on"):
                    mp["expires_on"] = info["expires_on"]
                mp["issued_on"] = info.get("issued_on") or ""
                # 🔴 باگ رفع‌شده (فاز ۳۷) — همان باگ فاز ۳۵:
                #    وقتی رویداد «شمارهٔ نامه» ندارد،
                #    build_full_code فقط کد فردی را برمی‌گرداند
                #    و شمارهٔ سریال رسمی NORA-… گم می‌شد.
                if info.get("doc_no"):
                    serial = info["full_code"]
                # 💾 سریال نهایی باید در دیتابیس هم بنشیند،
                #    وگرنه رکورد با سریال قدیمی می‌ماند و
                #    استعلام کار نمی‌کند.
                db_execute("UPDATE certificates SET serial=? "
                           "WHERE id=?", (serial, cert_id))
        except Exception as _e:
            log(f"⚠️ شناسهٔ استعلام: {_e}")

        # 📷 فاز ۳۷ — عکس پرسنلی
        try:
            import certphoto as _cp
            _cp.attach(mp, uid, tpl)
        except Exception as _pe:
            log(f"⚠️ عکس پرسنلی: {_pe}")

        res = certgen.generate(mp, tpl)
        path = res.get("png") or res.get("pdf") or res.get("docx")
        if path:
            db_execute(
                "UPDATE certificates SET png_path=?, pdf_path=?, "
                "docx_path=?, file_path=? WHERE id=?",
                (res.get("png"), res.get("pdf"), res.get("docx"),
                 path, cert_id))
        mark_claimed(row["id"], uid, cert_id)
        # 🔴 باگ رفع‌شده (فاز ۳۷): شمارندهٔ گواهینامهٔ کاربر
        #    فقط در certissue بالا می‌رفت. کسی که از لینک
        #    اکسل گواهینامه می‌گرفت، در پروفایلش
        #    «🎓 گواهینامه‌ها: ۰» می‌دید.
        db_execute("UPDATE users SET total_certificates="
                   "COALESCE(total_certificates,0)+1 "
                   "WHERE bale_user_id=?", (int(uid),))

        send(cid, (
            f"🎉 گواهینامهٔ شما آماده شد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"👤 {row.get('full_name') or ''}\n"
            f"🔖 شمارهٔ ثبت: {serial}\n"))
        try:
            from certissue import send_cert_files
            send_cert_files(cid, cert_id)
        except Exception:
            if path:
                send_document(cid, path, "🎓 گواهینامهٔ شما")
        return True
    except Exception as e:
        log(f"❌ صدور دسته‌ای: {e}")
        return send(cid, (
            "🌱 ساخت گواهینامه به مشکل خورد.\n\n"
            "لطفاً چند دقیقهٔ دیگر دوباره امتحان کنید یا\n"
            "به برگزارکننده اطلاع دهید."))
