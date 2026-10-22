# اجرای قابل‌تکرار آزمون‌های Nora در محیط تمیز — ۲۰۲۶-۱۰-۲۲

هدف: هر کس با یک checkout تازه بتواند همان runnerهای رسمی مخزن را اجرا کند و همان شمارش‌ها را بگیرد. هیچ تستی حذف یا تضعیف نشده؛ فقط پیش‌نیازهای محیط مستند شده‌اند. مبنای اعداد: شاخهٔ مرجع `arena/840de336-strix` @ `0c637ab` (کد بک‌اند/فرانت‌اند همان `6520787`؛ کامیت‌های بعدی فقط مستندات).

## ۱. پیش‌نیازها (نسخه‌های واقعاً استفاده‌شده)
- Python 3.11.2 · Node v22.22.3 / npm 10.9.8
- `pgserver==0.1.4` فقط برای اجرای PostgreSQL موقت (بستهٔ توسعه، native Linux/macOS)

## ۲. پایتون: یک venv برای بک‌اند + ربات + mypy
```bash
cd Final-Delivery/website/nora-ui
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt \
            -r ../../bale-bot/nora_bot/requirements.txt \
            httpx "pgserver==0.1.4" psycopg
python tools/run-python-tests.py all          # backend (SQLite) + bot + types (mypy) + storage
python tools/run-postgres-tests.py            # همان backend روی PostgreSQL موقت (Unix socket، بدون دیتابیس اصلی)
```
`run-python-tests.py` خودش `PYTHONPATH` و متغیرهای توکن را (خالی) تنظیم می‌کند؛ اجرای مستقیم `pytest` از پوشهٔ `bale-bot` یک فایل آزمون ربات کمتر را می‌بیند (۲۰۸/۲ به‌جای ۲۱۰/۱) — بنابراین عدد رسمی همان runner است.

## ۳. Node: runner رسمی و وابستگی‌های آن
`nora-ui` فایل `package.json` ندارد؛ ۳۲ سوئیت `*.test.mjs` با ESM مستقیماً `jsdom` و یک سوئیت (`qr.test.mjs`) `jsqr` را import می‌کنند. ESM از `NODE_PATH` استفاده نمی‌کند؛ بسته‌ها باید در `node_modules` کنار فایل‌های تست (یا پوشهٔ والد) باشند. `node_modules/` در `.gitignore` ریشهٔ مخزن است.
```bash
cd Final-Delivery/website/nora-ui
npm install --no-save --no-package-lock --no-audit --no-fund jsdom@30.1.3 jsqr@1.4.0   # ۳۷ بسته، ~۳ ثانیه
node tools/run-unit-tests.cjs                 # هر سوئیت در فرایند جدا با --max-old-space-size=3072
```
نتیجهٔ انتظاری: `Nora suites: 37/37 passed; 0 failed.` با کد خروج ۰. اگر `jsqr` نصب نباشد فقط `qr.test.mjs` با `ERR_MODULE_NOT_FOUND` می‌شکند (۳۶/۳۷) — این خطای محیط است، نه نقص تست. ابزارهای مرورگر (`tools/browser-*.cjs`, `*-browser-evidence.cjs`) جدا از runner واحدند و به `playwright-core` + `@sparticuz/chromium` نیاز دارند.

## ۴. نتایج ثبت‌شده روی مرجع (آزموده‌شده، ۲۰۲۶-۱۰-۲۲)
| فرمان | نتیجه | خروج |
|---|---|---|
| `python -m pytest -q tests` (cwd `backend`, SQLite) | 367 passed, 4 skipped | 0 |
| `python tools/run-postgres-tests.py` | 371 passed (`PASS backend`) | 0 |
| `python tools/run-python-tests.py bot` | 210 passed, 1 skipped | 0 |
| `python tools/run-python-tests.py storage` | PASS | 0 |
| `python tools/run-python-tests.py types` (mypy) | Success: no issues found in 73 source files | 0 |
| `node tools/run-unit-tests.cjs` (محیط سندباکس، پیش از نصب `jsqr`) | 36/37؛ تنها خطا `qr.test.mjs`: `Cannot find package 'jsqr'` | 1 |
| `node qr.test.mjs` پس از `npm i jsqr` | qr: 33 بررسی، 0 خطا | 0 |
| اجرای تمیز (بخش ۳، export با `git archive` از `0c637ab` در پوشهٔ موقت، نصب تازهٔ jsdom+jsqr) | → بخش ۵ | |

## ۵. اجرای تمیز Node (شاهد تکرارپذیری)
- روش: `git archive 0c637ab Final-Delivery/website/nora-ui | tar -x -C /tmp/clean-nora` (بدون `node_modules`، بدون symlink)، سپس دقیقاً دو فرمان بخش ۳.
- `npm install …`: `added 37 packages`، `jsdom 30.1.3 jsqr 1.4.0`، خروج ۰.
- `node tools/run-unit-tests.cjs`: **`Nora suites: 37/37 passed; 0 failed.`**، `RUNNER_EXIT=0`؛ از جمله `admin-test: 817 بررسی، 0 خطا`، `admin-restore: 50 بررسی، 0 خطا`، `فرم خرید: 30/30 معیار`، `qr: 33 بررسی، 0 خطا`.
- لاگ کامل: `/tmp/node-suites-clean.log` در سندباکس (خارج از مخزن؛ ۳۶۶۵ خط). پوشهٔ موقت پس از ثبت پاک شد.

## ۶. آنچه این سند ثابت نمی‌کند
این اعداد متعلق به **بک‌اند مرجع بدون رابط U4/U5/H1** است. پس از ورود شاخهٔ رابط، همهٔ موارد بخش ۲ و ۳ باید روی SHA یکپارچه دوباره اجرا و با فرمان/شمارش/کد خروج ثبت شوند؛ نتایج بالا جایگزین آن نیستند.
