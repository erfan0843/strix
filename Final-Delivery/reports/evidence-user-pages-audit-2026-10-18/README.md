# شواهد ممیزی صفحات کاربر نورا — 2026-10-18

گزارش اصلی: `../USER-PAGES-AUDIT-2026-10-18.fa.md`

- `logs/pytest-read-boundary-red.log` — اثبات نشت محتوای غیرعمومی در `59f971f` (3 failed) پیش از اصلاح.
- `logs/pytest-user-pages-2026-10-18.log` — pytest کامل پس از اصلاح (225 passed, 4 skipped).
- `logs/mypy-user-pages-2026-10-18.log` — mypy تمیز.
- `logs/unit-tests-user-pages-2026-10-18.log` — `tools/run-unit-tests.cjs` (25/25).
- `logs/flows-audit-run1.log` (42/47 قبل از اصلاح) و `logs/flows-audit-run2.log` (53/53 بعد) — Playwright روی سرور تست محلی.
- `logs/pages-audit-run1.log`, `logs/pages-audit-after.log` — خزش ۲۷ مسیر × ۵ ویوپورت (قبل) و ۱۰ صفحهٔ تغییریافته (بعد).
- `pages-audit-before.json`, `pages-audit-after.json`, `flows-results-run2.json` — دادهٔ خام.
- `shots/before/`, `shots/after/` — تصویر ۳۹۰×۸۴۴ (و `-dark`) صفحه‌ها؛ `shots/flows/` — حالت‌های جریانی؛ `shots/sheets/` — شیت‌های مقایسه (موبایل، دسکتاپ، تیره، PNG↔WebP صفحهٔ ۴۰۴).
- `logs/*final*`, `logs/flows-audit-run3|4.log`, `logs/verify-remaining-fixes-2026-10-18.log`, `logs/ticket-sideeffect-{before,after}.log`, `shots/final-verify/` — فاز تثبیت نهایی (بخش ۱۳ گزارش).
- `tools/pages-audit.mjs`, `tools/flows-audit.mjs`, `tools/verify-remaining-fixes.mjs`, `tools/seed-test-data.py` — اسکریپت‌های ممیزی و seed دادهٔ تست (مسیرهای مطلق محیط sandbox را دارند؛ برای اجرا `browser-launch.cjs` همین مخزن را مسیردهی کنید).

محیط: سرور تست ایزوله روی SQLite موقت با دادهٔ «(دادهٔ تست)»؛ هیچ دامنهٔ زنده، دادهٔ واقعی، راز، کوکی یا توکنی در این پوشه نیست. شمارهٔ `09120000000` در اسکریپت جریان‌ها ساختگی است.
