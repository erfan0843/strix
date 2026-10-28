# فاز ششم — پیاده‌سازی دفترکل امتیاز باشگاه (ربات → سرور → پنل)

- تاریخ: ۱۴۰۵/۰۷/۲۹ (2026-10-21)
- شاخه: `arena/840de336-strix` (مبنا: `48bd947` سند طراحی فاز پنجم)
- سند مرجع: `Final-Delivery/reports/PHASE5-POINTS-LEDGER-DESIGN-2026-10-21.fa.md` (با اصلاحیهٔ فاز ششم در همان سند)
- وضعیت: **کد آماده و آزموده‌شده در محیط آزمایشی؛ آمادهٔ استقرار نیست** تا پشتیبان معتبر و تأیید جداگانهٔ مالک گرفته شود. هیچ مهاجرت تولیدی، استقرار، ادغام (merge) یا شاخهٔ موازی انجام نشده.

---

## ۱. خلاصهٔ یک‌نگاه

| موضوع | وضعیت |
|---|---|
| یک مسیر مرکزی برای هر تغییر امتیاز (`points_ledger.post_points`) | پیاده‌سازی و آزموده (ربات) |
| تراکنش اتمیک: ردیف دفترکل + به‌روزرسانی موجودی + وضعیت عملیات مرتبط | پیاده‌سازی و آزموده (`db_transaction`, `BEGIN IMMEDIATE`) |
| ایدمپوتنسی بر پایهٔ رویداد تجاری (`UNIQUE(source, ref_key)`) | پیاده‌سازی و آزموده |
| ردیف‌های تغییرناپذیر؛ اصلاح فقط با ردیف برگشت (`UNIQUE(reverses_id)`) | پیاده‌سازی و آزموده (تریگرهای DB) |
| نگهبان DB در برابر نوشتن مستقیم `users.total_points` | پیاده‌سازی و آزموده + آزمون ایستا |
| ۱۱ مسیر فعال امتیاز روی دفترکل (۹ مسیر طرح + نظرسنجی رویداد + تولد/مناسبت که جدا شمرده شد) | پیاده‌سازی و آزموده |
| تعدیل دستی: جدا از ویرایش پروفایل، فقط سوپرادمین، دلتا + دلیل، دو مرحله، سقف از env (fail-closed) | پیاده‌سازی و آزموده |
| ابزار سلامت (فقط گزارش، بدون اصلاح خودکار) + ممیزی قدیمی | پیاده‌سازی و آزموده |
| اسکریپت افتتاحیه (dry-run پیش‌فرض، `--apply --yes`، پشتیبان، ایدمپوتنت) | پیاده‌سازی و آزموده روی دادهٔ ساختگی |
| آینهٔ سرور: مهاجرت `0030` + `POST /api/bot/club/points` + `GET /api/admin/club/points…` | پیاده‌سازی و آزموده (SQLite + PostgreSQL یک‌بارمصرف) |
| پنل فقط‌خواندنی برای مالک/سرپرست باشگاه (`cl_member`) | پیاده‌سازی، آزمون jsdom و مرورگر روی سرور آزمایشی |
| ارسال واقعی به بله | **آزموده‌نشده** (بدون دسترسی شبکه به بله؛ آزمون‌ها `bale_api.api` را جایگزین می‌کنند) |
| dry-run روی پشتیبان واقعی تولید | **انجام‌نشده** (در این محیط فقط نسخهٔ ساختگی موجود بود) |

قواعد کسب‌وکار (مبلغ، نرخ، سقف، شرط، پاداش) تغییر نکرده؛ پاداش کلیک تبلیغ و `refund_points` قدیمی همچنان غیرفعال‌اند؛ هیچ امتیازی سمت سرور داده نمی‌شود؛ سطح عضویت خارج از دامنه ماند؛ **پنل هیچ مسیر نوشتنی برای امتیاز ندارد.**

---

## ۲. کامیت‌ها (به ترتیب، همه روی `arena/840de336-strix`)

| # | کامیت | محتوا |
|---|---|---|
| ۱ | `7540825` | اصلاحیهٔ سند طراحی: افتتاحیه در آغاز L1 (پس از توقف ربات و پشتیبان معتبر)، L2 = تطبیق + فعال‌سازی، بازگشت = توقف کنترل‌شدهٔ نوشتن + نسخهٔ سازگار یا re-baseline صریح و ممیزی‌شده |
| ۲ | `42a330b` | `database.db_transaction` (قفل + `BEGIN IMMEDIATE`، بدون تداخل با `db_execute` خودکار، بدون BEGIN تودرتو) + `points_ledger.py` + آزمون‌ها |
| ۳ | `fdf8ae3` | همهٔ مسیرهای فعال امتیاز روی دفترکل + تعدیل دستی جدید + `test_points_paths` + آزمون ایستای «نبودِ نوشتن مستقیم» |
| ۴ | `6ce5c9d` | `doctor.py` (گزارش سلامت دفترکل)، `legacy_data_audit.py`، `migrate_points_opening_balance.py`، پیش‌شرط راه‌اندازی ربات |
| ۵ | `9e46c68` | سرور: مهاجرت `0030_club_points_entries`، `backend/club_points.py`، مسیرهای ربات/مدیر، `shared_api.submit_points_entry`، همگام‌سازی ربات→سرور |
| ۶ | `19b6d94` | پنل فقط‌خواندنی «امتیاز باشگاه» + `admin-club-points.test.mjs` + شواهد مرورگر و همگام‌سازی واقعی |
| ۷ | (این گزارش) | گزارش نهایی + `POINTS_MANUAL_ADJUST_MAX` در `deployment/bale-bot.env.example` |

---

## ۳. آنچه ساخته شد

### ۳.۱ ربات — هستهٔ دفترکل (`nora_bot/points_ledger.py`, `database.py`)
- جدول `points_ledger` با ستون‌های `bale_user_id, delta, balance_after, entry_type, source, ref_key, reason, actor_kind, actor_id, ref_table, ref_id, reverses_id, meta, created_at, shared_status, shared_id, shared_error, synced_at`.
- قیود: `UNIQUE(source, ref_key)`، `UNIQUE(reverses_id)`، FK به `users`، `CHECK` روی نوع/منبع/دلتا≠۰؛ تریگرهای `BEFORE UPDATE/DELETE` که ستون‌های مالی را تغییرناپذیر می‌کنند (فقط ستون‌های همگام‌سازی قابل به‌روزرسانی‌اند).
- نگهبان: تریگر روی `users` که هر `UPDATE total_points` خارج از `post_points` را رد می‌کند؛ `startup_check()` اجرای ربات را بدون نگهبان یا با کاربرانِ غیرصفرِ بدون افتتاحیه متوقف می‌کند (کد خروج ۱ با پیام ترتیب درست).
- `post_points()`: اعتبارسنجی → در یک تراکنش: بررسی تکرار کلید (تکرار = «created=False» و موجودی دست‌نخورده) → درج ردیف → به‌روزرسانی موجودی از همان ردیف → commit؛ اگر داخل تراکنش بیرونی فراخوانی شود، به همان تراکنش می‌پیوندد تا «وضعیت عملیات + دفترکل» با هم commit/rollback شوند.
- `reverse_entry()` تنها راه اصلاح: ردیف `reversal` با `reverses_id` یکتا؛ برگشت دوم رد می‌شود.
- `post_opening_balance()` با کلید `opening:{uid}`؛ `reconcile()`/`health_report()` فقط گزارش می‌دهند.
- همگام‌سازی: `build_sync_payload/sync_entry/sync_pending/sync_after_commit`؛ وضعیت‌های `pending/mirrored/unmapped/failed`؛ کلید بیرونی `{source_uuid}:{ledger_id}` (شناسهٔ منبع از `nora_legacy_migration_meta` و پایدار بین راه‌اندازی‌ها)؛ بدون `NORA_SHARED_API_URL` کاری نمی‌کند و جریان ربات را نمی‌شکند.

### ۳.۲ ربات — مسیرها (`fdf8ae3`)
کلیدها بر پایهٔ رویداد تجاری؛ وضعیت عملیات و ردیف دفترکل در یک تراکنش:

| مسیر | منبع | کلید | نکتهٔ رفتاری |
|---|---|---|---|
| نشان‌ها | `achievement` | `ach:{user}:{key}` | بدون تغییر مبلغ |
| قوانین امتیاز | `point_rule` | `rule:{user}:{key}[:n{progress}]` | — |
| تولد / مناسبت | `birthday` / `occasion` | `birthday:{user}:{jy}` / `occasion:{user}:{key}:{jy}` | سالی یک‌بار همان‌طور که بود |
| پایان رویداد | `event_finished` | `evfin:{event}:{user}` | اجرای دوباره امتیاز تکراری نمی‌دهد ولی نفرات جامانده را تکمیل می‌کند |
| حضور (دستی، کد/موقعیت، mark_all، خودکار) | `attendance_session` | `att:{session}:{user}` | پاک‌کردن و ثبت دوبارهٔ همان جلسه امتیاز دوباره نمی‌دهد |
| نظرسنجی رویداد | `survey` | `survey:{event}:{user}` | مسیر فعالی که در ممیزی فاز پنجم دیده نشده بود |
| جایزهٔ قرعه‌کشی | `lottery_prize` | `lot:{lottery}:{prize}:{user}` | — |
| خرید پاداش | `reward_redeem` | `redeem:{request}` | درخواست + کسر (+ تحویل خودکار) اتمیک؛ nonce تأیید در callback → دوبار زدن یک کسر |
| رد درخواست | `reward_reject_refund` | `redeem-refund:{request}` | فقط از `pending`؛ برگشت یک‌بار و با اشاره به ردیف کسر |
| پرداخت با امتیاز | `payment_spend` | `pay:{tx}` | ایجاد تراکنش + کسر + ردیف در یک تراکنش؛ meta ریالی از همان تراکنش مرجع (نرخ تاریخی حدس زده نمی‌شود) |
| تعدیل دستی | `admin_manual` | `manual:{uuid}` | حذف از فرم ویرایش پروفایل؛ جریان جدا، فقط سوپرادمین، دلتا + دلیل (≥۵ نویسه)، تأیید دومرحله‌ای، سقف `POINTS_MANUAL_ADJUST_MAX` (تنظیم‌نشده = غیرفعال)، قبل/بعد/عامل/دلیل در ردیف |

غیرفعال مانده (بدون تغییر): پاداش کلیک تبلیغ، `refund_points`، هر امتیاز سمت سرور، سطح عضویت.

### ۳.۳ ربات — ابزارها (`6ce5c9d`)
- `doctor.py` بخش «دفترکل امتیاز»: اختلاف شمارنده با دفترکل، موجودی منفی، ردیف‌های نامعتبر/تکراری، ردیف‌های بدون مرجع تجاری، وضعیت همگام‌سازی، کاربران بدون هویت بلهٔ قابل‌پیوند — فقط گزارش.
- `legacy_data_audit.py` (فقط‌خواندنی روی نسخهٔ پشتیبان) همان آمار را برای ممیزی پیش از cutover می‌دهد.
- `migrate_points_opening_balance.py --database … [--action opening|report|guard-off|guard-on|rebaseline] [--apply --yes] [--json]`: پیش‌فرض dry-run؛ `--apply` پشتیبان می‌گیرد و آن را با `PRAGMA integrity_check` و شمارش کاربر/موجودی و checksum تأیید می‌کند؛ اجرای دوباره ردیف جدید نمی‌سازد؛ منفی‌ها «پرچم» می‌خورند نه صفر؛ شناسه‌های نامعتبر جدا گزارش می‌شوند؛ تاریخچهٔ ساختگی تولید نمی‌شود.

### ۳.۴ سرور (`9e46c68`)
- مهاجرت `0030_club_points_entries` (پس از `0029_public_media`)؛ فقط ساختار آینه؛ `downgrade` کامل.
- `POST /api/bot/club/points` (فقط توکن سرویس ربات): مالک از `bale_user_id` در `platform_identities` تعیین می‌شود؛ بدون هویت تأییدشده → `404 owner_identity_not_found` و هیچ چیزی ذخیره یا ساخته نمی‌شود؛ بازپخش یکسان → `created:false`؛ کلید یکسان با محتوای متفاوت → `409 points_entry_conflict`؛ کلید با مالک دیگر → `409 points_entry_owner_mismatch`.
- `GET /api/admin/club/points`, `/members`, `/members/{account_id}` با مجوز `cl_member` (مالک و سرپرست باشگاه؛ مدیر عادی `403`)؛ پاسخ‌ها بدون تلفن/کد ملی/توکن/شناسهٔ خام ادمین؛ `write_routes:false` صریح؛ `history_complete` از پیوستگی زنجیرهٔ موجودی مشتق می‌شود.

### ۳.۵ پنل (`19b6d94`)
- کارت «امتیاز باشگاه» در هاب کاربران فقط برای دارندگان `cl_member`؛ نماها: اعضا (موجودی طبق آخرین ردیف رسیده، تعداد ردیف، «تاریخچهٔ کامل/ناقص»)، جزئیات عضو، همهٔ ردیف‌ها با فیلتر نوع و جست‌وجو (نام/شناسهٔ بله/کلید مرجع/دلیل)، صفحه‌بندی.
- حالت‌های صادق: خالی («هنوز ردیفی از ربات نرسیده»)، قطعی سرور («سرور در دسترس نیست…» + تلاش دوباره)، نشست منقضی؛ هیچ عدد ساختگی.
- `owner-api.js`: سه تابع خواندنی؛ پذیرش پارامترهای `entry_type/account_id/bale_user_id`. ضمناً نقص پیشین `safeQuery` که `kind/event_ref/slot` (فیلترهای گواهینامه) را سمت کلاینت رد می‌کرد، در همین تغییر رفع شد.
- پین نسخه‌ها: `admin.js?v=127`, `owner-api.js?v=113` (در همهٔ صفحات مصرف‌کننده).

---

## ۴. نتایج واقعی آزمون‌ها (اجرای نهایی روی `19b6d94`)

| مجموعه | نتیجه |
|---|---|
| ربات `pytest tests` (`bale-bot/nora_bot`) | **۲۰۴ passed** (۱ هشدار) — شامل `test_points_ledger` ۱۴، `test_points_paths` ۱۷، `test_points_write_paths_static` ۳، `test_points_opening_script` ۷، `test_points_sync_server` ۲ |
| سرور `pytest tests` (`nora-ui/backend`) | **۲۵۲ passed, 4 skipped** (skipهای PostgreSQL بدون URL) — شامل `test_club_points_api` ۳ |
| PostgreSQL یک‌بارمصرف (`pgserver`) `-k postgres` | **۵ passed** (upgrade/downgrade تا `0030`) — اجرا در کامیت ۵؛ کد سرور از آن پس تغییر نکرده |
| mypy (`backend/mypy.ini`) | **بدون خطا، ۵۸ فایل** |
| Node/jsdom `tools/run-unit-tests.cjs` | **۲۸/۲۸ passed** (`logs/node-suites.txt`) |
| `admin.test.mjs` | **۸۱۷ بررسی، ۰ خطا** (بازاجرا پس از آخرین تغییر قالب تاریخ) |
| `admin-club-points.test.mjs` (جدید) | سبز: مالک (اعضا، جزئیات، ردیف‌ها، فیلتر، جست‌وجو)، خالی، قطعی + نشست منقضی، سرپرست، مدیر عادی بدون کارت/با `403` |

پوشش الزامات مرحلهٔ ۷ (همه در آزمون‌های بالا): اجرای دوبار = یک اثر؛ کلید یکسان هم‌زمان (رشته‌ها) = یک ردیف؛ شکست بین درج و به‌روزرسانی موجودی = rollback کامل؛ هر مسیر دقیقاً یک ردیف با همان مبلغ قبلی؛ پایان دوبارهٔ رویداد / پاک‌کردن و ثبت دوبارهٔ حضور / رد دوباره / تکرار پرداخت = بدون دو‌بار شمردن؛ تعدیل بی‌مجوز/بی‌دلیل/بالای سقف/بدون سقف و برگشت دوم رد می‌شوند؛ dry-run چیزی تغییر نمی‌دهد و apply ایدمپوتنت است؛ ابزار سلامت فقط گزارش می‌دهد؛ مهاجرت سرور رفت‌وبرگشت روی PG؛ احراز هویت/هویت/مجوز/نشت API ربات و مدیر؛ پنل خالی/تاریخچه/همگام‌سازی/ناقص.

### ۴.۱ شواهد مسیر واقعی روی سرور آزمایشی (`reports/evidence-points-ledger-phase6-2026-10-21/`)
- سرور آزمایشی محلی (SQLite `/tmp/nora-preview`, پس از `alembic upgrade head` → `0030`) + پایگاه آزمایشی ربات با ۳ کاربر ساختگی (دو کاربر با هویت بلهٔ پیونددار در سرور، یکی بدون هویت).
- `sync/bot-to-server-sync.json`: ۹ ردیف دفترکل از `post_points/reverse_entry`؛ تکرار کلید نشان → موجودی بدون تغییر؛ همگام‌سازی HTTP واقعی: **۸ mirrored، ۱ unmapped، ۰ failed**؛ اجرای دوبارهٔ `sync_pending(include_unmapped=True)` → همان ۱ unmapped، هیچ ردیف تازه؛ بازپخش دستی ردیف ۱ → `created:false`؛ `reconcile` → `ok:true`, `mismatched:0`, `chain_breaks:0` (`missing_business_ref:7` چون دادهٔ ساختگی جدول رویداد/درخواست ندارد — گزارش صادقانهٔ ابزار).
- `sync/server-mirror-rows.json`: ۸ ردیف آینه روی سرور (بدون شناسهٔ حساب/بله).
- `ui/`: اسکرین‌شات‌های ۱۲۸۰×۸۰۰ و ۳۹۰×۸۴۴ — کارت در هاب، فهرست اعضا، جزئیات عضو، همهٔ ردیف‌ها، فیلتر «برگشت ردیف»، جست‌وجو، و هاب مدیر عادی بدون کارت؛ `browser-log.txt`: بررسی نشت «clean»، بدون خطای صفحه، فهرست دکمه‌های پنل فقط بازخوانی/فیلتر/جست‌وجو، درخواست مستقیم مدیر عادی → `403 permission_denied`.
- `scripts/`: اسکریپت‌های تکرارپذیر (`seed-and-sync.py`, `browser-panel.mjs`).

### ۴.۲ dry-run اسکریپت افتتاحیه
- روی نسخهٔ ساختگی (`legacy.sqlite` ساخته‌شده در فاز ۴/۶، checksum قبل و بعد یکسان `f97490f9…`): `mode: dry-run`, `users_total 4, users_nonzero 3, sum_points 145, negative 1 (پرچم‌خورده), invalid_ids 0, already_opened 3, planned_opening_rows 0`, «هیچ تغییری اعمال نشد».
- **روی پشتیبان واقعی تولید اجرا نشده** (در این محیط موجود نیست). پیش از cutover باید روی نسخهٔ پشتیبان واقعی اجرا و خروجی ثبت شود.

---

## ۵. محدودیت‌ها و موارد آزموده‌نشده
1. **بله:** هیچ پیام واقعی ارسال نشده؛ همهٔ آزمون‌های ربات `bale_api.api` را جایگزین می‌کنند. رفتار callbackها (nonce تأیید خرید، تعدیل دستی) فقط با شبیه‌ساز آزموده شد.
2. **دادهٔ واقعی:** dry-run/ممیزی روی پشتیبان واقعی انجام نشده؛ تعداد unmapped واقعی (کاربران بدون هویت بلهٔ پیونددار در سرور) ناشناخته است و فقط پس از ممیزی روی پشتیبان مشخص می‌شود.
3. **پنل:** آزمون مرورگر روی سرور آزمایشی محلی با حساب‌های آزمایشی `qa-owner`/`qa-manager` انجام شد، نه روی محیط تولید. نقش «سرپرست باشگاه» فقط در jsdom آزموده شد (حساب آزمایشی سرپرست جدا ساخته نشد).
4. **PostgreSQL:** مهاجرت ۰۰۳۰ روی نمونهٔ یک‌بارمصرف آزموده شد؛ روی پایگاه تولید اجرا نشده.
5. `missing_business_ref` در ابزار سلامت برای ردیف‌هایی که جدول مرجعشان در پایگاه نیست (مثلاً دادهٔ آزمایشی) مثبت کاذب می‌دهد؛ ابزار فقط گزارش است و تصمیم با انسان.

---

## ۶. دستور راه‌اندازی (پیشنهادی؛ فقط پس از تأیید جداگانه)
1. پشتیبان معتبر از SQLite ربات و PostgreSQL سرور؛ تمرین کامل روی نسخهٔ پشتیبان (ممیزی `legacy_data_audit.py`، dry-run افتتاحیه، `reconcile`).
2. توقف ربات (نسخهٔ فعلی). ثبت checksum و شمارش کاربر/موجودی.
3. `python migrate_points_opening_balance.py --database <sqlite> --json` (dry-run) → بررسی گزارش → `--apply --yes` → ثبت خروجی (مجموع قبل/بعد، تعداد افتتاحیه، منفی‌ها، شناسه‌های نامعتبر).
4. استقرار وب + `alembic upgrade head` (۰۰۳۰) → سلامت `200`.
5. در `bale-bot.env`: در صورت تصمیم مالک `POINTS_MANUAL_ADJUST_MAX` (خالی = تعدیل دستی غیرفعال). اجرای نسخهٔ جدید ربات؛ `startup_check` بدون افتتاحیه یا بدون نگهبان اجازهٔ اجرا نمی‌دهد.
6. پس از راه‌اندازی: `doctor.py` → بخش دفترکل؛ `sync_pending` ردیف‌های مانده را می‌فرستد؛ unmappedها پس از پیوند هویت با `include_unmapped` دوباره ارسال می‌شوند.

## ۷. بازگشت (rollback)
- **برگرداندن کد به‌تنهایی کافی نیست.** گزینه‌ها: (الف) توقف کنترل‌شدهٔ ربات و اجرای نسخهٔ سازگار با دفترکل؛ (ب) اگر باید به نسخهٔ پیش از دفترکل برگشت: `--action guard-off --reason … --apply --yes` (ممیزی‌شده و ثبت‌شده)، سپس نسخهٔ قدیمی؛ بازگشت دوباره به دفترکل فقط با `--action rebaseline` صریح (ردیف `rebaseline` با دلیل) و `guard-on`.
- سرور: `alembic downgrade 0029_public_media` فقط جدول آینه را حذف می‌کند (منبع حقیقت در ربات است).

## ۸. فایل‌های تغییر‌یافته/افزوده (کل فاز)
- ربات: `database.py`, `points_ledger.py`(جدید), `club.py`, `main.py`, `attendance.py`, `attendance_auto.py`, `survey.py`, `events.py`, `lottery.py`, `occasions.py`, `payments.py`, `config.py`, `admin.py`, `activity_log.py`, `guard.py`, `doctor.py`, `legacy_data_audit.py`, `migrate_points_opening_balance.py`(جدید), `shared_api.py`, آزمون‌ها `tests/_points_fixture.py`, `test_points_*.py`(جدید) و به‌روزرسانی `test_phase11/12b/13/14/17b/17d/18/40`.
- سرور: `backend/app.py`, `backend/club_points.py`(جدید), `backend/models.py`, `migrations/versions/0030_club_points_entries.py`(جدید), `tests/test_club_points_api.py`(جدید), `tests/test_migrations.py`, `tests/test_local_development.py`, `README.fa.md`, `SHARED_DATA.fa.md`.
- پنل: `admin.js`, `owner-api.js`, `admin.html`, `account.html`, `builder.html`, `create.html`, `form.html`, `home.html`, `admin.test.mjs`, `admin-club-points.test.mjs`(جدید).
- اسناد/استقرار: `PHASE5-POINTS-LEDGER-DESIGN…`(اصلاحیه), این گزارش, `deployment/bale-bot.env.example`, شواهد `reports/evidence-points-ledger-phase6-2026-10-21/`.
