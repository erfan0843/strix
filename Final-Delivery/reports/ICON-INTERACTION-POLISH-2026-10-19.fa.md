# نورا — سیستم آیکون، طراحی دکمه و بازخوردهای ریز (micro-interactions)
**تاریخ:** ۲۰۲۶-۱۰-۱۹ · **مخزن:** `erfan0843/strix` · **شاخه:** `arena/840de336-strix` · **PR:** #1 (باز؛ بدون merge/release/deploy)
**پوشهٔ شواهد:** `Final-Delivery/reports/evidence-icon-interaction-polish-2026-10-19/` (لاگ‌ها با `git add -f`، تصاویر قبل/بعد، اسکریپت‌ها)

---

## ۰. وضعیت اولیه (پیش از هر تغییر)

- HEAD شاخه: `49f711c` = `origin/arena/840de336-strix` (هیچ تغییر تازه‌ای روی شاخه نبود)؛ worktree تمیز (فقط symlink‌های `node_modules` که ردیابی نمی‌شوند).
- محیط: venv، وابستگی‌های Node، مرورگر headless و سرور تست محلی (`uvicorn` روی `:8000` با DB ایزولهٔ `/tmp/nora-preview`) از فاز قبل برقرار بود؛ دادهٔ تست همان seed فاز قبل (`qa-ev-*`, `np-qa-*`, `qa-p1`, `qa-partner-*`, فرم منتشرشدهٔ تست).
- همهٔ آزمون‌های بصری/رفتاری این گزارش روی **همان سرور تست محلی** اجرا شده‌اند، نه دامنهٔ زنده.

### فایل‌های بررسی‌شده
`icons.svg`، `glass.css`، `nora.css`، `ui.js`، CSS/JS صفحه‌ها (`events-page.css`, `events.css`, `person-page.css`, `partner-page.css`, `login.css/js`, `account.css/js`, `support.css/js`, `admin.css/js`, `events-page.js`, `event-page.js`, `post.html`)، بلوک‌های `<style>` درون `home/form/create/builder/event/events/post/final-page-review`، و اسپرایت‌های SVG درون همهٔ ۱۹ صفحهٔ HTML. اسکریپت `tools/screenshot-matrix.mjs` هم در هر صفحه `use[href]` شکسته، کنترل‌های کوچک‌تر از ۲۴px، دکمهٔ آیکونی بدون نام دسترس‌پذیر، گلیف/ایموجی در کنترل‌ها، سرریز افقی و خطای کنسول را شمرد (`logs/metrics-before.jsonl`).

### یافته‌های اولیه
| # | یافته | شاهد |
|---|---|---|
| 1 | مجموعهٔ آیکون نورا (شبکهٔ ۲۴، ضخامت ۱٫۷، سرِ گرد) در ۱۰ صفحه + `icons.svg` یکسان است، اما **`events.html` (۱۶ نماد) و `support.html` (۴۳ نماد)** و تک‌نمادهایی در `account/admin/login/offline` همان شناسه‌ها را با **رسم متفاوت** (ضخامت ۱٫۸، مسیر دیگر) داشتند؛ در مجموع ۴۹ شناسه از ۱۰۲ شناسه بین صفحه‌ها واگرا بود | اسکریپت مقایسهٔ بدنهٔ `<symbol>`ها (بخش ۱) |
| 2 | دو ارجاع شکسته: `builder.html → #i-refresh` (دکمهٔ «به‌روزرسانی API» و «تازه‌سازی») و `form.html → #i-info` (۳ جا، از جمله پیام پیش‌نمایش پرداخت) | `metrics-before.jsonl`: form ۷ بار `broken:["#i-info"]`؛ builder ۷ بار |
| 3 | کلید شب/روز در `events/person/partner` به‌جای SVG، گلیف متنی `☼`/`☾` داشت که در عمل **خالی** دیده می‌شد؛ در `home/login/event/post/account/support` SVG بود | `shots/compare/cmp-events-top-zoom.jpg`, `cmp-person-top-zoom.jpg` |
| 4 | `create.html` برای «شب / روز» (ریل دسکتاپ و نوار پایین) آیکون **چشم** داشت | `shots/compare/cmp-create-1280.jpg` |
| 5 | `icons.svg` (که Service Worker آن را در پوسته کش می‌کند) فقط ۶۳ نماد داشت؛ ۳۹ نمادِ فقط-درون-صفحه در آن نبود | `git diff icons.svg` |
| 6 | دکمه‌ها: `.btn:hover` فقط تغییر پس‌زمینه؛ `.btn:active` ۰٫۹۷۵؛ `.icon-btn` نسخهٔ `glass.css` (صفحه‌های form/create/builder) **بدون** گذار و بازخورد فشردن؛ `.btn.stop` بدون hover متمایز؛ `aria-busy` در `form.html`/`create.html` روی دکمه‌های عملیات واقعی set می‌شد اما **هیچ CSS** برایش نبود (بدون چرخانه)؛ `.toast` بدون خروج نرم و `is-error` بدون استایل (فقط آیکون ✓ پنهان می‌شد) | `glass.css` قبل از تغییر |
| 7 | **موفقیت دروغین کپی:** `ui.copyText` در مسیر fallback، خروجی `execCommand('copy')` را نادیده می‌گرفت و همیشه «کپی شد» می‌گفت | `ui.js` L~790 قبل از تغییر |
| 8 | تنظیم «حرکت: خاموش» نورا (`html[data-motion="off"]`) فقط در `nora.css` بود → در صفحه‌های فقط-`glass.css` (form/create/builder) اثر نداشت | `nora.css:521` |
| 9 | دکمه‌های بنر خانه (`.bbtn`) هیچ hover/active/focus اختصاصی نداشتند | `home.html` style block |
| 10 | نسخهٔ کش `nora.css` در `login.html` (`v=121`) با بقیه (`v=101`) ناهمخوان بود | grep |
| 11 | هیچ دکمهٔ آیکونی بدون نام دسترس‌پذیر، هیچ سرریز افقی و هیچ خطای کنسول در ۱۳۳ ترکیب صفحه×ویوپورت×تم یافت نشد | `metrics-before.jsonl` |

---

## ۱. قواعد یکپارچهٔ آیکون (اعمال‌شده)

- **منبع واحد:** هر شناسهٔ `i-*` در همهٔ صفحه‌ها همان بدنهٔ SVG را دارد (نسخهٔ اکثریت = `icons.svg`/`home.html`)؛ `icons.svg` اکنون **مرجع کامل ۱۰۲ نماد** است. هیچ کتابخانهٔ خارجی (از جمله Lucide) نصب یا از CDN بارگذاری نشد؛ مجموعهٔ خود نورا از نظر فرم با Lucide هم‌خانواده است و کمبودی که آوردن کتابخانه را توجیه کند دیده نشد.
- شبکهٔ ۲۴×۲۴، `stroke 1.7` (استثناهای عمدی: `i-check`/`i-sun` با ۱٫۹ برای خوانایی در ۱۴–۱۶px)، `linecap/linejoin round`.
- اندازه‌ها (بدون تغییر، فقط تأیید): دکمهٔ معمولی ۱۹–۲۰px، دکمهٔ کوچک/چیپ ۱۶–۱۷px، تب‌بار ۲۶px، آیکون وضعیت/کارت ۲۴–۳۴px، کلید شب/روز ۱۴px.
- آیکون‌های تزئینی داخل دکمه‌های متنی همچنان `aria-hidden`/بدون نام‌اند؛ هر دکمهٔ آیکونی `aria-label` دارد (سنجهٔ خودکار: ۰ مورد بدون نام، قبل و بعد).
- نگاشت کاربرد→نماد (موجود در مجموعه): خانه `i-home`، رویداد `i-calendar`، فرم `i-doc`/`i-align`، جست‌وجو `i-search`، فیلتر `i-sliders`/`i-filter`، اشتراک `i-share`، کپی `i-copy`/`i-link`، ادامه/جزئیات در RTL `i-chev-left` (جهت حرکت = چپ؛ بررسی شد و با CSS معکوس نشده)، اعلان `i-bell`، پروفایل `i-user`، سنجاق `i-pin`، ویرایش `i-pen`، بستن `i-close`، حذف `i-trash`، موفقیت `i-check`، هشدار/اطلاع `i-info`، پشتیبانی `i-headphone`، بارگذاری: چرخانهٔ CSS (`btnSpin`) یا `i-refresh.is-spinning`.
- کلید شب/روز: همه‌جا SVG `i-sun`/`i-moon`؛ در دکمه‌های متنی (`create.html`) جفت `theme-ico-moon/sun` که **حالت مقصد** را نشان می‌دهد (در روز ماه، در شب خورشید).

---

## ۲. اجزای دکمه و کنترل اصلاح‌شده (همه در `glass.css`، مشترک همهٔ صفحه‌ها)

| دسته | قاعدهٔ یکسان |
|---|---|
| Primary | گرادیان برند موجود؛ hover: بالا آمدن ۱px + سایهٔ کمی عمیق‌تر + آیکون ۱٫۰۶؛ **درخشش یک‌بارهٔ ۵۶۰ms** (`::after` زیر متن، `isolation:isolate`، جهت‌آگاه با `--shine-dir` در RTL)؛ press ۰٫۹۷؛ حلقهٔ فوکوس با هالهٔ روشن داخلی تا با hover اشتباه نشود |
| Secondary (`.btn`) | hover: پس‌زمینهٔ `surface-2` + بالا آمدن ۱px؛ press ۰٫۹۷؛ گذار ۱۴۰ms فنری |
| Quiet/Tint | بدون تغییر رنگ؛ همان بازخورد حرکت |
| Icon-only (`.icon-btn`) | گذار یکسان در هر دو نسخه (glass/nora)؛ hover رنگ برند + آیکون ۱٫۰۷؛ press ۰٫۹۳؛ `.icon-btn.stop`؛ روی لمس، نسخهٔ ۳۸px نوار بالا با `::before` به ۴۴px هدف می‌رسد بدون بزرگ‌شدن آیکون |
| Destructive (`.btn.stop`) | tint توقف + hover پررنگ‌تر (۲۰٪)؛ `icon-btn.stop` با رنگ توقف |
| Toggle/Segmented | `.chip`/`.seg button` با گذار یکسان؛ `.seg button.on` pop ظریف ۳۶۰ms فقط با `prefers-reduced-motion:no-preference`؛ تب‌بار همان `noraTabPop` قبلی؛ کلید شب/روز بدون تغییر منطق |
| Disabled | `[disabled]`, `:disabled`, `[aria-disabled="true"]`: opacity ۰٫۴۵، `pointer-events:none`، بازنشانی transform/filter (حس hover نمی‌دهد) |
| Loading (`[aria-busy="true"]`) | چرخانهٔ ۱۵px (۱۲px در `.sm`) جای آیکون، متن می‌ماند، `pointer-events:none`، `cursor:progress`، درخشش خاموش؛ `.lgbtn` ورود هم همین را با `login-spin` دارد |
| Hover فقط با نشانگر واقعی | همهٔ قواعد hover داخل `@media (hover:hover) and (pointer:fine)`؛ روی لمس هیچ hover مصنوعی نیست |

JS: `login.js` روی سه دکمهٔ submit و «خروج» هنگام `state.busy` → `aria-busy="true"`؛ `account.js` روی «پیوند حساب بله»/«برداشتن پیوند» هنگام busy. `form.html`/`create.html` از قبل `aria-busy` را روی دکمه‌های ارسال/کوپن/انتشار/رسید set می‌کردند و اکنون دیده می‌شود. هیچ listener عمومی یا ripple جاوااسکریپتی اضافه نشد.

---

## ۳. انیمیشن‌ها و حالت‌های تعاملی

- زمان‌ها: hover/press ۱۴۰ms (`--t-fast`, `--spring`)، گذار رنگ ۲۲۰ms (`--t`)، درخشش ۵۶۰ms یک‌بار، pop سگمنت ۳۶۰ms، ورود توست ۲۲۰ms / خروج ۱۴۰ms. فقط `transform`/`opacity` (به‌جز رنگ/سایهٔ سبک). هیچ عنصر دائماً متحرکی اضافه نشد.
- **کاهش حرکت:** هر دو سازوکار حفظ و تقویت شد: `prefers-reduced-motion:reduce` (قاعدهٔ سراسری `glass.css` + استثناهای صریح برای shine/segPop) و `html[data-motion="off"]` که اکنون در `glass.css` است و همهٔ صفحه‌ها (از جمله form/create/builder) را می‌پوشاند.
- **توست:** ورود `up`، خروج `is-out` (۱۶۰ms) و سپس حذف `on`؛ توست پشت‌سرهم هر دو زمان‌سنج را صفر می‌کند؛ `is-error` با رنگ توقف و آیکون ⓧ (mask) — وضعیت فقط با رنگ بیان نمی‌شود.
- **کپی:** `ui.copyText` فقط پس از موفقیت واقعی (`clipboard.writeText` resolve یا `execCommand('copy')===true`) «کپی شد» می‌گوید؛ در شکست، توست خطا و callback بعدی اجرا نمی‌شود. (`post.html` از قبل مسیر صادقانهٔ خودش را داشت.)
- **رفع مورد قدیمی:** `.icon-btn:active` و `html[data-motion]` که در `nora.css` تکرار شده بودند حذف شدند تا برای یک selector دو قاعدهٔ موازی نباشد.

---

## ۴. تصاویر قبل و بعد

- `shots/before/` و `shots/after/`: ۸۷ تصویر در هر پوشه — همهٔ ۱۸ صفحه در `390×844` و `1280×800` روشن + تاریک؛ و `360×800`، `768×1024`، `1440×900` برای home/events/create/form/login. (کل ۱۳۳ ترکیب در هر اجرا گرفته شد؛ سنجه‌های همه در `logs/metrics-*.jsonl` است.)
- `shots/compare/`: مقایسه‌های کنار هم — `cmp-events-390.jpg`، `cmp-person-390.jpg`، `cmp-support-390.jpg`، `cmp-create-1280.jpg`، `cmp-events-1280-dark.jpg`، `cmp-partner-390-dark.jpg`، زوم سر صفحه‌ها، `sheet-shine.png` (سه فریم: ساکن / hover با درخشش / hover ساکن‌شده)، `sheet-interact.png` (چرخانهٔ busy روی دکمهٔ اصلی، فرم و ورود؛ توست خطا؛ کلید شب/روز person در روشن و تاریک).
- `shots/interact/`: برش‌های رفتاری (`primary-busy`, `primary-focus`, `toast-error`, `login-busy`, `form-next-busy`, `person-theme-switch`, `person-dark-top`, `primary-hover-shine`).

---

## ۵. آزمون‌های واقعاً اجراشده (کد خروج واقعی)

| فرمان / اسکریپت | نتیجه | exit | لاگ |
|---|---|---|---|
| `tools/screenshot-matrix.mjs` قبل از تغییر (۱۹ صفحه × ۷ ترکیب) | ۱۳۳ تصویر؛ `broken`: form ۷، builder ۷، nora-pay-preview (→form) ۷؛ گلیف در کلید تم: events/person/partner | 0 (یک بار SIGSEGV مرورگر، با retry تکمیل شد) | `logs/screenshots-before.log`, `metrics-before.jsonl` |
| همان، بعد از تغییر | ۱۳۳ تصویر؛ **broken=0، emoji=0، overflowX=0، errs=0 در همه** | 0 | `logs/screenshots-after.log`, `metrics-after.jsonl` |
| `tools/interaction-checks.mjs` (Playwright روی سرور تست؛ hover/active/focus/disabled/busy، لمس، کاهش حرکت، `data-motion`، توست، کپی موفق/ناموفق، سگمنت، icon-btn، hit-area لمسی، صفحه‌کلید، تم تاریک، busy ورود/فرم، ارجاع‌های `<use>` در ۱۳ صفحه) | **35 passed, 0 failed** | 0 | `logs/interact-final.log` (اجراهای میانی با شکست‌های خودِ اسکریپت: `interact-run1-first-attempt.log`, `interact-run4.log`) |
| `node tools/run-unit-tests.cjs` (۲۵ مجموعه) — اجرای اول | 24/25؛ `admin.test` ۳ شکست: کپی در jsdom حالا صادقانه «ناموفق» می‌گفت (jsdom کلیپ‌بورد ندارد) | 1 | `logs/unit-tests-run1-before-test-fix.log` |
| `node admin.test.mjs` پس از شبیه‌سازی `execCommand` موفق در harness تست | ۸۱۷ ✓، ۰ ✗ | 0 | `logs/admin-test-after-fix.log` |
| `node tools/run-unit-tests.cjs` — اجرای نهایی | **25/25 passed; 0 failed** (post.test ۱۰۴ با سنجهٔ تازهٔ «شکست کپی = توست خطا») | 0 | `logs/unit-tests-final.log` |
| `python -m pytest -q tests -p no:cacheprovider` (بک‌اند؛ person/partner HTML تغییر کرده بود) | **225 passed, 4 skipped** | 0 | `logs/pytest-final.log` |

رفتارهای فهرست‌شده در بند ۱۰ درخواست که واقعاً امتحان شدند: hover/active/focus/disabled ✓، کلیک پشت‌سرهم (توست‌های پیاپی، busy با `pointer-events:none`) ✓، سوییچ و تب فعال (کلید تم، سگمنت، تب‌بار) ✓، باز/بسته‌شدن modal و منو: فقط در مجموعهٔ واحد (jsdom) نه در مرورگر واقعی این فاز، کپی پیوند موفق/ناموفق ✓، توست موفق/خطا ✓، spinner در عملیات: روی دکمه‌هایی که کد واقعاً `aria-busy` می‌گذارد (شبیه‌سازی‌شده با set کردن attribute؛ عملیات سروری واقعی اجرا نشد) ✓، تغییر تم و کاهش حرکت ✓، صفحه‌کلید ✓، نمایشگر کوچک و لمس ✓، ذخیره/برداشتن ذخیره (سنجاق): فقط در مجموعهٔ واحد موجود.

---

## ۶. ایرادهای رفع‌شده (خلاصه)

1. ۴۹ نماد واگرا بین صفحه‌ها → یکدست (events ۱۶، support ۴۳، + ۵ تک‌مورد).
2. دو ارجاع `<use>` شکسته (builder `i-refresh`، form `i-info`).
3. کلید شب/روز خالی/گلیفی در events/person/partner → SVG.
4. آیکون چشم برای شب/روز در create → جفت ماه/خورشیدِ حالت‌آگاه.
5. `icons.svg` ناقص → مرجع کامل.
6. نبود بازخورد فشردن/گذار در `icon-btn` نسخهٔ glass؛ نبود hover متمایز برای حذف.
7. `aria-busy` بدون نمایش → چرخانه + قفل کلیک؛ ورود و حساب هم `aria-busy` می‌گذارند.
8. موفقیت دروغین کپی در fallback.
9. توست بدون خروج نرم و بدون آیکون خطا.
10. `data-motion=off` بی‌اثر در صفحه‌های فقط-glass.
11. `.bbtn` بنر خانه بدون hover/active/focus.
12. ناهمخوانی نسخهٔ کش `nora.css` در login؛ همهٔ کلیدهای کش فایل‌های تغییرکرده بالا رفت (`glass v100`, `nora v102`, `ui.js v129`, `login.css v126`, `login.js v128`, `account.js v126`, SW `nora-v98`) تا نسخهٔ قدیمی CSS به‌طور نامعلوم دیده نشود؛ قواعد حریم خصوصی SW دست نخورد.

---

## ۷. صفحه‌ها/خدماتی که آزمون واقعی نداشتند

- **`index.html`**: فقط ریدایرکت به `home.html` (تصویرش همان خانه است).
- **`loading-preview.html`، `nora-pay-preview.html`، `final-page-review.html`**: صفحه‌های پیش‌نمایش/آزمایشی‌اند؛ `nora-pay-preview` فقط فرم نمونهٔ محلی می‌سازد و به `form.html` می‌رود (هیچ پرداختی). **عمداً به جریان عملیاتی وصل نشدند**؛ فقط اسکرین‌شات گرفته شد. `final-page-review` از `icons.svg#…` بیرونی استفاده می‌کند و با کامل‌شدن `icons.svg` سازگار ماند.
- **`404.html`، `nora-pay-preview.html`، `index.html`** `glass.css`/`nora.css` را بارگذاری نمی‌کنند؛ ۴۰۴ کنترل خودش را دارد و در سنجه‌ها بدون نقص بود → تغییری لازم نشد. تم تیره برای ۴۰۴/offline/final-page-review همچنان «نیازمند تصمیم» از گزارش قبلی است.
- عملیات واقعی شبکه‌ای پشت دکمه‌های busy (ارسال پیامک، پرداخت، رسید، پیوند بله) اجرا نشد؛ وضعیت busy با set کردن همان attribute که کد واقعی می‌گذارد تأیید شد.
- `admin.html` فقط با نشست مالکِ سرور تست اسکرین‌شات شد؛ تعامل‌های پنل در مجموعهٔ واحد (`admin.test`, ۸۱۷ سنجه) پوشش دارد نه در مرورگر واقعی این فاز.

---

## ۸. موارد باقی‌مانده و دلیل

| مورد | دلیل انجام‌نشدن / تصمیم |
|---|---|
| ادغام دو نسخهٔ `.icon-btn` (glass ۴۴px بی‌قاب برای فرم‌ساز، nora ۳۸px قاب‌دار برای نوار بالا) به یک جزء | دو بافت متفاوت‌اند؛ رفتار (گذار/فشردن/hover) یکسان شد، ظاهر عمداً متفاوت ماند تا نوار بالا جابه‌جا نشود |
| `.btn.sm` ۳۴px و چیپ‌های ۳۲px دسکتاپ به ۴۴px | روی لمس چیپ/سگمنت از قبل ۴۴px است؛ دسکتاپ حداقل WCAG (۲۴px) را دارد؛ بزرگ‌کردن سراسری = تغییر طراحی فهرست‌های فشرده (همان «نیازمند تصمیم» گزارش قبلی) |
| لینک‌های متنی ۱۸–۲۱px داخل breadcrumb/پاورقی | لینک درون‌متنی از استثنای WCAG 2.5.8 است |
| pop روی `.chip.on` | چیپ‌های فیلتر در events با هر تغییر دوباره رندر می‌شوند و pop همگانی آزاردهنده می‌شد؛ فقط گذار نرم |
| ripple/موج روی همهٔ دکمه‌ها | طبق درخواست انجام نشد؛ press + درخشش کنترل‌شده |
| `nora.css` هنوز چند اندازهٔ آیکون را روی `.btn .i` بازتعریف می‌کند (۲۰ به‌جای ۱۹) | رفتار فعلی صفحه‌های nora است؛ تغییرش تأثیر چیدمانی گسترده دارد و ارزش ریسکش را نداشت |
| ممیزی چشمی کامل همهٔ تصاویر ۷۶۸/۱۴۴۰ | سنجه‌های خودکار (سرریز، خطا، ارجاع شکسته) در همهٔ ۱۳۳ ترکیب صفر بود؛ بازبینی چشمی روی برش‌های مقایسه انجام شد نه تک‌تک تصاویر |

---

## ۹. فایل‌های تغییریافته و کامیت‌ها

- **`0600891`** — آیکون‌ها: ۱۷ فایل HTML (اسپرایت‌ها، نمادهای افزوده، کلید تم، نسخه‌های کش)، `icons.svg`، `sw.js`، سه فایل تست (پین نسخه). (دکمه‌های بنر `home.html` هم در همین کامیت رفت چون همان فایل بود.)
- **`a1b6229`** — لایهٔ تعامل: `glass.css`, `nora.css`, `login.css`, `ui.js`, `login.js`, `account.js`, `post.test.mjs`, `admin.test.mjs`.
- کامیت گزارش/شواهد: هش در پاسخ نهایی.
- هیچ وابستگی تازه، هیچ تغییر در API/مدل داده/احراز هویت/مسیرها؛ همه فقط روی `arena/840de336-strix`؛ PR #1 باز.
