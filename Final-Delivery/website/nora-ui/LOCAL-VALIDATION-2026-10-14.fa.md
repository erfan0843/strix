# نتیجهٔ نصب، اجرا و تست محلی — ۱۴ اکتبر ۲۰۲۶

راهنمای قابل کپی: [راهنمای نصب، اجرا و تست محلی](../../../LOCAL-DEVELOPMENT.fa.md).

**این گزارش نتیجهٔ اجرای تازه در محیط Linux است، نه تکرار PASSهای گزارش ۱۱ اکتبر.** هیچ deploy، cloud upload، پیام/SMS/OTP واقعی، پرداخت یا migration دیتابیس اصلی انجام نشد. نورا روی DB توسعهٔ خالی اجرا شد؛ fixtureها تنها در سرور QA جدا با عنوان صریح «دادهٔ واقعی نیست» بودند. Strix مستقل انگلیسی حفظ شد.

## آماده‌سازی قابل تکرار

- npm ریشه اکنون `test:nora` و `test:nora:browser` دارد؛ dependencies از lock واقعی نصب می‌شوند. نیاز Node jsdom 30 یعنی 22.22.2+/24.15+/26+ در manifest نیز ثبت شد.
- runnerهای Python مسیر import و cwd صحیح backend/bot را تعیین می‌کنند و گروه‌ها در processهای جدا اجرا می‌شوند؛ وابستگی به PYTHONPATH دستی این sandbox وجود ندارد.
- `local-dev.py init/check/migrate/serve` env خصوصی و SQLite خالی داخل `.local` را مدیریت می‌کند، فقط Alembic واقعی اجرا می‌کند، overwrite نمی‌کند، DB بیرون مسیر مجاز/کلید provider خارجی را رد می‌کند و inherited provider/SEO config را نیز خالی می‌کند.
- owner محلی اختیاری با getpass و hash خصوصی است؛ هیچ credential واقعی یا hash در `.env.local.example`، گزارش یا خروجی نیست. فایل env جدید 0600 است و پوشهٔ state/environmentها Git ignored هستند.
- browser QA با managed Chromium/Chrome local در Windows/macOS/Linux قابل پیکربندی است؛ Sparticuz فقط fallback opt-in Linux برای sandbox است. defaultها دیگر `/tmp` نیستند؛ fixture/report در `.local/qa`، Node deps از package واقعی workspace.
- مسیر ثابت `/home/user/strix` و file URL خام/percent-encoded در آزمون‌های رابط رفع شد. post/QR/audit از مسیر متفاوتِ دارای فاصله واقعاً اجرا شدند.
- تست admin وضعیت رویداد به روز ۲۱ ماه وابسته بود و در اجرای تازه شکست خورد؛ تاریخ fixture آیندهٔ قطعی شد، بدون دست‌کاری ساعت یا رفتار محصول. 817 assertion بعد از اصلاح موفق بودند.
- یک advisory transitive `source-map-js` در npm lock harness پیدا شد؛ patch سازگار lockfile، `npm ci` مجدد و audit صفر انجام شدند. manifest مستقیم jsdom/jsqr عوض نشد.

## نتیجهٔ واقعی فرمان‌ها

| فرمان / بررسی | نتیجهٔ اجراشده | تفسیر صحیح |
|---|---|---|
| `python -m venv` با Python 3.11.2 | موفق | یک محیط واقعاً خالی؛ Python root Strix محسوب نمی‌شود |
| نصب requirements-dev backend و requirements bot | موفق | همهٔ packageها در venv جدا؛ source runtime اصلی بازنویسی نشد |
| `python -m pip check` | موفق؛ dependency شکسته صفر | runtime package compatibility نصب‌شده، نه همهٔ providerها |
| `npm ci` root lock | موفق | بدون symlink dependency این جلسه؛ Node 22.22.3 |
| `local-dev.py init` | موفق؛ Alembic head 0022 | DB خالی، بدون حساب/response/محتوای نمونه؛ خارجی نیست |
| `local-dev.py check` | موفق | revision صحیح، provider خاموش و HTTP local cookie config |
| init تکراری | **عمداً رد شد؛ exit 2** | عدم overwrite env/DB؛ guard موفق، نه خرابی اجرا |
| Uvicorn از `local-dev.py serve --host 0.0.0.0 --port 8000` | موفق؛ برنامه واقعاً listening | UI و API همان process؛ بدون انتشار production |
| health، خانه، حساب، login، events، support | HTTP 200 | صفحات واقعی روی localhost؛ خالی‌بودن DB به دادهٔ ساختگی تبدیل نشد |
| account API بدون session / public content بدون record | 401 / 404 | state طبیعی DB نصب تازه، نه نتیجهٔ موفق login یا محتوای واقعی |
| robots / llms / favicon و route ناموجود | 200 / 200 / asset موجود / 404 | custom 404 از HTTP نیز واقعاً 404 |
| sitemap بدون دامنه | **503 مورد انتظار** | domain رسمی نداریم؛ sitemap production موفق اعلام نمی‌شود |
| integration status | `deliveryEnabled=false`, `sendAttempted=false` | هیچ ارائه‌دهنده‌ای تماس واقعی نگرفت |
| `run-python-tests.py backend` بدون PG | **126 passed, 4 skipped** | هشت regression local-dev تازه + تست‌های موجود؛ PG skip موفق نیست |
| `run-postgres-tests.py` روی PostgreSQL موقت با Unix socket | **130 passed**؛ یک warning | چهار PG case واقعاً اجرا شد؛ instance/تراکنش کاملاً isolated و حذف/stop شد |
| bot pytest | **123 passed** | provider keys خاموش؛ legacy phase scripts دارای side effect به‌صورت blanket اجرا نشدند |
| storage guard | **PASS** | main قبل از ساخت SQLite legacy متوقف می‌شود |
| Mypy backend | **0 خطا در 40 source file** | همان config basic پروژهٔ Nora؛ root Strix typecheck نیست |
| npm test UI، اجرای اول | **18/19 suite موفق؛ admin یک failure** | شکست واقعی date-dependent fixture پنهان نشد |
| admin پس از اصلاح تاریخ/مسیر | **817 بررسی، صفر خطا** | انتظار انتشار future fixture از تقویم روز CI مستقل شد |
| `npm run test:nora` پس از اصلاح | **19/19 suite موفق** | همهٔ fixtureها حفظ؛ no shell glob و manifest/lock واقعی |
| suiteهای post، QR و audit در checkout متفاوت با فاصله | **99 / 33 / 16 موفق** | اصلاح portability واقعاً بیرون مسیر فعلی بررسی شد؛ Windows بومی نیست |
| Playwright managed Chromium install | **ناموفق، exit 1**؛ CDN مسدود/شبکه | قبل از browser fallback به‌عنوان PASS گزارش نشد |
| Sparticuz fallback، تلاش اول | **ناموفق**؛ `libnspr4.so` نبود | bundled libraries باید unpack شوند؛ ابزار QA اصلاح شد |
| fallback، تلاش دوم | **ناموفق**؛ export package.json نبود | module root از entry export واقعی resolve شد، نه subpath ممنوع |
| `npm run test:nora:browser` با fallback opt-in Linux | **84 case، صفر JS error/axe violation/overflow؛ exit 0** | Chromium واقعی 153؛ روشن/تیره، 320/390/1280، member history مثبت در چهار case، دو keyboard switch |
| TypeScript viewer Strix | موفق | `tsc --noEmit` از deps frozen مستقل |
| Vite viewer build، outDir تازه | موفق | static قبلی untouched؛ chunk 975.00KB/gzip299.68KB هنوز هشدار بزرگ دارد |
| نصب Python 3.12 توسط uv 0.13.1 با system certs | **ناموفق**؛ TLS handshake EOF پس از retry | 3.12.15 دانلود نشد؛ Python 3.11 را به‌جای supported root اجرا نکردیم |
| root Strix runtime/pytest/Mypy/Pyright و Go TUI/wheel/scan | **اجرا‌نشده/مسدود** | Python 3.12، Go1.24 و Docker در محیط نبودند؛ هیچ scan واقعی/خارجی اجرا نشده |
| Windows/macOS native، Firefox/WebKit/صفحه‌خوان واقعی | **اجرا‌نشده** | تغییر portable code برابر تأیید عملی چند سیستم‌عامل/مرورگر نیست |

warn کتابخانهٔ FastAPI/Starlette دربارهٔ httpx TestClient در این venv وجود دارد. تست‌های واقعی موفق‌اند، ولی این warning یا محدودیت provider بیرونی حذف/پنهان نشده است. PostgreSQL 16.2 صرفاً runtime تست است، نه نسخه/وضعیت امنیت دیتابیس production.

## فایل‌های این مرحله

- ریشه: `LOCAL-DEVELOPMENT.fa.md`، `.gitignore` و npm `package.json/package-lock.json` harness.
- ابزارهای جدید: `tools/local-dev.py`، `tools/run-unit-tests.cjs`، `tools/run-python-tests.py`، `tools/run-postgres-tests.py`.
- QA portable: `tools/browser-audit.cjs`، `tools/browser-fixture-server.py`؛ بدون تغییر app boot عمومی.
- نمونهٔ خالی: `.env.local.example`؛ پیوند راهنما در `backend/README.fa.md`.
- آزمون جدید: `backend/tests/test_local_development.py`؛ هشت case محافظت DB/env/provider/password.
- اصلاح harnessهای file path: `account/admin/post/qr/smoke/support/delivery.test.mjs`؛ admin fixture date مستقل شد. رفتار محصول/فونت‌ها/شناسه‌های DB/API تغییر نکردند.
- گزارش و شواهد این مرحله. generated venv/DB/env/cookie/build/سرویس‌های موقت جزو source/publish نیستند.

## آمادگی واقعی

**اجرای محلی نورا با DB خالی تأیید شد.** توسعه‌دهنده بدون DNS، پرداخت، بله یا Safir می‌تواند UI/API، guards، tests، metadata و 404 را بررسی کند. ورود مالک محلی اختیاری، آزمون member/owner با fixture جدا، و PostgreSQL regression disposable است.

**اجرای کامل همهٔ محصولات/سرویس‌ها تأیید نشده:** root Strix و بعضی مسیرهای legacy/providerهای واقعی نیازمند پیش‌نیاز/دسترسی/اجازه‌اند. روی سیستم توسعه‌دهنده، اول Python3.12+/Go1.24+/Docker/Chromium را طبق بخش‌های مربوط فراهم و فرمان‌های واقعی را اجرا کنید. هیچ محیط نمونه یا موفقیت build viewer، تأیید production یا همهٔ تست‌های پروژه نیست.
