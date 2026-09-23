# راهنمای اسکیل‌های جدید استریکس (Context7، UI Skills، Supabase، Playwright CLI و خودِ Strix)

> این سند خلاصهٔ کاری است که در همین ریپو انجام شد: پنج ابزاری که فرستادید به‌صورت **اسکیل‌های داخلی ایجنت** (`strix/skills/`) اضافه شدند تا ایجنت‌های Strix بتوانند از آن‌ها استفاده کنند، و یک اسکیل هم‌بندی برای «حلقهٔ ساخت و اثبات امن» اضافه شد.

---

## ۱) چه چیزی اضافه شد

| فایل | نام اسکیل | کاربرد |
| --- | --- | --- |
| `strix/skills/tooling/context7.md` | `context7` | گرفتن داکیومنتِ نسخه‌دقیق کتابخانه‌ها (MCP یا CLI) پیش از نوشتن کد یا پچ |
| `strix/skills/tooling/playwright_cli.md` | `playwright_cli` | مرورگر واقعی برای اثبات یافته‌ها و بازآزمایی اصلاحیه‌ها (اسنپ‌شات رفرنس‌محور، سشن‌ها، state، شبکه، تریس، کدگن) |
| `strix/skills/tooling/supabase_cli.md` | `supabase_cli` | استک لوکال Supabase، مایگریشن‌ها، `db lint`/`db advisors` و اتصال MCP — همراه با پیش‌فرض‌های امن (RLS-first) |
| `strix/skills/tooling/ui_skills.md` | `ui_skills` | رجیستری اسکیل‌های طراحی (ui-skills.com) + چک‌لیست Baseline UI برای کدی که در جریان رفع آسیب‌پذیری نوشته می‌شود |
| `strix/skills/custom/secure_stack_loop.md` | `secure_stack_loop` | اسکیل هم‌بند: داکیومنت → کد → اثبات در مرورگر → اسکن دوبارهٔ Strix |

همچنین:
- `strix/skills/README.md` به‌روزرسانی شد (دستهٔ `/tooling` و فهرست اسکیل‌های شاخص).
- `docs/integrations/mcp.mdx` یک بخش جدید گرفت: **«سرورهای آمادهٔ کپی‌پیست»** برای Context7، UI Skills و Supabase (به‌صورت read-only).

نکتهٔ فنی: لودر اسکیل‌ها در `strix/skills/__init__.py` همهٔ پوشه‌های دسته را می‌خواند و فایل‌های تازه در build هم لحاظ می‌شوند (`strix.spec` از `skills/**/*.md` استفاده می‌کند و hatchling هم فایل‌های غیر‌پایتونی داخل پکیج را شامل می‌شود). بنابراین هیچ تغییری در کد لازم نبود.

---

## ۲) پنج ابزار، یک نگاه

### ۱. Context7 — داکیومنتِ نسخه‌دقیق
- سایت: <https://context7.com> · گیت‌هاب: <https://github.com/upstash/context7> (MIT)
- نقش در پروژه: جلوگیری از «توهم API». وقتی در حال نوشتن یا بازبینی یک پچ هستیم، امضاها و گزینه‌های واقعی همان نسخه را از داکیومنت می‌گیریم.
- نقطهٔ اتصال MCP: `https://mcp.context7.com/mcp` با دو ابزار `resolve-library-id` و `query-docs`؛ کلید رایگان از <https://context7.com/dashboard>.
- خط فرمان (Node 18+):

```bash
npx ctx7@latest library supabase "row level security policy examples"
npx ctx7@latest docs /supabase/supabase "RLS policy for per-tenant reads"
npx ctx7@latest setup --mcp        # اتصال به ایجنت کدنویس
```

- هشدار: محتوا مشارکتی است؛ برای موارد امنیتی حتماً با نسخهٔ نصب‌شدهٔ واقعی مقایسه کنید و هیچ توکن/دادهٔ حساسی در کوئری نگذارید.

### ۲. UI Skills — اسکیل‌های مهندسی طراحی
- سایت: <https://www.ui-skills.com/> · گیت‌هاب: <https://github.com/ibelick/ui-skills> (MIT)
- نقش در پروژه: هر کد فرانت‌اندی که در جریان رفع آسیب‌پذیری نوشته می‌شود، باید حداقل‌های طراحی/دسترس‌پذیری را رعایت کند. رجیستری شامل اسکیل‌های مشارکتی است (مثل `anthropics/frontend-design`، `emilkowalski/improve-animations`، `shadcn/improve`) به‌همراه فایل‌های **DESIGN.md** از Vercel، Atlassian، Mintlify و UNICEF.
- CLI: `npx ui-skills start` / `categories` / `list --category motion` / `get baseline-ui`
- MCP: `https://www.ui-skills.com/mcp` با ابزارهای `list_skills` و `get_skill` (بدون احراز هویت).
- در اسکیل نوشته‌شده، «Baseline UI» به‌صورت چک‌لیست عملی آمده است: پرimitiveهای دسترس‌پذیر (`Base UI`/`React Aria`/`Radix`)، `aria-label` روی دکمه‌های آیکونی، `AlertDialog` برای کارهای مخرب، `h-dvh` به‌جای `h-screen`، انیمیشن فقط روی `transform/opacity` و زیر ۲۰۰ms، احترام به `prefers-reduced-motion`، `text-balance`/`tabular-nums`، مقیاس ثابت `z-index` و …

### ۳. Supabase — بک‌اند
- سایت: <https://supabase.com/> · مونوریپو: <https://github.com/supabase/supabase> · سرور MCP: <https://github.com/supabase/mcp>
- نقش در پروژه: ساخت و راستی‌آزمایی بک‌اند؛ خواندن اسکیمای واقعی و پالیسی‌ها (به‌جای حدس زدن از روی پاسخ‌ها) از طریق MCP.
- استک لوکال: `supabase init` → `supabase start`؛ پورت‌های پیش‌فرض از `config.toml` تازه: API روی `54321`، Postgres روی `54322`، Studio روی `54323`، Mailpit روی `54324` و MCP لوکال روی `http://localhost:54321/mcp`.
- دستورهای کلیدی بازبینی امنیتی (نسخهٔ CLI آزمایش‌شده: `2.117.0`):

```bash
supabase db lint --local --level warning --fail-on warning
supabase db advisors --local --type security --level warn --fail-on warn
supabase db query "select tablename, policyname, cmd, roles, qual from pg_policies where schemaname = 'public'"
supabase test db
supabase gen types typescript --local > src/db/types.ts
```

- MCP میزبانی‌شده، با پارامترهای URL: `https://mcp.supabase.com/mcp?project_ref=<ref>&read_only=true&features=database,docs,debugging` — ابزارهایی مثل `list_tables`، `execute_sql`، `get_advisors`، `query_logs`.
- اسکیل‌های مرتبط در همین ریپو: `supabase` (پلی‌بوک حمله) در برابر `supabase_cli` (ابزار ساخت و بازبینی). یکی بدون دیگری نصف کار است.

### ۴. Playwright CLI — مرورگر برای ایجنت‌ها
- داکیومنت: <https://playwright.dev/agent-cli/introduction> · گیت‌هاب: <https://github.com/microsoft/playwright-cli>
- نصب (نسخهٔ آزمایش‌شده: `0.1.21`):

```bash
npm install -g @playwright/cli@latest
playwright-cli install --skills
playwright-cli install-browser chromium
```

- چرخهٔ کار: `open` → `snapshot` (رفرنس‌هایی مثل `e21`) → `click/fill` → **اسنپ‌شات مجدد**؛ رفرنس‌ها بعد از هر تغییر صفحه بی‌اعتبار می‌شوند.
- چیزهایی که برای کار امنیتی حیاتی‌اند: `state-save`/`state-load` برای نگه‌داشتن هویت‌ها (`tenant_a.json` / `tenant_b.json`) و اثبات مرز مجوزدهی، `requests`/`request <n>`/`response-body <n>` برای دیدن بدنهٔ واقعی، `route` برای موک‌کردن، `console`، `set-reduced-motion`، `tracing-start/stop` و `recording-stop` که فلو را به کد Playwright تبدیل می‌کند.
- نسبتش با `agent_browser` (که از قبل در سندباکس نصب و به پروکسی Caido وصل است): `agent_browser` برای گشت‌زنی سریع و ثبت ترافیک در پروکسی؛ `playwright-cli` وقتی هویت ذخیره‌شده، بدنهٔ درخواست/پاسخ، شبیه‌سازی، تریس و کدگن لازم است.

### ۵. Strix — خودِ حلقه
- سایت: <https://www.strix.ai> · گیت‌هاب: <https://github.com/usestrix/strix>
- در اسکیل `secure_stack_loop` نقش «بستن حلقه» به Strix سپرده شده است: بعد از اصلاح، همان ابزار اسکن را دوباره اجرا می‌کنیم.

```bash
strix -n -t ./ --scan-mode quick --max-budget 10
strix -n -t https://staging.example.com --max-budget 20
```

- کدهای خروج در حالت headless: `0` پاک، `1` خطای مهلک، `2` یافته. خروجی `0` فقط چیزی را پوشش می‌دهد که تحلیل شده — `strix_runs/<run-name>/run.json` را چک کنید (`status` و `llm_usage.cost` در برابر بودجه). مصنوعات: `penetration_test_report.md`، `vulnerabilities/*.md`، `vulnerabilities.json`، `findings.sarif`.
- بدون Docker یا در CI: مسیر مدیریت‌شدهٔ `strix cloud login` و `strix cloud scans start ...` (با تأیید صریح digest سورس).

---

## ۳) نحوهٔ استفادهٔ ایجنت‌ها از این اسکیل‌ها

اسکیل‌ها دو مسیر مصرف دارند:

1. **از پیش بارگذاری برای یک متخصص** — موقع ساخت ایجنت فرزند:

```python
create_agent(
    task="Fix BOLA in the orders API and prove it in a browser",
    name="API Fixer",
    skills=["supabase_cli", "playwright_cli", "secure_stack_loop"],
)
```

2. **بارگذاری درون‌خطی** — با ابزار `load_skill` وقتی وسط کار به راهنما نیاز شد:

```python
load_skill(skills=["context7", "ui_skills"])
```

نام‌ها به‌صورت `دسته/نام` هم قابل استفاده‌اند (`tooling/context7`). سقف هر ایجنت ۵ اسکیل است و انتخاب‌گرِ خودکار حدود ۱–۳ اسکیل متناسب با تسک را برمی‌دارد.

---

## ۴) نمونهٔ پیکربندی MCP

مسیر فایل: `~/.strix/mcp-servers.json` (یا با `--mcp-config <path>` / متغیر `STRIX_MCP_CONFIG`) — Strix در شروع هر اجرا آن را می‌خواند. برای فقط-همین-اجرا می‌شود با `strix --mcp-server context7 ...` محدودش کرد.

```json
[
  {
    "name": "context7",
    "transport": "http",
    "url": "https://mcp.context7.com/mcp",
    "auth": { "kind": "bearer", "token": "<CONTEXT7_API_KEY>" },
    "notes": "داکیومنت نسخه‌دقیق کتابخانه‌ها"
  },
  {
    "name": "ui_skills",
    "transport": "http",
    "url": "https://www.ui-skills.com/mcp",
    "allowed_tools": ["list_skills", "get_skill"]
  },
  {
    "name": "supabase",
    "transport": "http",
    "url": "https://mcp.supabase.com/mcp?project_ref=<ref>&read_only=true&features=database,docs,debugging",
    "auth": { "kind": "bearer", "token": "<SUPABASE_ACCESS_TOKEN>" },
    "allowed_tools": ["list_tables", "execute_sql", "get_advisors", "query_logs"],
    "notes": "فقط‌خواندنی و محدود به یک پروژه"
  }
]
```

نکات:
- Supabase MCP در حالت تعاملی با OAuth کار می‌کند، ولی Strix فقط `bearer` دارد؛ برای CI هم مستندات Supabase همین مسیر (PERSONAL ACCESS TOKEN) را توصیه می‌کند.
- `allowed_tools` را جدی بگیرید: Strix خودش تصمیم نمی‌گیرد کدام ابزار سرور فقط «خواندن» است.
- داده‌ای که از طریق MCP برمی‌گردد ورودی غیرقابل‌اعتماد است (مسیر شناخته‌شدهٔ تزریق پرامپت از طریق محتوای ذخیره‌شده).

---

## ۵) حلقهٔ کاری پیشنهادی برای پروژه

| گام | ابزار | خروجی قابل‌اتکا |
| --- | --- | --- |
| ۰. دامنه و مجوز | — | هدف، محیط (لوکال/استیجینگ)، دو هویت برای اثبات BOLA/IDOR |
| ۱. امضای دقیق API | Context7 | نسخهٔ تأییدشده + اسنیپت واقعی |
| ۲. کد با پیش‌فرض امن | `supabase_cli` + `ui_skills` | مایگریشن با RLS و پالیسی در همان تغییر؛ UI با چک‌لیست Baseline |
| ۳. بازبینی عینی بک‌اند | `supabase db lint` / `db advisors` / `test db` | صفر advsor به‌عنوان کف، نه سقف |
| ۴. اثبات در مرورگر | Playwright CLI | اسکرین‌شات/تریس قبل و بعد با هویت‌های مشخص |
| ۵. اسکن دوباره | Strix | `findings.sarif` و گزارش تازه در `strix_runs/` |

قاعدهٔ طلایی: **هر ادعای «اصلاح شد» باید با دستور، هویت و مصنوع همراه باشد.** هرگز چند تغییر را با هم جمع نکنید تا یک بار تأیید شوند.

---

## ۶) وضعیت راستی‌آزمایی در همین سندباکس

| ابزار | نتیجه |
| --- | --- |
| Playwright CLI | نصب شد (`0.1.21`)؛ `--help`، `install --skills`، `install-browser`، دامنهٔ دستورها (شبکه،‌استوریج، شبیه‌سازی، تریس، WebMCP) تأیید شد |
| Supabase CLI | با `npx supabase@latest` اجرا شد (`2.117.0`)؛ زیرفرمان‌ها، `db lint`، `db advisors`، `db query`، `gen types` و پورت‌های پیش‌فرض `config.toml` تأیید شد |
| UI Skills CLI | اجرا شد؛ دستورهای `start/categories/list/get` تأیید شد |
| Context7 CLI | اجرا شد؛ `library`/`docs`/`setup` و ابزارهای MCP تأیید شدند |
| فراخوانی‌های شبکه‌ای زنده | **محدود**: خروجی شبکهٔ این سندباکس فقط npm/pypi را عبور می‌دهد؛ `ui-skills.com`، `mcp.context7.com`، `supabase.com` و `cdn.playwright.dev` از اینجا مسدودند. دانلود باینری مرورگر هم همین‌جا شکست خورد |

یعنی: ساختار، دستورها و اتصال‌ها مستند و بخشِ اجرایی CLI تأیید شده است؛ ولی تماس‌های واقعی با سرورهای MCP، دانلود مرورگر و اجرای یک اسکن زنده نیاز به شبکهٔ باز دارد (ماشین خودتان یا کانتینر Strix).

---

## ۷) گام بعدی

برای «پروژه» یکی از این‌ها را مشخص کنید تا بلافاصله شروع کنیم:

1. **ساخت یک اپ نمونه** روی همین استک (Supabase + فرانت‌اند با Baseline UI) و بعد اسکن آن با Strix.
2. **سخت‌سازی یک اپ موجود** (ریپو/آدرس هدف را بدهید): حلقهٔ بالا را روی آن اجرا کنیم.
3. **رسمی‌کردن این ابزارها در CI** (GitHub Actions: `db advisors` + Playwright + Strix scan روی هر PR).

> یادآوری: فقط روی دارایی‌هایی اسکن و تست اجرا کنید که مجوز آن را دارید.
