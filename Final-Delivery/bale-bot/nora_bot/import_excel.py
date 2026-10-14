"""
ورود کاربران از اکسل - نسخه 4.1 (فیکس شده)

فیکس‌های مهم:
- 🐛 «نام و نام خانوادگی از اکسل خوانده نمی‌شد»:
  ریشه: map_headers کلید را lower() می‌کرد ولی COLUMN_MAP کلیدهای فارسی
  با فاصله/نیم‌فاصله داشت و مقایسه شکست می‌خورد. حالا نرمال‌سازی کامل
  (نیم‌فاصله، ی/ک عربی، فاصله اضافی، حذف "‌") انجام می‌شود.
- مقادیر عددی اکسل (مثل موبایل) دیگر با ".0" ذخیره نمی‌شوند
- ردیف‌های تکراری داخل خود فایل هم تشخیص داده می‌شوند
- گزینه «به‌روزرسانی رکورد موجود» اضافه شد (قبلاً فقط skip می‌کرد)
- ستون‌های ناشناخته دیگر باعث خطای SQL نمی‌شوند (whitelist)
- تاریخ‌های datetime اکسل درست تبدیل می‌شوند
"""
from privacy import user_error_message
import json
import time
from datetime import datetime, date
from pathlib import Path

from config import IMPORT_DIR, MAX_IMPORT_MB
from database import db_execute, log
from auth import (
    get_user, set_state, get_state_data, clear_state,
    normalize_mobile, split_full_name, normalize_digits, is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, get_file_info, download_file, kb_cancel, BTN_BACK)

STATE_WAIT_FILE = "waiting_import"
STATE_CONFIRM = "confirm_import"

# ستون‌های مجازِ دیتابیس (whitelist - جلوگیری از SQL injection و ستون اشتباه)
ALLOWED_DB_COLUMNS = {
    "first_name", "last_name", "mobile", "national_id", "birth_date",
    "gender", "age", "email", "phone", "province", "city", "address",
    "postal_code", "education_level", "field_of_study", "university",
    "job_title", "company_name", "father_name", "mother_name", "bio",
}


def _norm_key(s):
    """نرمال‌سازی نام ستون برای تطبیق مطمئن"""
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = t.replace("\u200c", " ")   # نیم‌فاصله -> فاصله
    t = t.replace("\u064a", "\u06cc")  # ي عربی -> ی
    t = t.replace("\u0643", "\u06a9")  # ك عربی -> ک
    t = t.replace("ـ", "")
    for ch in (":", "*", "؟", "?", ".", "،", ","):
        t = t.replace(ch, " ")
    return " ".join(t.split())


_RAW_MAP = {
    # نام کامل
    "نام و نام خانوادگی": "full_name",
    "نام و نام خانوادکی": "full_name",
    "نام ونام خانوادگی": "full_name",
    "نام و فامیل": "full_name",
    "نام کامل": "full_name",
    "نام و نام خانوادگی کامل": "full_name",
    "full name": "full_name",
    "fullname": "full_name",
    "full_name": "full_name",
    "نام‌ونام‌خانوادگی": "full_name",
    # نام
    "نام": "first_name",
    "اسم": "first_name",
    "first name": "first_name",
    "firstname": "first_name",
    "first_name": "first_name",
    "name": "first_name",
    # فامیل
    "نام خانوادگی": "last_name",
    "فامیل": "last_name",
    "فامیلی": "last_name",
    "last name": "last_name",
    "lastname": "last_name",
    "last_name": "last_name",
    "family": "last_name",
    "surname": "last_name",
    # موبایل
    "موبایل": "mobile",
    "شماره": "mobile",
    "شماره موبایل": "mobile",
    "شماره تماس": "mobile",
    "تلفن همراه": "mobile",
    "همراه": "mobile",
    "mobile": "mobile",
    "phone": "mobile",
    "tel": "mobile",
    "phone number": "mobile",
    "cell": "mobile",
    # کد ملی
    "کد ملی": "national_id",
    "کدملی": "national_id",
    "شماره ملی": "national_id",
    "national id": "national_id",
    "national_id": "national_id",
    "nationalcode": "national_id",
    "کد ملی /شناسه": "national_id",
    # ایمیل
    "ایمیل": "email",
    "پست الکترونیک": "email",
    "email": "email",
    "mail": "email",
    # تاریخ تولد
    "تاریخ تولد": "birth_date",
    "تولد": "birth_date",
    "birth date": "birth_date",
    "birth_date": "birth_date",
    "birthday": "birth_date",
    # سن
    "سن": "age",
    "age": "age",
    # جنسیت
    "جنسیت": "gender",
    "جنس": "gender",
    "gender": "gender",
    "sex": "gender",
    # مکان
    "شهر": "city",
    "city": "city",
    "استان": "province",
    "province": "province",
    "state": "province",
    "شهر و استان": "city_province",
    "استان و شهر": "city_province",
    "شهرستان": "city",
    "آدرس": "address",
    "نشانی": "address",
    "address": "address",
    "کد پستی": "postal_code",
    "کدپستی": "postal_code",
    "postal code": "postal_code",
    "postal_code": "postal_code",
    "zip": "postal_code",
    # تحصیلات
    "مقطع": "education_level",
    "مقطع تحصیلی": "education_level",
    "تحصیلات": "education_level",
    "education": "education_level",
    "رشته": "field_of_study",
    "رشته تحصیلی": "field_of_study",
    "field": "field_of_study",
    "major": "field_of_study",
    "دانشگاه": "university",
    "محل تحصیل": "university",
    "university": "university",
    "مدرسه": "university",
    # شغل
    "شغل": "job_title",
    "عنوان شغلی": "job_title",
    "job": "job_title",
    "job title": "job_title",
    "occupation": "job_title",
    "شرکت": "company_name",
    "محل کار": "company_name",
    "سازمان": "company_name",
    "company": "company_name",
    # خانواده
    "نام پدر": "father_name",
    "نام‌پدر": "father_name",
    "father name": "father_name",
    "father_name": "father_name",
    "نام مادر": "mother_name",
    "mother name": "mother_name",
    "mother_name": "mother_name",
    # بیو
    "توضیحات": "bio",
    "بیو": "bio",
    "معرفی": "bio",
    "bio": "bio",
    "description": "bio",
}

COLUMN_MAP = {_norm_key(k): v for k, v in _RAW_MAP.items()}


def _cell_to_text(value):
    """تبدیل امن سلول اکسل به متن"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "بله" if value else "خیر"
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y/%m/%d")
    if isinstance(value, float):
        # فیکس: 9123456789.0 -> 9123456789
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value).strip()


# ==================== COMMAND ====================
def handle_import_command(message):
    cid = message["chat"]["id"]
    uid = message["from"]["id"]

    if not _is_admin(uid):
        return send(cid, "❌ این دستور فقط برای ادمین است")

    set_state(uid, STATE_WAIT_FILE, {}, merge=False)
    send(cid, (
        f"📥 ورود کاربران از اکسل\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📎 فایل را ارسال کنید\n"
        f"📋 فرمت مجاز: .xlsx / .xls / .csv\n"
        f"📏 حداکثر حجم: {MAX_IMPORT_MB} مگابایت\n\n"
        f"💡 ستون‌هایی که شناسایی می‌شوند:\n"
        f"• نام و نام خانوادگی (یا نام + نام خانوادگی جدا)\n"
        f"• موبایل ⭐ (اجباری)\n"
        f"• کد ملی، ایمیل، تاریخ تولد، جنسیت\n"
        f"• استان، شهر، آدرس، کد پستی\n"
        f"• مقطع، رشته، دانشگاه، شغل، محل کار\n"
        f"• نام پدر، نام مادر\n\n"
        f"⚠️ ردیف اول فایل باید عنوان ستون‌ها باشد."
    ), kb_cancel())


def handle_import_file(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]

    doc = message.get("document")
    if not doc:
        return send(cid, "❌ لطفاً فایل اکسل ارسال کنید")

    fn = doc.get("file_name") or "unknown.xlsx"
    fs = doc.get("file_size") or 0

    if not any(fn.lower().endswith(e) for e in (".xlsx", ".xls", ".csv")):
        return send(cid, "❌ فقط فایل‌های .xlsx / .xls / .csv پذیرفته می‌شوند")

    if fs > MAX_IMPORT_MB * 1024 * 1024:
        return send(cid, f"❌ حجم فایل بیش از {MAX_IMPORT_MB} مگابایت است")

    send(cid, "⏳ در حال دانلود فایل...")

    fi = get_file_info(doc.get("file_id"))
    if not fi.get("ok"):
        clear_state(uid)
        return send(cid, "❌ خطا در دریافت فایل از بله")

    fpath = (fi.get("result") or {}).get("file_path")
    if not fpath:
        clear_state(uid)
        return send(cid, "❌ مسیر فایل نامعتبر")

    content = download_file(fpath)
    if not content:
        clear_state(uid)
        return send(cid, "❌ خطا در دانلود فایل")

    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in fn if c.isalnum() or c in "._- ")[:60] or "import.xlsx"
    saved = Path(IMPORT_DIR) / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    try:
        saved.write_bytes(content)
    except Exception as e:
        clear_state(uid)
        return send(cid, f"❌ خطا در ذخیره فایل: {user_error_message(e)}")

    log(f"📥 فایل ذخیره شد: {saved.name} ({fs/1024:.0f}KB)")

    try:
        process_excel(cid, uid, str(saved), fn)
    except Exception as e:
        log(f"❌ خطای پردازش اکسل: {e}")
        clear_state(uid)
        send(cid, f"❌ خطا در خواندن فایل:\n{user_error_message(e)}")


# ==================== READ ====================
def read_file(file_path):
    """خواندن اکسل یا CSV -> (headers, rows)"""
    p = str(file_path)

    if p.lower().endswith(".csv"):
        import csv
        for enc in ("utf-8-sig", "utf-8", "cp1256", "windows-1256"):
            try:
                with open(p, "r", encoding=enc, newline="") as f:
                    reader = csv.DictReader(f)
                    headers = [h for h in (reader.fieldnames or [])]
                    rows = [dict(r) for r in reader]
                return headers, rows
            except UnicodeDecodeError:
                continue
        raise Exception("انکودینگ فایل CSV پشتیبانی نمی‌شود")

    try:
        import openpyxl
    except ImportError:
        raise Exception("openpyxl نصب نیست.\nدستور نصب:\npy -m pip install openpyxl")

    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        wb.close()
        return [], []

    headers = [(_cell_to_text(c) or f"col{i+1}") for i, c in enumerate(header_row)]

    rows = []
    for row in rows_iter:
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue
        d = {}
        for i, h in enumerate(headers):
            d[h] = row[i] if i < len(row) else None
        rows.append(d)

    wb.close()
    return headers, rows


def map_headers(headers):
    """
    ✅ فیکس باگ «نام خوانده نمی‌شود»:
    نرمال‌سازی کامل نام ستون قبل از تطبیق.
    """
    mapped, unmapped = {}, []
    used = set()
    for h in headers:
        if not h:
            continue
        key = _norm_key(h)
        target = COLUMN_MAP.get(key)
        if not target:
            # تطبیق تقریبی: اگر عنوان شامل کلیدواژه باشد
            for cand, val in COLUMN_MAP.items():
                if len(cand) >= 4 and (cand in key or key in cand):
                    target = val
                    break
        if target and target not in used:
            mapped[h] = target
            used.add(target)
        elif target and target in used:
            unmapped.append(f"{h} (تکراری)")
        else:
            unmapped.append(h)
    return mapped, unmapped


# ==================== PREVIEW ====================
def process_excel(cid, admin_id, file_path, original_name):
    headers, rows = read_file(file_path)

    if not rows:
        clear_state(admin_id)
        return send(cid, "❌ فایل خالی است یا ردیف داده‌ای ندارد")

    mapped, unmapped = map_headers(headers)

    has_name = any(v in ("full_name", "first_name") for v in mapped.values())
    has_mobile = "mobile" in mapped.values()

    log(f"📊 اکسل: {len(rows)} ردیف، {len(mapped)} ستون شناسایی شد")

    lines = [
        "📊 پیش‌نمایش فایل",
        "━━━━━━━━━━━━━━",
        "",
        f"📁 {original_name}",
        f"📄 تعداد ردیف: {len(rows)}",
        f"📋 تعداد ستون: {len(headers)}",
        "",
        f"✅ ستون‌های شناسایی شده ({len(mapped)}):",
    ]
    for orig, target in list(mapped.items())[:15]:
        lines.append(f"• {orig} ← {target}")

    if unmapped:
        lines += ["", f"⚠️ ستون‌های نادیده گرفته شده ({len(unmapped)}):"]
        for u in unmapped[:6]:
            lines.append(f"• {u}")
        if len(unmapped) > 6:
            lines.append(f"• ... و {len(unmapped)-6} مورد دیگر")

    # نمونه ۲ ردیف اول
    lines += ["", "🔎 نمونه ردیف اول:"]
    sample = rows[0]
    shown = 0
    for orig, target in mapped.items():
        val = _cell_to_text(sample.get(orig))
        if val:
            lines.append(f"• {target}: {val}")
            shown += 1
        if shown >= 6:
            break

    if not has_mobile:
        lines += ["", "⛔ ستون «موبایل» پیدا نشد!",
                  "بدون موبایل امکان ورود اطلاعات نیست.",
                  "💡 نام ستون را به «موبایل» تغییر دهید."]
        clear_state(admin_id)
        return send(cid, "\n".join(lines))

    if not has_name:
        lines += ["", "⚠️ ستون نام پیدا نشد — کاربران بدون نام ثبت می‌شوند."]

    lines += ["", "🎯 نحوه برخورد با شماره‌های تکراری را انتخاب کنید:"]

    set_state(admin_id, STATE_CONFIRM, {
        "file_path": file_path,
        "mapped_headers": mapped,
        "total_rows": len(rows),
        "file_name": original_name,
    }, merge=False)

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "➕ فقط ثبت جدیدها", "callback_data": "import_start"}],
        [{"text": "🔄 ثبت جدید + به‌روزرسانی قدیمی‌ها", "callback_data": "import_update"}],
        [{"text": "❌ انصراف", "callback_data": "import_cancel"}],
    ]})


# ==================== IMPORT ====================
def do_import(file_path, mapped_headers, admin_id, file_name, update_existing=False):
    stats = {"total": 0, "success": 0, "duplicate": 0,
             "updated": 0, "error": 0, "errors": []}

    try:
        headers, rows = read_file(file_path)
    except Exception as e:
        stats["errors"].append(f"خطای خواندن فایل: {user_error_message(e)}")
        return stats

    stats["total"] = len(rows)
    log(f"🔄 شروع Import: {stats['total']} ردیف (به‌روزرسانی={update_existing})")

    seen_mobiles = set()

    for idx, row in enumerate(rows, start=2):
        try:
            data = {}
            for orig_col, db_col in mapped_headers.items():
                val = _cell_to_text(row.get(orig_col))
                if not val:
                    continue

                if db_col == "mobile":
                    val = normalize_mobile(val)
                    if not val:
                        continue
                elif db_col == "national_id":
                    val = normalize_digits(val).replace("-", "").replace(" ", "")
                elif db_col == "age":
                    v = normalize_digits(val)
                    val = v if v.isdigit() else ""
                    if not val:
                        continue
                elif db_col == "gender":
                    low = val.strip()
                    if low in ("مرد", "آقا", "پسر", "male", "m", "1"):
                        val = "مرد"
                    elif low in ("زن", "خانم", "دختر", "female", "f", "2"):
                        val = "زن"
                elif db_col in ("birth_date", "postal_code"):
                    val = normalize_digits(val)

                data[db_col] = val

            # نام کامل -> نام + فامیل
            if "full_name" in data:
                full = data.pop("full_name")
                first, last = split_full_name(full)
                if first and not data.get("first_name"):
                    data["first_name"] = first
                if last and not data.get("last_name"):
                    data["last_name"] = last

            # شهر و استان ترکیبی
            if "city_province" in data:
                cp = data.pop("city_province").strip()
                sep = next((s for s in ("_", "-", "/", "،", ",") if s in cp), None)
                if sep:
                    parts = [p.strip() for p in cp.split(sep) if p.strip()]
                    if len(parts) >= 2:
                        data.setdefault("province", parts[0])
                        data.setdefault("city", parts[1])
                    elif parts:
                        data.setdefault("city", parts[0])
                elif cp:
                    data.setdefault("city", cp)

            mobile = data.get("mobile")
            if not mobile:
                stats["error"] += 1
                if len(stats["errors"]) < 30:
                    stats["errors"].append(f"ردیف {idx}: موبایل معتبر ندارد")
                continue

            # تکراری داخل خود فایل
            if mobile in seen_mobiles:
                stats["duplicate"] += 1
                continue
            seen_mobiles.add(mobile)

            # فیلتر ستون‌های مجاز (whitelist)
            data = {k: v for k, v in data.items()
                    if k in ALLOWED_DB_COLUMNS and str(v).strip()}
            if not data.get("mobile"):
                data["mobile"] = mobile

            existing = db_execute(
                "SELECT id FROM users WHERE mobile=?", (mobile,), fetch="one"
            )

            if existing:
                if not update_existing:
                    stats["duplicate"] += 1
                    continue
                upd = {k: v for k, v in data.items() if k != "mobile"}
                if not upd:
                    stats["duplicate"] += 1
                    continue
                # فقط فیلدهای خالی را پر کن (اطلاعات تأییدشده را خراب نکن)
                sets = ", ".join(f"{k}=COALESCE(NULLIF({k},''), ?)" for k in upd)
                db_execute(
                    f"UPDATE users SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    list(upd.values()) + [existing["id"]],
                )
                stats["updated"] += 1
                continue

            data.update({
                "imported": 1,
                "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "imported_from": file_name[:100],
                "registration_source": "imported",
                "auth_method": "imported",
                "referral_code": f"IMP{int(time.time()*1000)}{idx}",
            })

            cols = list(data.keys())
            ph = ", ".join("?" * len(cols))
            r = db_execute(
                f"INSERT INTO users ({', '.join(cols)}) VALUES ({ph})",
                list(data.values()),
            )
            if r is None:
                stats["error"] += 1
                if len(stats["errors"]) < 30:
                    stats["errors"].append(f"ردیف {idx}: خطای درج در دیتابیس")
            else:
                stats["success"] += 1
                if stats["success"] % 50 == 0:
                    log(f"  ✅ {stats['success']}/{stats['total']}")

        except Exception as e:
            stats["error"] += 1
            if len(stats["errors"]) < 30:
                stats["errors"].append(f"ردیف {idx}: {user_error_message(e)}")

    db_execute("""
        INSERT INTO import_history
        (admin_id, file_name, total_rows, success_count,
         duplicate_count, updated_count, error_count, details)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        admin_id, file_name, stats["total"], stats["success"],
        stats["duplicate"], stats["updated"], stats["error"],
        json.dumps(stats["errors"][:20], ensure_ascii=False),
    ))

    log(f"✅ Import تمام شد: {stats['success']} جدید، {stats['updated']} آپدیت، "
        f"{stats['duplicate']} تکراری، {stats['error']} خطا")
    return stats


def run_import(cid, uid, update_existing=False):
    """اجرای Import از روی state"""
    data = get_state_data(uid)
    if not data.get("file_path"):
        clear_state(uid)
        return send(cid, "⏰ زمان منقضی شد. دوباره /import را بزنید")

    fp = data["file_path"]
    if not Path(fp).exists():
        clear_state(uid)
        return send(cid, "❌ فایل پیدا نشد. دوباره ارسال کنید")

    send(cid, "⏳ در حال ورود اطلاعات... (ممکن است چند لحظه طول بکشد)")

    try:
        res = do_import(
            fp, data.get("mapped_headers") or {}, uid,
            data.get("file_name") or "import.xlsx",
            update_existing=update_existing,
        )
    except Exception as e:
        clear_state(uid)
        return send(cid, f"❌ خطای غیرمنتظره: {user_error_message(e)}")

    text = (
        f"✅ ورود اطلاعات تمام شد\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📊 نتیجه:\n"
        f"├── کل ردیف‌ها: {res['total']}\n"
        f"├── ✅ ثبت جدید: {res['success']}\n"
        f"├── 🔄 به‌روزرسانی: {res['updated']}\n"
        f"├── ⚠️ تکراری (رد شد): {res['duplicate']}\n"
        f"└── ❌ خطا: {res['error']}"
    )
    if res["errors"]:
        text += "\n\n📝 نمونه خطاها:\n"
        for err in res["errors"][:8]:
            text += f"• {err}\n"

    clear_state(uid)
    send_or_edit(cid, text, {"inline_keyboard": [
        [{"text": "👥 مشاهده کاربران", "callback_data": "admin_users"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}],
    ]})
