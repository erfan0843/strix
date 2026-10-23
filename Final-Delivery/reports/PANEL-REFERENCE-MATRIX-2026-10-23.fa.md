# ممیزی جامع پنل مدیران بر پایهٔ نسخهٔ مرجع — ماتریس حقیقت فعلی (۱۴۰۵/۰۸/۰۱ – 2026-10-23)

## ۰. مبنا
- شاخه: `arena/840de336-strix` · HEAD واقعی هنگام شروع این ممیزی: **`4934934`** (محلی = ریموت؛ `git ls-remote` تأیید شد؛ درخت کار تمیز؛ `.arena/` خارج از Git).
- نسخهٔ طراحی مرجع: `Final-Delivery/website/nora-ui-docs-base/` (`admin.js` ۶۳۱۴ خط، `admin-arch.md`، `data.js`) — مبتنی بر `data.js`/`localStorage`.
- نسخهٔ اجرایی: `Final-Delivery/website/nora-ui/` (`admin.js` ۱۱۵۶۱ خط، `owner-api.js`، `backend/app.py` + ماژول‌ها).
- گزارش‌های پیشین که این سند آن‌ها را جمع‌بندی و اصلاح می‌کند: `PANEL-RESTORE-MATRIX-2026-10-22` (۱۰۹ ردیف)، `OWNER-PANEL-FROM-ZERO-AUDIT-2026-10-22`، `OWNER-PANEL-COMPLETION-STAGES-2026-10-22` (H1، انتخاب‌گرها، U4/U5، `forms.ev`).
- روش: هر ردیف با `grep`/خواندن تابع در هر دو نسخه، و برای وضعیت «کامل» فقط وقتی سه چیز جدا ثبت شده باشد: **در کد هست** / **آزمون سبز** / **در مرورگر روی DB آزمایشی کار کرد**. ستون «آزمون و شاهد» این سه را جدا می‌نویسد؛ «کد» ≠ «آزمون» ≠ «مرورگر».

### تناقض‌های ماتریس ۱۰۹ ردیفی که با کد حل شد
| ردیف قدیمی | وضعیت در ماتریس ۱۰۹ | واقعیت کد در `4934934` | شاهد |
|---|---|---|---|
| H1 (ویرایشگر افراد) | «بک‌اند آماده / رابط در انتظار» | **کامل**: `PE_SRV`/`pe*` در تنظیمات → «استادان و افراد سایت»، روی `GET/PATCH /api/owner/site-content` با CSRF و `expected_version`؛ نگهبان `reference_in_use` سروری | `ead537c`, `cddae96`; jsdom بلوک H1؛ مرورگر `h1-people-editor-check.json` ۸/۸ |
| H4 (اتصال مدرس به رویداد) | «کامل (متنی)؛ ارجاع ساخت‌یافته نیازمند تصمیم» | **کامل و شناسه‌محور**: انتخاب‌گر `PK` برای `tchr`/`partnerId` (رویداد) و `tchr` (مطلب)، فقط از `GET /api/public/site-content`؛ سرور B1 `unknown_reference` | `621715d`, `dd06974`; مرورگر `stage2-pickers-check.json` |
| E15 (دوره‌ها/مدرس‌ها) | «وابسته به H1» | با H1 + انتخاب‌گر بسته شد؛ «برنامهٔ بعدی» کارت استاد در صفحهٔ عمومی از همان `tchr` حل می‌شود | همان |
| U4 / U5 | «بک‌اند آماده / رابط در انتظار» | **کامل**: زبانه‌های پروندهٔ کاربر روی `…/registrations[/{id}]` و `…/notifications` | `b438021`; مرورگر `stage3-user-file-check.json` |
| B1 و «باقی‌ماندهٔ `forms.ev`» | باز | **بسته**: `_require_known_form_event` در `POST/PUT /api/forms` (۴۲۲ `unknown_reference` فیلد `ev`؛ استثنا: خالی، شناسهٔ کهنهٔ ذخیره‌شده، فرم خرید) | `a82f422`; pytest قرمز→سبز |
| D12 (بخش‌های `reports/money/club` در ناوبری) | P2 «تصمیم» | ناوبری سروری ۵ بخش است (`data.js` `menu` ۴ + داشبورد)؛ `S.sec='reports'` از `secOf` به «کاربران» نگاشت می‌شود ولی `serverBody` برای `reports/money/club` «API متصل نشده» می‌دهد — **مسیر مرده‌ی داخلی** (از منو قابل‌رسیدن نیست، از حافظهٔ مرورگر هست) | `admin.js` L9457–9465 |
| شمارش «۷۷ / ۴ / ۲۸» | — | ردیف‌های «در انتظار» (U4, U5, H1, E15) بسته شدند → با همان مبنا **۸۱ کامل / ۰ در انتظار / ۲۸ مسدود = ۱۰۹**؛ اما این سند مبنای تازه‌ای با ریزقابلیت‌های بیشتر می‌سازد (بخش ۲) و عدد ۱۰۹ دیگر مرجع نیست | — |

### خلاصهٔ یک‌نگاهی ساختار
| محور | طراحی مرجع | اجرایی در `4934934` |
|---|---|---|
| بخش‌های ناوبری | داشبورد، تعریف جدید، رویدادها و مطالب، کاربران، فرم‌ها، گزارش‌ها، تنظیمات (+ مالی/باشگاه در سند اولیه) | داشبورد، رویدادها و مطالب، کاربران، فرم‌ها، تنظیمات؛ گزارش‌ها زیر «کاربران»؛ باشگاه زیر «کاربران»؛ مالی پراکنده (کارتابل/سفارش‌ها/گزارش) |
| منبع داده | `data.js` + `localStorage` | API هم‌مبدأ؛ نماهای طراحی فقط پشت `IS_TEST` |
| مجوز | `canSec/canPerm` محلی از `data.js` | `permissions` نشست از `/api/auth/me` یا `/api/account/me`؛ هر endpoint با `require_*` سروری (`roles.py`) |
| چیزهایی که اجرایی **بهتر** از طراحی دارد | — | قفل نسخه (409)، تأیید پیش از انتشار/توقف/بایگانی، CSRF، حسابرسی، CSV واقعی، ماسک PII سروری، نگهبان ارجاع‌ها |

---

## ۱. ماتریس کامل (بر پایهٔ بخش‌های مرحلهٔ دو: A تا H)

ستون «وضعیت»: **کامل** (کد + آزمون + مرورگر) · **کامل‌ـ‌آزمون** (کد + آزمون؛ مرورگر ندارد) · **ناقص** (بخشی) · **غایب** · **نمایشی** (فقط `data.js`/`localStorage`، در مسیر واقعی رندر نمی‌شود) · **خراب** · **مسدود** (نیازمند تصمیم/مدل/سرویس).
ستون «مجوز» = مجوز و **محل اعمال در سرور** (تابع `require_*`؛ رابط فقط خوانایی).

### A. ساختار کلی، ناوبری و داشبورد

| # | قابلیت طراحی | مسیر/رفتار مرجع | وضعیت | فایل/تابع فعلی | API / مدل | مجوز (سرور) | آزمون · شاهد | اختلاف با مرجع | اقدام / اولویت / معیار پذیرش |
|---|---|---|---|---|---|---|---|---|---|
| A1 | ریل دسکتاپ + نوار پایین موبایل + قفل بخش بی‌مجوز | هر بخش قفل‌دار با پیام | کامل | `renderNav`, `canSec` L269 | نقش نشست | `canSec` از `permissions` سروری؛ endpointها جدا | admin.test, admin-rbac · مرورگر: ممیزی ۲۲ مهر | ۵ بخش به‌جای ۷ | حفظ؛ «گزارش‌ها» به‌عنوان بخش ناوبری: تصمیم (A8) |
| A2 | نوار بالا: نام بخش، نقش، ساعت، وضعیت API، خروج | ✓ | کامل | `renderTop`, چیپ `data-preview-badge` | `/api/auth/me`, `/api/account/me`, `/api/health` | — | admin.test · مرورگر | چیپ سلامت «فعال نیست» برای سرویس پیکربندی‌نشده (B9 قدیمی) | A-P2: تمایز «پیکربندی‌نشده» از «خراب» |
| A3 | داشبورد: سرصفحهٔ تاریخ جلالی + ساعت + «مهلت‌ها از سرور» | ✓ | کامل | `serverDashboard` | — | — | admin-restore · `02-dash-*.png` | — | حفظ |
| A4 | KPIها | چهار عدد با درصد تغییر | ناقص | `serverDashboardKpis` | `GET /api/admin/reports/summary?period` | `rp_view` (`require_any_permission`) | admin-phase2/3 | بدون «درصد تغییر نسبت به دورهٔ قبل» (API سری زمانی ندارد) | مسدود جزئی: نیازمند endpoint مقایسهٔ دوره؛ ثبت در «تصمیم‌ها» |
| A5 | کارهای در انتظار (کارتابل، پرسش‌های بی‌پاسخ، سفارش‌ها، اعلان‌های ناموفق) | `cardQueue` با سقف | کامل | `dashx*` (`data-dashx-queue`) | `inbox`, `event-interaction/summary`, `recordings/summary`, `notifications?state=failed` | هر API مجوز خودش | admin-restore · مرورگر | — | حفظ |
| A6 | رویدادهای نزدیک با ظرفیت | ✓ | کامل | `data-dashx-upcoming` | `content/events?status=published&sort=date` | `ev_create`/`ev_publish` | admin-restore | ظرفیت/ثبت‌نام‌شده روی کارت نیست (شمار ثبت‌نام از API فرم می‌آید) | A-P2: نمایش «ظرفیت فرم» وقتی `registration` در detail هست |
| A7 | انتشار زمان‌بندی‌شده + اجرای دستی | — | **کامل** | `data-dashx-sched`, `runServerSched` با `confirm` | `scheduled-publish`, `POST …/run` | `ev_publish` | کد `ea95403` · آزمون admin.test/restore سبز · مرورگر `evidence/panel-reference-2026-10-23/stage-ab-results.json` (A7: تأیید/انصراف بدون POST؛ بدون تصویر جدا) | — | بسته |
| A8 | بخش‌های `reports` / `money` / `club` | در طراحی اولیه بخش ناوبری بودند | **کامل (مسیرهای نام‌دار)** | `serverHashRoute`/`serverHashAfterRender` | — | `canSec` همان مقصد | کد `ea95403` · آزمون admin.test سبز · مرورگر `evidence/panel-reference-2026-10-23/A8-money-orders.png`, `A8-club.png` + `stage-ab-results.json` (`#att`، `#reports`) | هیچ `sec` ذخیره‌شده‌ای به «متصل نشده» نمی‌رسد | بسته |
| A9 | نقشهٔ امکانات پنل | — | کامل | `panelModuleMapView` | — | — | admin-restore | — | حفظ؛ باید با این ماتریس هم‌خوان بماند |
| A10 | خط زمانی مالک (audit) | `cardFeed` | کامل | `data-dashx-audit` | `/api/owner/audit` | `require_owner` | pytest audit | — | حفظ |
| A11 | سلامت سامانه | `cardStatus` | کامل | `serverHealthView` | `/api/health`, `storage/health` | — | admin.test | — | حفظ |
| A12 | حوزه‌ها/تیم/کارنامهٔ هفته/تعریف‌های تازه | `cardFields/cardTeam/cardWeek/cardDefs` | مسدود | — | مدل حوزه/تیم/سری زمانی/صف تعریف در سرور نیست | — | — | — | تصمیم محصول (ساختار حوزه‌ای) |
| A13 | تب‌های داخلی (`S.uV`, `S.uHub`, `S.setG`, `EI.tab`, `UFL.tab`) پایدار در `localStorage` | ✓ | کامل | `save()`/`sanitize` | — | — | admin.test | — | حفظ |
| A14 | حالت‌های بارگذاری/خالی/خطا/تلاش دوباره در هر بلوک داشبورد | — | کامل | `dashx*` | — | — | admin-restore | — | حفظ |

### B. رویدادها و محتوا

| # | قابلیت طراحی | مسیر/رفتار مرجع | وضعیت | فایل/تابع | API / مدل | مجوز (سرور) | آزمون · شاهد | اختلاف | اقدام / اولویت / معیار |
|---|---|---|---|---|---|---|---|---|---|
| B1 | فهرست رویدادها: جست‌وجو، فیلتر وضعیت، ترتیب، صفحه‌بندی | صافی همه/جاری/پیش‌رو/گذشته | **کامل** | `ctList` (چیپ‌های `[data-ct-when]` + «امروزِ سرور») | `GET /api/admin/content/events?when=today|upcoming|past` (سطل‌بندی روی روز شمسی تهران در سرور: `content_admin.event_time_bucket`؛ پاسخ `when_counts`/`today`؛ `when` روی مطالب یا مقدار ناشناخته → ۴۲۲) | `ev_create`/`ev_publish` (`_CONTENT_*_PERMS`؛ بی‌نشست ۴۰۱) | کد این شاخه · pytest `test_events_time_filter_is_judged_on_the_server_calendar_day` + admin-phase2 (B1) · مرورگر `evidence/panel-reference-2026-10-23/B1-when-past.png`, `B1-when-upcoming-draft.png`, `B1-when-mobile.png`, `stage-b1-results.json` (۱۲/۱۲) | — (رویداد بدون تاریخ قابل‌تشخیص در هیچ سطل زمانی نمی‌آید و شمارش جدا دارد) | بسته |
| B2 | ساخت/ویرایش رویداد (همهٔ فیلدها) | ویزارد ۵ گامی با ۹ قالب | **کامل (فرم تک‌صفحه‌ای + ۶ قالب شروع)** | `ctEditor`, `CT_TEMPLATES`, `ctApplyTemplate` | `POST/PUT content/events` با `expected_version` | `ev_create` | کد `e859c0a`+`b45e4ba` · آزمون admin-phase2 (بخش B) سبز · مرورگر `evidence/panel-reference-2026-10-23/stage-ab-results.json` (B2؛ بدون تصویر جدا) | قالب فقط فیلدهای خالی را پر می‌کند؛ بدون ذخیرهٔ خودکار | بسته (ویزارد چندگامی عمداً نه) |
| B3 | اعتبارسنجی فیلدی و فوکوس روی اولین خطا | خطای کنار فیلد + پرش | **کامل** | `ctFocusFirstError` | 422 `detail.field` | — | کد `e859c0a` · آزمون admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/B3-focus-error.png` (فوکوس `#ctf_t`) | — | بسته |
| B4 | قفل نسخه ۴۰۹ با حفظ نوشته | ✓ | کامل | `ctSave` | 409 | — | admin-phase2 · مرورگر `stage2-05` | — | حفظ |
| B5 | چرخهٔ وضعیت با تأیید | ✓ | کامل | `ctSetStatus` | `POST …/status` | `ev_publish` | pytest · مرورگر | — | حفظ |
| B6 | پیش‌نمایش زندهٔ کارت | کارت + صفحه | کامل | `ctPreview` | — | — | · مرورگر | پیش‌نمایش صفحهٔ کامل نیست | B-P2: پیوند «صفحهٔ عمومی» برای منتشرشده هست (`eiHeader`); کافی |
| B7 | تاریخ شمسی: تقویم، روز هفته خودکار، همگام‌سازی `on`↔`startsAt`، پایان همراه شروع | ✓ (`dpBox`, `jcal`) | **کامل** | `ctWeekday`, `ctSyncDates`, تقویم `[data-ctdp]` | — | — | کد `e859c0a`+`b45e4ba` · آزمون admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/B7-calendar.png`, `B7-calendar-mobile.png` + `stage-ab-results.json` | — | بسته |
| B8 | ساعت ۲۴ با دونقطهٔ خودکار، مدت خودکار | ✓ | **کامل (دونقطه)** | `ctTimeFix` (۴ رقم زنده / ناقص‌ها در blur) | — | — | کد `e859c0a`+`b45e4ba` · آزمون admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/stage-ab-results.json` (B8: `1030`→`10:30`؛ بدون تصویر جدا) | «مدت خودکار» نیست (مدل مدت ندارد) | بسته؛ مدت = تصمیم‌نشده (P3) |
| B9 | ردیف جلسه‌ها (هر جلسه تاریخ/ساعت) | `sessRows` | **کامل** | `ctPartsBox`, `ctPartsFrom` | `parts[]` در `EVENT_EDITABLE` (≤۸۰، 422 `invalid_parts`) | `ev_create` | کد `8040cea`+`e859c0a` · آزمون pytest `test_event_parts_*` + admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/B9-parts-editor.png`, `B9-public-event.png` | — | بسته |
| B10 | ظرفیت/قیمت | ✓ | کامل | `cap`, `price` | — | — | pytest | ظرفیت رویداد ≠ ظرفیت فرم (تصمیم ۸) | ثبت تصمیم |
| B11 | مدرس/نهاد همکار با شناسه | چیپ‌های `data-wtchr`, ساخت درجا | کامل | `PK`/`ctPicker` | `GET /api/public/site-content`; B1 سروری | `ev_create` + `unknown_reference` در `build_record` | jsdom مرحلهٔ ۲ · مرورگر `stage2-*` | «ساخت درجا» نیست؛ میان‌بر به ویرایشگر افراد (فقط مالک) هست | B-P2: ساخت درجا = ناوبری به H1 با بازگشت؛ قابل قبول |
| B12 | فرم ثبت‌نام متصل از ویرایشگر | برگهٔ انتخاب از انبار + «ساختن در فرم‌ساز» | کامل | `ctEventForms`, `create.html?ev=` | `GET /api/forms`; `forms.ev` سروری | `fm_create` | admin-phase2 (B4) · مرورگر `fix-b4-*` | «انتخاب فرم موجود از برگه» نیست؛ فرم با `ev` خودش وصل می‌شود | B-P2: کافی (فرم خود `ev` را دارد) |
| B13 | ثبت‌نام‌کنندگان/حضور/گواهی از پروندهٔ رویداد | تب‌های `reg/att/cert` | کامل | `eiHeader` `data-ei-jump-attendance/cert` | `attendance/forms?q=`, `certificates?event=` | `attendance`, `certificate` | admin-restore · مرورگر `08-ei-*` | پرش به بخش کاربران به‌جای تب درجا | حفظ |
| B14 | منابع/ضبط/پرسش/دیدگاه/گزارش/سفارش | تب‌های `media/news/survey/money` | کامل | `EI`, `REC` | `/api/admin/events/{id}/*` | `ev_create`/`ev_publish`/`receipt_approve` | pytest EI/REC · مرورگر | نظرسنجی مدل ندارد؛ «اطلاع‌رسانی دستی» endpoint ندارد | مسدود (تصمیم ۳) |
| B15 | پوستر: آپلود/URL | گالری + تم کارت | کامل | `CM` | `POST /api/admin/media` | `pr_media`/`ev_create` | admin-phase3 · مرورگر | گالری/تم نیست | B-P2 |
| B16 | کپی/تکثیر رویداد | `copyev` | **کامل** | `[data-ct-dup]` → `ctBlank` پر، بدون id/وضعیت/تاریخ | همان POST | `ev_create` | کد `e859c0a` · آزمون admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/B16-duplicate.png` | — | بسته |
| B17 | پیش‌نویس محلی هنگام تایپ | `S.wiz` در `localStorage` | **کامل** | `ctDraftSave`/`ctDraftBanner` در `sessionStorage` با کلید حساب+رکورد | — | — | کد `e859c0a` · آزمون admin-phase2 سبز · مرورگر `evidence/panel-reference-2026-10-23/B17-draft-banner.png` | هرگز به‌جای دادهٔ سرور نشان داده نمی‌شود | بسته |
| B18 | تاریخچهٔ نسخه‌ها | `S.evHist` | مسدود | — | سرور فقط `version/updated_at`؛ حسابرسی `content.*` در audit | — | — | — | تصمیم: جدول تاریخچه |
| B19 | یادآورها (بله/پیامک) | `remRows` | مسدود | — | مدل/زمان‌بند/سرویس نیست | — | — | — | تصمیم ۳ |
| B20 | مطالب: فهرست، ویرایشگر، نویسندهٔ پروفایلی + میهمان، دسته، تصویر، وضعیت، **بدنهٔ بلوکی** | ویرایشگر بلوکی دوگامی | **کامل (بلوک‌های p/h/q/img/ul/ol/box/hr)** | `ctBlocksBox`, `ctBlocksFrom`, `ctBlocksPayload`; عمومی `post.html` + `public-data.js` | `blocks` در `ARTICLE_EDITABLE` (422 `invalid_blocks`/`invalid_image`؛ `body` از بلوک‌های p مشتق) | `ev_create` | کد `01fe58a`+`57de428` · آزمون pytest `test_article_blocks_*` + admin-phase2 (B20) + post/smoke سبز · مرورگر `evidence/panel-reference-2026-10-23/B20-block-editor.png`, `B20-public-post.png`, `stage-b20-results.json` (۷/۷) | **نقص یافت‌شده در مرورگر و رفع‌شده:** مطلب body-فقط در حالت سرور بدنهٔ خالی داشت؛ فهرست‌های `ul/ol` در `public-data.js` رشته می‌شدند. ویدیو/صدا/فایل/پیوند بیرونی عمداً نیست (نیازمند تصمیم منبع معتبر) | بسته؛ رسانهٔ ویدیویی = تصمیم مالک |
| B21 | پیش‌نمایش مطلب در `post.html` پیش از انتشار | ✓ | ناقص | پیش‌نمایش کارت در ویرایشگر | صفحهٔ عمومی فقط منتشرشده | — | — | پیش‌نویس در `post.html` دیده نمی‌شود | B-P2: پیش‌نمایش سروری نیازمند endpoint پیش‌نمایش مالک؛ تصمیم |
| B22 | برچسب‌ها/دسته‌ها/تقویم/قالب مطلب/دکمه‌های خانه (`skdevView`) | ✓ | نمایشی | — | مدل پیکربندی سایت نیست | مالک | — | — | مسدود (خارج از v1) |
| B23 | رسانه‌ها: فهرست با وضعیت استفاده | — | کامل | `cmPanel` | `GET /api/admin/media` | `pr_media` | admin-phase3 | — | حفظ |

### C. کاربران

| # | قابلیت | مرجع | وضعیت | فایل/تابع | API / مدل | مجوز (سرور) | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|---|
| C1 | فهرست: جست‌وجو، فیلتر ورود/نقش، صفحه‌بندی | ۴ کاشی + فیلتر وضعیت/برچسب | کامل | `serverUsersList` | `GET /api/admin/users` | `us_view` | admin-phase2 · مرورگر | فیلتر «وضعیت/برچسب» مدل ندارد | مسدود جزئی (تصمیم ۲) |
| C2 | پروندهٔ کاربر: اطلاعات/هویت‌ها/نقش | تب اطلاعات | کامل | `serverUserDetail` | `GET /api/admin/users/{id}` | `us_view`; ایمیل فقط مالک (سرور) | admin-phase2 · مرورگر | — | حفظ |
| C3 | ثبت‌نام‌ها + جزئیات پاسخ (ماسک، همراهان، فیش، حضور، مالی با مجوز) | تب رویدادها و فرم‌ها | کامل | `UFL`/`uf*` | `…/registrations[/{id}]` | `us_view`; `finance` فقط روی پاسخ سرور | jsdom مرحلهٔ ۳ · مرورگر `stage3-*` (ثبت‌نام رایگان؛ پولی فقط jsdom+pytest) | — | مرورگر با ثبت‌نام پولی: C-P2 (نیازمند دادهٔ آزمایشی) |
| C4 | اعلان‌های همان حساب | تب پیام‌ها | کامل | `UFL` notifs | `…/notifications` | `us_view` | jsdom · مرورگر | — | حفظ |
| C5 | تاریخچهٔ حساب (audit) | تب تاریخچه | **کامل (مالک)** | زبانهٔ `hist` در `ufPane` → `ufLoadHist` (فقط `isOwner()`؛ فراخوانی تنبل هنگام باز کردن زبانه) | `GET /api/owner/audit?target_type=account&target_id=` (فیلتر دقیق سمت سرور؛ `target_id` با الگوی محدود، ۴۲۲ روی ورودی بد) | `require_owner` سرور + زبانه فقط برای مالک | کد `43e5150` · آزمون pytest `test_admin_audit_trail` (مجاز/ناموجود/ورودی بد) + admin-phase2 (مالک: خطا→تلاش دوباره→۲ ردیف→خالی؛ مدیر: بدون زبانه و بدون تماس با `/api/owner/*`) سبز · مرورگر `evidence/panel-reference-2026-10-23/C5-account-history.png`, `C5-manager-no-history-tab.png`, `stage-c5-results.json` (۱۱/۱۱: مدیر ۴۰۱، بی‌نشست ۴۰۱) | ادعای قبلی «پیوند audit با فیلتر» نادرست بود: API پارامتر `target` نداشت؛ اکنون افزوده شد. فقط ردیف‌هایی که هدفشان همین حساب است (نقش/ورود مدیر) | بسته |
| C6 | امتیاز باشگاه از پرونده | تب باشگاه | کامل (فقط‌خواندنی) | `[data-user-club-points]` | `club/points/members/{id}` | `cl_member` | pytest · مرورگر | — | حفظ |
| C7 | درخواست‌ها (کارتابل) | کاشی درخواست‌ها | کامل | `sharedWorkflowInboxView` | `inbox`, `decision` | `us_approve`/`receipt_approve` | pytest workflows · مرورگر | — | حفظ |
| C8 | حضور و غیاب | کاشی | کامل | `serverAttendanceView` | `attendance/*` | `attendance` | pytest · مرورگر | — | حفظ |
| C9 | گواهینامه‌ها | کاشی | کامل | `serverCertView` | `certificates`, `issue` | `certificate` | pytest · مرورگر | ابطال از پنل نیست (قاعده: منبع ربات) | مسدود |
| C10 | نقش‌ها و اعتبارنامهٔ مدیر | ابزار staff | کامل | `cUServerStaff` | `/api/owner/accounts/*` | `require_owner` | admin-rbac, pytest · مرورگر (چرخش واقعی ۲۲ مهر) | — | حفظ |
| C11 | برچسب/یادداشت/مسدود/والد/افزودن دستی/اکسل | ۵ زیرابزار | مسدود | `SERVER_TOOL_BLOCKED` با دلیل | مدل نیست | — | مرورگر `12-tools-*` | — | تصمیم ۲ |
| C12 | آزمون منفی: شناسهٔ حساب دیگر، پاسخ حساب دیگر، نشت مالی | — | کامل‌ـ‌آزمون + مرورگر | — | ۴۰۴ داخل scope | سرور | pytest `test_admin_user_file_api`, jsdom · مرورگر `stage3` گام ۵ | — | حفظ |

### D. فرم‌ساز

| # | قابلیت | مرجع | وضعیت | فایل/تابع | API | مجوز (سرور) | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|---|
| D1 | فهرست فرم‌ها داخل پنل + وضعیت + پیوندها | `vForms` | کامل | `serverFormsView` | `GET /api/forms` | `fm_create`/`fm_responses` | admin-restore · مرورگر `13-forms-*` | — | حفظ |
| D2 | ساخت/ویرایش در `create.html` با `?ev=` | ✓ | کامل | `create.html` | `POST/PUT /api/forms` | `fm_create`; مالی `finance` | pytest · مرورگر `fix-b4-create-prefilled` | — | حفظ |
| D3 | اعتبارسنجی `ev` سروری | — | **کامل** | `_require_known_form_event`; `create.html` پیام فارسی برای 422 `unknown_reference`/`ev` | 422 `unknown_reference` | سرور | کد `a82f422`+`f24522e` · آزمون pytest سبز · مرورگر `evidence/panel-reference-2026-10-23/D3-unknown-ev-422.png`, `stage-d-results.json` (پیام فارسی، چیزی ذخیره نشد، متن تایپ‌شده ماند) | — | بسته |
| D4 | پاسخ‌ها، جزئیات، CSV | `builder.html` | کامل | `builder.html` | `/responses[?format=csv]` | `fm_responses`, `fm_export`, `finance` | pytest, شواهد `panel-restore/` | xlsx → 422 صادقانه | حفظ |
| D5 | ظرفیت/صف انتظار/همراهان/بلیت/پرداخت/فیش | ✓ | کامل | فرم‌ساز + `form.html` | مدل فرم | — | pytest فازهای ۷–۹ | — | حفظ |
| D6 | انتخاب رویداد از فهرست سروری داخل فرم‌ساز | برگهٔ انتخاب رویداد | **کامل** | `#evPickBox` در `create.html` (`evPickLoad`/`renderEvPick`؛ جست‌وجوی فارسی، Enter، قطع اتصال، قفل برای فرم منتشرشده) | `GET /api/admin/content/events` (۴۰۱/۴۰۳ → `GET /api/public/site-content` فقط منتشرشده‌ها) | `ev_create` یا عمومی | کد `f24522e` · آزمون خودکار: `builder-event-picker.test.mjs` ۲۸/۲۸ · مرورگر `evidence/panel-reference-2026-10-23/D6-picker-open.png`, `D6-picked.png`, `D6-saved.png`, `stage-d-results.json` (۱۱/۱۱؛ `ev` در بدنهٔ `POST /api/forms`) | — (فوکوس قلم جست‌وجو هنگام بازنویسی فهرست از دست می‌رفت → رفع شد) | بسته |
| D7 | وبهوک/گردش کار پیشرفته | ✓ | مسدود | — | مدل نیست | — | — | — | تصمیم |

### E. کارتابل و اعلان‌ها

| # | قابلیت | وضعیت | فایل/تابع | API | مجوز (سرور) | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|
| E1 | کارتابل پروفایل/فیش با تصمیم + دلیل الزامی رد/فیش + فایل | کامل | `sharedWorkflowInboxView` | `inbox`, `files`, `decision` | `us_approve`/`receipt_approve` سروری | pytest · مرورگر | — | حفظ |
| E2 | پرسش‌ها/گزارش‌های باز همهٔ رویدادها | کامل | `EI.all` | `event-questions`, `event-reports` | `ev_publish` | pytest | — | حفظ |
| E3 | صندوق خروجی: وضعیت/تلاش دوباره/خطا/فیلتر | کامل | `vServerOutbox` | `notifications`, `retry` | `rp_view`/`bc_send`? (بررسی) | pytest · مرورگر | — | E-P2: تأیید مجوز `retry` در کد |
| E4 | ارسال دستی/گروهی، قالب اعلان | مسدود | — | endpoint ندارد | — | — | — | نساختن بدون endpoint+مجوز+حد+حسابرسی (قاعدهٔ مأموریت) |

### F. گزارش، مالی، حضور، گواهینامه

| # | قابلیت | وضعیت | فایل/تابع | API | مجوز | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|
| F1 | گزارش دوره‌ای با منبع و بازه | کامل | `vServerReports` | `reports/summary?period` | `rp_view` | pytest · مرورگر | ۹ گزارش تخصصی طراحی نیست؛ نمودار نیست | F-P2: نمودار میله‌ای سادهٔ CSS از همان داده (بدون سری زمانی جعلی) |
| F2 | مالی: مبلغ/رسید/بازپرداخت فقط با `finance` | کامل | `REC`, کارتابل | `recording-orders`, `refund` | `finance` سروری | pytest · مرورگر (prompt رد شد) | — | حفظ |
| F3 | حضور | کامل | `serverAttendanceView` | `attendance/*` | `attendance` | pytest · مرورگر | — | حفظ |
| F4 | گواهی: فهرست/فیلتر/صدور دستی با دلیل | کامل | `serverCertView` | `certificates`, `issue` | `certificate` | pytest · مرورگر | صدور خودکار/قالب در ربات | حفظ |
| F5 | خروجی اکسل هفت‌شیتی / گزارش زمان‌بندی‌شده | مسدود | — | — | — | — | — | تصمیم |

### G. استادان و محتوای عمومی

| # | قابلیت | وضعیت | فایل/تابع | API | مجوز | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|
| G1 | فهرست سروری افراد: جست‌وجو، ویرایش، ترتیب، پیش‌نمایش، انتشار با تأیید، ۴۰۹، ردیف ردشده، **عکس** | کامل | `PE_SRV`; عکس: `[data-ppfile]` → `api.uploadAdminMedia` در حالت سرور | `GET/PATCH /api/owner/site-content` + `POST /api/admin/media` (نشانی `/api/public/media/…` در `photo`؛ بدون base64) | `require_owner` + CSRF | کد `d22a431` · آزمون admin-phase3 (G1: فایل غیرتصویری رد، POST با CSRF، نشانی پایدار، بدون PATCH خودکار) سبز · مرورگر `evidence/panel-reference-2026-10-23/G1-person-photo-upload.png`, `stage-g1-results.json` (۶/۶) | «رونوشت از پروفایل» هنوز نیست | عکس بسته؛ رونوشت P2 |
| G2 | نهادهای همکار | کامل | `PP_SRV` | همان | مالک | pytest retention · مرورگر | — | حفظ |
| G3 | انتخاب در رویداد/مطلب با جست‌وجوی فارسی و Enter | کامل | `PK` | `GET /api/public/site-content` | — | jsdom · مرورگر | — | حفظ |
| G4 | مدیران (صفحهٔ پشتیبانی) | نمایشی | — | `nora-managers` فقط `localStorage` در طراحی؛ سرور ندارد | — | — | — | مسدود (تصمیم: مدل «تیم پشتیبانی») |

### H. تنظیمات و امنیت

| # | قابلیت | وضعیت | فایل/تابع | API | مجوز | آزمون · شاهد | اختلاف | اقدام |
|---|---|---|---|---|---|---|---|---|
| H1 | سرویس‌ها (ذخیرهٔ پوشیده، خالی پاک نمی‌کند، آزمون اتصال) | کامل (ذخیره) / تأییدنشده (اتصال واقعی) | `servicesSettingsView` | `service-settings` | `require_owner` | pytest · مرورگر | — | حفظ |
| H2 | دامنه/راه‌اندازی، داده/پشتیبان، سلامت | کامل | `deploy/data/perf` | `health`, `owner/data/*` | مالک | مرورگر | — | حفظ |
| H3 | نقش‌ها/مجوزها/حساب‌ها/ثبت عملیات | کامل | `security*`, `serverAuditView` | `owner/accounts`, `owner/audit` | مالک | pytest, admin-rbac | — | حفظ |
| H4 | انتشار محتوا (بنرها، همکاران، افراد) | کامل | `publishing`, `people` | site-content | مالک | — | — | حفظ |
| H5 | پوسته/فرم‌ساز/باشگاه کتاب/چت پشتیبانی (کاشی‌های طراحی) | نمایشی/مسدود | — | مدل نیست | — | — | — | تصمیم (خارج از v1) |
| H6 | اعتبارنامه در log/گزارش/Git | کامل | `secret_box`, ماسک | — | — | grep در شواهد | — | حفظ (grep مجدد در پایان) |

### هوش مصنوعی داخلی
- در طراحی و تاریخچه: **وجود ندارد** (`grep -ri` برای `هوش مصنوعی|openai|anthropic|llm|gpt|embedding` در `Final-Delivery/` و `git log --all --grep` → تنها دو برخورد غیرمرتبط: جملهٔ «از SDK هوش مصنوعی استفاده نمی‌کند» در `QUALITY-VALIDATION.md` و واژهٔ `embedding` ویدیو در `video_sources.py`؛ «جمع‌بندی خودنویس» = قالب شمارنده‌ای `rpSummary`، «دستیار نورا» = متن ثابت `support.js`).
- هیچ دکمه یا پاسخ ثابتی AI جا زده نمی‌شود. پیش‌نیاز پیاده‌سازی واقعی (تصمیم مالک): مدل محلی (CPU، بدون خروج داده) یا API ابری؛ دامنهٔ اول فقط پیش‌نویس توضیح رویداد/خلاصهٔ گزارش؛ endpoint فقط مالک با حد نرخ و audit بدون متن کاربران؛ ورودی فقط محتوای عمومی خود مالک، هرگز `form_responses`/فیش/اعلان شخصی.

---

## ۲. برنامهٔ اجرا (ترتیب وابستگی) و معیار اتمام
A (A8 مسیرهای مردهٔ `reports/money/club`, A7 تأیید اجرای دستی, A2 چیپ سلامت) → B (B3 فوکوس خطا, B8 ساعت, B7 تاریخ/روز هفته/همگام‌سازی, B16 تکثیر, B17 پیش‌نویس محلی, B9 جلسه‌ها اگر مدل اجازه دهد, B2 قالب‌ها) → C (C5 بررسی زبانهٔ تاریخچه) → D (D3 مرورگر `create.html` با ۴۲۲, D6 انتخاب‌گر رویداد) → E (E3 بسته: مجوز retry = `ev_publish` نوشتنی) → F (F1 نمودار ساده) → G (G1 عکس با media) → H (grep نهایی). هر بخش: کامیت کوچک + آزمون jsdom/pytest + مرورگر روی DB آزمایشی + به‌روزرسانی همین سند (بخش ۳).

## ۳. وضعیت اجرا (به‌روزشده تا `43e5150` — 2026-10-23)

سه سطح جدا برای هر مورد: **کد** (کامیت) / **آزمون خودکار** (suite و نتیجهٔ واقعی) / **مرورگر** (کرومیوم روی سرور آزمایشی `127.0.0.1:8000` با DB آزمایشی `/home/user/nora-preview`؛ شواهد در `evidence/panel-reference-2026-10-23/`). «—» یعنی انجام نشده و ادعایی هم نیست.

| ردیف | موضوع | کد | آزمون خودکار | مرورگر |
|---|---|---|---|---|
| A7 | تأیید پیش از اجرای دستی انتشار زمان‌بندی‌شده | `ea95403` | admin.test ۸۱۷/۰، admin-restore ۵۰/۰ | ✓ `stage-ab-results.json` (A7؛ انصراف = بدون POST) |
| A8 | مسیرهای `#money/#club/#att/#reports` به مقصد واقعی مجاز | `ea95403` | admin.test سبز | ✓ `A8-money-orders.png`, `A8-club.png`, `stage-ab-results.json` |
| B2 | قالب‌های شروع رویداد | `e859c0a`, `b45e4ba` | admin-phase2 «قبول» | ✓ `stage-ab-results.json` (B2) |
| B3 | فوکوس روی اولین خطای ۴۲۲ | `e859c0a` | admin-phase2 | ✓ `B3-focus-error.png` |
| B7 | تقویم شمسی، روز هفته، همگام‌سازی تاریخ | `e859c0a`, `b45e4ba` | admin-phase2 | ✓ `B7-calendar.png`, `B7-calendar-mobile.png` |
| B8 | دونقطهٔ خودکار ساعت | `e859c0a`, `b45e4ba` | admin-phase2 | ✓ `stage-ab-results.json` (B8) |
| B9 | جلسه‌ها (`parts`) | `8040cea`, `e859c0a` | pytest content_admin ۱۱ passed؛ admin-phase2 | ✓ `B9-parts-editor.png`, `B9-public-event.png` |
| B16 | تکثیر رویداد | `e859c0a` | admin-phase2 | ✓ `B16-duplicate.png` |
| B17 | پیش‌نویس محلی زبانه | `e859c0a` | admin-phase2 | ✓ `B17-draft-banner.png` |
| B20 | ویرایشگر بلوکی مطلب + نمایش عمومی | `01fe58a`, `57de428` | pytest `test_article_blocks_*`؛ admin-phase2 (B20)؛ post ۱۰۴/۰؛ smoke ۸۰۸/۰ | ✓ `B20-block-editor.png`, `B20-public-post.png` (۷/۷ در `stage-b20-results.json`) |
| C5 | تاریخچهٔ حساب در پروندهٔ کاربر (مالک) | `43e5150` | pytest `test_admin_audit_trail` ۴ passed؛ admin-phase2 (مالک + مدیر) | ✓ `C5-account-history.png`, `C5-manager-no-history-tab.png` (۱۱/۱۱) |
| D3 | پیام فارسی ۴۲۲ `unknown_reference(ev)` در فرم‌ساز | `f24522e` | pytest (سرور) | ✓ `D3-unknown-ev-422.png` |
| D6 | انتخاب‌گر رویداد در فرم‌ساز | `f24522e` | `builder-event-picker.test.mjs` ۲۸/۲۸ (فهرست فقط از API مدیریتی/عمومی، جست‌وجو+Enter، قطع اتصال، خطا/تلاش دوباره، پنهان در فرم خرید، ۴۲۲ `unknown_reference`) | ✓ `D6-picker-open.png`, `D6-picked.png`, `D6-saved.png` (۱۱/۱۱ در `stage-d-results.json`) |
| B1 | صافی زمانی امروز/پیش‌رو/گذشتهٔ فهرست رویدادها (`when`) | این شاخه (پس از `e4a552a`) | pytest content_admin ۱۲ passed · admin-phase2 «قبول» | ✓ `B1-when-past.png`, `B1-when-upcoming-draft.png`, `B1-when-mobile.png`, `stage-b1-results.json` (۱۲/۱۲: روز سرور ۱۴۰۵/۰۸/۰۱، ۳ گذشته/۳ پیش‌رو، ترکیب با وضعیت، ۴۲۲ برای مقدار نامعتبر، مدیر ۲۰۰، بی‌نشست ۴۰۱) |
| G1 | بارگذاری عکس شخص با `POST /api/admin/media` | `d22a431` | admin-phase3 «قبول» | ✓ `G1-person-photo-upload.png`, `stage-g1-results.json` (۶/۶: یک POST ۲۰۱، نشانی پایدار در `photo`، PATCH ۲۰۰، فایل از `/api/public/media/…` با `image/png` سرو شد) |

### نقص‌هایی که فقط در مرورگر پیدا شدند (و رفع شدند)
- `b45e4ba`: `ctTimeFix` هنگام تایپ «۱» کاربر را قفل می‌کرد؛ قالب، پیش‌فرض خالی را رونویسی می‌کرد؛ تقویم روی ماه جاری باز می‌شد نه ماه رویداد.
- `01fe58a`: مطلبِ ساخته‌شده از پنل (فقط `body`) در `post.html` حالت سرور **بدنهٔ خالی** داشت؛ فهرست‌های `ul/ol` در `public-data.js` به رشته تبدیل می‌شدند.
- `43e5150`: ادعای ماتریس قبلی (C5 «کامل») نادرست بود — API فیلتر `target` نداشت.

### رگرسیون اجراشده پس از آخرین تغییر (`43e5150`)
- Node (هر فایل جدا، `timeout 280`): admin.test ۸۱۷/۰ · admin-phase2 قبول · admin-phase3 قبول · admin-rbac قبول · admin-restore ۵۰/۰ · admin-recordings گذشت · asset-audit ۳/۰ · smoke ۸۰۸/۰ · post ۱۰۴/۰ · events-page ۸۹/۰ · support ۱۷۹ · login ۱۰۵/۰ · account ۱۳۴/۰ · builder-purchase و form-purchase سبز · public-data-banner و site-content-sync سبز. (کل ۳۷ فایل یک‌جا اجرا نشد؛ فقط موارد مرتبط.)
- pytest SQLite: `test_content_admin_api` + `test_site_content*` ۲۰ passed؛ `test_admin_audit_trail` ۴ passed. **کل مجموعهٔ pytest پس از `43e5150` اجرا نشده** (آخرین اجرای کامل: تنهٔ `a82f422`، ۳۷۰ passed/۴ skipped).
- mypy: `PASS types` (۷۳ فایل).
- PostgreSQL و ربات: **تأییدنشده** (محیط ندارد).

### باقی‌مانده‌ها به ترتیب اولویت (باگ/مسیر ناقص اول)
1. ~~G1 شاهد مرورگر~~ انجام شد (`stage-g1-results.json`).
2. ~~D6 آزمون jsdom~~ انجام شد (`builder-event-picker.test.mjs`؛ ضمناً اشکال ازدست‌رفتن فوکوس قلم جست‌وجو هنگام بازنویسی فهرست در `create.html` رفع شد).
3. A2 چیپ سلامت «پیکربندی‌نشده» ≠ «خراب»؛ A6 ظرفیت روی کارت رویداد نزدیک؛ ~~B1 صافی زمانی~~ (انجام شد)؛ F1 نمودار CSS؛ G1 رونوشت از پروفایل (همه P2).
4. تصمیم مالک (مستند جدا، مسدودکننده نیست): A12، B14، B18، B19، B22، C1، C9، C11، D7، E4، F5، G4، H5؛ بلوک ویدیو/صدا در مطلب (منبع معتبر)؛ «مدت خودکار» رویداد؛ هوش مصنوعی داخلی (بدون شاهد در طراحی/تاریخچه).
