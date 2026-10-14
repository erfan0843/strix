"""تست محافظ‌های اجرا — فاز ۷"""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = tempfile.mkdtemp(prefix="norag_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l"})

import guard
PASS, FAIL = [], []
def check(n, c, d=""):
    if c: PASS.append(n); print(f"  ✅ {n}")
    else: FAIL.append((n, d)); print(f"  ❌ {n}  {d}")

print("\n" + "=" * 60)
print("🧪 تست محافظ‌های اجرا")
print("=" * 60)

print("\n[۱] فایل‌های پروژه")
check("همه فایل‌ها موجودند", not guard.check_files(), str(guard.check_files()))

print("\n[۲] تشخیص نصب کد جدید")
feats = guard.check_new_features()
for k, v in feats.items():
    check(f"{k}", v)
check("همه قابلیت‌ها نصب", all(feats.values()))

print("\n[۳] امضای کد")
fp, nf, sz = guard.code_fingerprint()
check("امضا ۸ رقمی", len(fp) == 8, fp)
check("حداقل ۱۱ فایل", nf >= 11, str(nf))

print("\n[۴] 🔴 قفل تک‌نمونه — جلوگیری از اجرای همزمان")
guard.release_lock()
ok1, _ = guard.acquire_lock(lambda *a: None)
check("قفل گرفته شد", ok1)
check("فایل قفل ساخته شد", guard.LOCK_FILE.exists())

guard.LOCK_FILE.write_text(f"{os.getpid()}|now", encoding="utf-8")
ok2, m2 = guard.acquire_lock(lambda *a: None)
check("🐛 نمونه دوم مسدود شد", not ok2, "دو ربات همزمان!")
check("پیام راهنمای بستن دارد", "taskkill" in m2 or "CMD" in m2)
check("شناسه فرآیند را نشان می‌دهد", str(os.getpid()) in m2)

guard.LOCK_FILE.write_text("999999|old", encoding="utf-8")
ok3, _ = guard.acquire_lock(lambda *a: None)
check("قفل مرده خودکار پاک می‌شود", ok3)
guard.release_lock()
check("آزادسازی قفل", not guard.LOCK_FILE.exists())

print("\n[۵] پاکسازی کش")
d = ROOT / "__pycache__"
d.mkdir(exist_ok=True)
(d / "old.pyc").write_bytes(b"stale")
n = guard.clear_pycache(lambda *a: None)
check("کش پاک شد", n >= 1 and not d.exists(), f"n={n}")

print("\n[۶] تشخیص PID")
check("PID خودم زنده است", guard._pid_alive(os.getpid()))
check("PID جعلی مرده است", not guard._pid_alive(999999))
check("PID نامعتبر", not guard._pid_alive("abc"))
check("PID صفر", not guard._pid_alive(0))

print("\n[۷] حذف خودکار وبهوک")
import bale_api
_calls = []
def _api(m, p=None, **k):
    _calls.append(m)
    if m == "getWebhookInfo":
        return {"ok": True, "result": {"url": "https://old.example.com/hook"}}
    if m == "deleteWebhook":
        return {"ok": True, "result": True}
    return {"ok": True}
bale_api.api = _api
bale_api.get_webhook_info = lambda: _api("getWebhookInfo")
bale_api.delete_webhook = lambda: _api("deleteWebhook")
okw, msgw = guard.ensure_polling_mode(lambda *a: None)
check("🐛 وبهوک فعال تشخیص داده شد", "deleteWebhook" in _calls, str(_calls))
check("وبهوک حذف شد", okw, msgw)

_calls.clear()
bale_api.get_webhook_info = lambda: {"ok": True, "result": {"url": ""}}
okw2, msgw2 = guard.ensure_polling_mode(lambda *a: None)
check("وبهوک خالی → کاری نمی‌کند", okw2 and "deleteWebhook" not in _calls)

print("\n" + "=" * 60)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 60)
if FAIL:
    for n, d in FAIL: print(f"  ❌ {n}  {d}")
    sys.exit(1)
print("\n🎉 همه محافظ‌ها کار می‌کنند!")
sys.exit(0)
