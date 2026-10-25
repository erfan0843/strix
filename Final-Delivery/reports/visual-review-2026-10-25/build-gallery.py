#!/usr/bin/env python3
"""Builds index.html (static gallery) for the visual review from the committed acceptance evidence.
Run from this folder. No product files are touched; images are referenced from ../evidence/… (full page)
and img/ (first-viewport crops produced with Pillow from the same full-page shots)."""
import json, html, os
HERE = os.path.dirname(os.path.abspath(__file__))
EV = "../evidence/product-acceptance-2026-10-25"
BEFORE_SHA, AFTER_SHA, HEAD_SHA = "974f4bcb07a1", "2e79729b4a21", "b8f33d198309"
FIXTURE = "nora-fixture/nora.db · md5 d4bfabcf… · پیش از هر دور بازنشانی؛ پس از دور: forms=3 / form_responses=2 (بدون تغییر)"
sizes = json.load(open(os.path.join(HERE, "img", "sizes.json")))
metrics = {}
for d in ("before", "after"):
    for r in json.load(open(os.path.join(HERE, EV, d, "metrics.json"))):
        metrics[(d, r["role"], r["name"], r["w"])] = r

PAGES = [
 dict(key="home", role="guest", title="خانهٔ عمومی", url="home.html", who="مهمان (بدون ورود)"),
 dict(key="dash", role="owner", title="داشبورد مالک", url="admin.html#dash", who="مالک"),
 dict(key="m-dash", role="manager", title="داشبورد مدیر محدود", url="admin.html#dash", who="مدیر محدود (بدون ev_publish و مجوز مالی)"),
 dict(key="events-list", role="owner", title="فهرست مدیریت رویدادها", url="admin.html#events", who="مالک"),
 dict(key="event-hub", role="owner", title="پروندهٔ رویداد", url="admin.html#event=<id>", who="مالک"),
 dict(key="forms", role="owner", title="مرکز فرم‌ها", url="admin.html#forms", who="مالک"),
 dict(key="event-regs", role="owner", title="ثبت‌نام‌کنندگان", url="admin.html#event=<id>&tab=regs", who="مالک (رویداد فیکسچر بدون ثبت‌نام → حالت خالی)"),
 dict(key="settings", role="owner", title="تنظیمات", url="admin.html#settings", who="مالک"),
 dict(key="account-member", role="member", title="حساب عضو", url="account.html", who="عضو (ورود با حساب آزمایشی)"),
]

# ارزیابی با نگاه کاربر — از خواندن شات‌های «بعد» (و مقایسه با «قبل»)؛ نوع ایراد: «کاربردپذیری» یا «سلیقه‌ای»
EVAL = {
"home": dict(
  first="بنر تیره با عنوان و دکمهٔ روشن «دیدن رویدادها»؛ نگاه درست به مقصد اصلی می‌رود.",
  primary="روشن (دکمهٔ پر، تنها رنگ روشن روی بنر). «مطالب» به‌درستی ثانویه است.",
  compete="کارت جست‌وجو با ۴ چیپ ستاره‌دار درست زیر بنر (پیش از هر محتوایی)؛ سه کنترل هم‌وزن سربرگ (پشتیبانی، شب/روز، ساعت)؛ شمارش معکوس با ارقام آبی که رنگ تأکیدی CTA را تکرار می‌کند.",
  cards="بنر، کارت جست‌وجو، کارت رویداد: سه کادر پشت هم. کارت جست‌وجو گروه‌بندی معنایی اضافه نمی‌کند؛ فقط یک سطح است.",
  next="بله؛ ویترین + «همهٔ رویدادها» + tabbar. نسبت به قبل (ویترین یک‌سوم عرض و فضای خالی) روشن‌تر شده است.",
  family="بله؛ همان زبان عمومی نورا (سطوح روشن، هیرلاین، چیپ).",
  issues=[("کاربردپذیری","در ۳۹۰ چیپ چهارم «گواهی‌دار» فقط به یک ستاره بدون برچسب تقلیل می‌یابد؛ صافی ناخوانا می‌شود.","img/after/home-390-top.png"),
          ("کاربردپذیری","کارت جست‌وجو + چیپ‌ها پیش از محتوا: اولین رویداد در ۱۴۴۰ از ≈۵۵۰px و در ۳۹۰ زیر تا شروع می‌شود؛ کاربر تازه‌وارد ابتدا ابزار می‌بیند، نه محتوا.",None),
          ("سلیقه‌ای","پیل ساعت در سربرگ و ارقام آبی شمارش معکوس، دو تأکید بی‌هدف کنار CTA.",None)]),
"dash": dict(
  first="عنوان «کارهای در انتظار» و چیپ «۳ مورد»؛ هدف درستی است.",
  primary="اقدام اصلی یکتا وجود ندارد (داشبورد = ورودی)؛ سه ردیف کار با شورون، قابل‌فهم.",
  compete="سربرگ با چهار عنصر پیش از هر محتوایی (چیپ «وضعیت از API سرور · سالم»، ساعت، هویت، مربع آیکون)؛ خوشهٔ پنج پیوند ریز «بدون مورد: …»؛ KPIهای کارت‌درکارت.",
  cards="کارت کارها خوب گروه‌بندی می‌کند؛ «شمارش‌های ۳۰ روز» کارتی است که چهار کارت کوچک در خود دارد (دو سطح بصری بدون معنای اضافه).",
  next="بله برای کارها؛ «گزارش کامل» و «همهٔ رویدادها» پیوندهای روشن.",
  family="بله؛ هم‌خانواده با بقیهٔ پنل. نسبت به قبل (۸ ردیف، ۶ صفر، جملهٔ توضیحی) بسیار آرام‌تر.",
  issues=[("کاربردپذیری","در ۱۴۴۰ ستون چپ (رویدادهای پیش‌رو) کوتاه است و بلوک خالی بزرگی کنار کارت کارها می‌ماند؛ نمای اول نیمه‌خالی به نظر می‌رسد.","img/after/dash-1440-top.png"),
          ("سلیقه‌ای","KPI کارت‌درکارت؛ همان اعداد با ردیف‌های هیرلاین‌دار در خود کارت کافی است.",None),
          ("کاربردپذیری","واژگان فنی در سربرگ («API سرور»)؛ برای مالک غیرفنی معنایی جز «سبز است» ندارد و جای ثابتی از سربرگ را می‌گیرد.",None)]),
"m-dash": dict(
  first="همان داشبورد مالک؛ تنها تفاوت قفل کنار «تنظیمات» و هویت «qa-manager مدیر».",
  primary="مثل مالک.",
  compete="مثل مالک؛ به‌علاوه مورد «تنظیمات» که دیده می‌شود اما مقصدش برای این نقش بسته است.",
  cards="مثل مالک.",
  next="بله؛ یکسان‌بودن ساختار برای دو نقش مثبت است (یادگیری یک‌باره).",
  family="بله.",
  issues=[("کاربردپذیری","«تنظیمات» با قفل در ناوبری می‌ماند: شفاف است اما یک مقصد قابل‌کلیک است که به «مجوز ندارید» می‌رسد؛ تصمیم محصولی (نمایش با قفل) باید آگاهانه تأیید شود.","img/after/m-dash-1440-top.png"),
          ("سلیقه‌ای","نام کاربری لاتین داخل پیل هویت، در سربرگ فارسی ناهم‌خوان است (نام نمایشی فارسی اگر در پروفایل باشد بهتر است).",None)]),
"events-list": dict(
  first="دکمهٔ پر «رویداد تازه» در انتهای سطر و سپس جعبهٔ جست‌وجو؛ سگمنت «رویدادها | مطالب» بالای کارت.",
  primary="روشن («رویداد تازه»). «تصاویر» و «بازخوانی» هم‌اندازه کنار آن ثانویه‌اند اما هم‌وزن دیده می‌شوند.",
  compete="۵ چیپ وضعیت + سطر «صافی‌ها و ترتیب»؛ در هر ردیف دو خط متای خاکستری (از جمله «آخرین تغییر» برای همهٔ ردیف‌ها).",
  cards="یک کارت برای همه‌چیز: خوب. ردیف‌ها با هیرلاین جدا شده‌اند.",
  next="بله؛ «مدیریت رویداد» در هر ردیف روشن، «ویرایش» کنار آن، بقیه در «بیشتر» (با صفحه‌کلید آزموده شد).",
  family="بله. نسبت به قبل (۸ بلوک کنترلی پیش از اولین ردیف) اولین ردیف بسیار بالاتر آمده است.",
  issues=[("کاربردپذیری","در ۳۹۰ سطر سرکارت به سه خط می‌شکند (بازخوانی/تصاویر، عنوان، «رویداد تازه» تنها در یک خط) و دکمهٔ جداگانهٔ «جست‌وجو» کنار ورودی تکراری است؛ اولین ردیف از ≈۵۴۰px شروع می‌شود.","img/after/events-list-390-top.png"),
          ("کاربردپذیری","سگمنت «رویدادها | مطالب» بیرون کارت با ظاهر چیپ: مثل زبانهٔ صفحه عمل می‌کند اما شبیه صافی است.",None),
          ("سلیقه‌ای","خط دوم متای هر ردیف («آخرین تغییر: …») ارزش تصمیمی کم و هزینهٔ ارتفاع دارد.",None)]),
"event-hub": dict(
  first="عنوان رویداد با برچسب وضعیت، سپس شش کاشی هم‌وزن.",
  primary="«ویرایش رویداد» (کادردار) و «مشاهدهٔ صفحه»؛ برای رویداد برگزارشده اقدام اصلی طبیعتاً کم‌رنگ است؛ کاشی‌ها ناوبری‌اند.",
  compete="سطر دوم چیپ («ثبت‌نام: ۰») همان اطلاع چیپ سطر اول («ثبت‌نام: ۰ نفر · بدون سقف») را تکرار می‌کند؛ درون کاشی‌ها فهرست پیوندهای زیرخط‌دار (الگوی دوم تعامل داخل یک کاشی).",
  cards="شش کاشی با ارتفاع برابر و بدنهٔ خالی؛ کادر بیش از محتواست. گروه‌بندی ۶گانه درست است، ظرف آن سنگین.",
  next="بله؛ نام کاشی‌ها گویاست. اما این‌که «روی کاشی کلیک کنم یا روی پیوند زیر آن» مبهم است.",
  family="بله. نسبت به قبل (۹ چیپ، ۶ صفر، سگمنت داخل پرونده) خلوت‌تر.",
  issues=[("کاربردپذیری","چیپ تکراری «ثبت‌نام: ۰» در سطر جداگانه (یک اطلاع، دو بار، دو جا).","img/after/event-hub-1440-top.png"),
          ("کاربردپذیری","در ۳۹۰ سطر چیپ‌ها از لبه بریده می‌شود («مبل…») و «ویرایش تنظیمات ثبت‌نام» به شکل متن لخت زیر دکمه می‌افتد؛ سلسله‌مراتب اقدام‌ها گم می‌شود.","img/after/event-hub-390-top.png"),
          ("سلیقه‌ای","کاشی‌های بلند با بدنهٔ خالی و پیوندهای زیرخط‌دار؛ فهرست ردیفی با شمارش و یک شورون همان کار را با نصف ارتفاع می‌کند.",None)]),
"forms": dict(
  first="دکمهٔ پر «فرم تازه» و برچسب «منبع حقیقت ثبت‌نام و خرید»؛ سپس پاراگراف فنی.",
  primary="روشن («فرم تازه»)؛ اما «مرکز فرم‌ساز و پاسخ‌ها» کنار آن و «مرکز فرم‌ها» در نوار کناری، یک مقصد را دو بار نشان می‌دهند.",
  compete="پاراگراف فنی (`/api/forms/`، `fm_export`، CSV): دو خط در ۱۴۴۰ و پنج خط در ۳۹۰ (≈یک‌پنجم نما)؛ متای هر ردیف با شناسهٔ خام (`مدل registration · رویداد ev-a5371e1afd · recording_access`).",
  cards="یک کارت؛ خوب.",
  next="چهار اقدام آیکونی بدون برچسب در هر ردیف (چشم، دانلود، صندوق، مداد): روی دسکتاپ با hover و روی موبایل با حدس.",
  family="بله؛ ولی تنها صفحهٔ پنل است که هنوز با متن فنی شروع می‌شود (در دو مرحلهٔ قبل دست نخورده بود؛ سنجه‌ها قبل/بعد یکسان).",
  issues=[("کاربردپذیری","اقدام‌های آیکونی بی‌برچسب؛ روی موبایل hover وجود ندارد.","img/after/forms-390-top.png"),
          ("کاربردپذیری","پاراگراف فنی + شناسه‌های خام در ردیف‌ها؛ اولین فرم در ۳۹۰ تازه در انتهای نما دیده می‌شود.",None),
          ("کاربردپذیری","مقصد تکراری فرم‌ساز (پیوند سرکارت + نوار کناری).",None)]),
"event-regs": dict(
  first="دو پیوند بازگشت پشت هم («بازگشت به رویدادها»، «پروندهٔ رویداد») و سپس حالت خالی.",
  primary="وجود ندارد؛ حالت خالی («هنوز کسی ثبت‌نام نکرده») بن‌بست است: نه «ثبت‌نام دستی»، نه «پیوند ثبت‌نام را به اشتراک بگذار».",
  compete="جست‌وجو + ۳ چیپ وضعیت + «صافی‌های پرداخت و حضور» برای فهرستی که خالی است؛ منوی «بخش‌های دیگر».",
  cards="دو کارت (فهرست، لغوشده‌ها): منطقی. سربرگ صفحه هنوز «رویدادها و مطالب» است و نام رویداد فقط در متن ریز زیر عنوان.",
  next="بازگشت بله؛ ادامهٔ کار خیر (بدون اقدام).",
  family="بله. نسبت به قبل (۱۰ چیپ صفر + جملهٔ توضیحی) خلوت.",
  issues=[("کاربردپذیری","حالت خالی بدون اقدام.","img/after/event-regs-1440-top.png"),
          ("کاربردپذیری","دو پیوند بازگشت با دو مقصد نزدیک، پشت هم.",None),
          ("سلیقه‌ای","نمایش ابزار صافی وقتی فهرست خالی است.",None)]),
"settings": dict(
  first="فهرست «حوزه‌های تنظیمات» (۸ ردیف)؛ در ۳۹۰ کل نمای اول همین فهرست است.",
  primary="وجود ندارد؛ «ذخیره در سرور» (درست) غیرفعال و خاکستری در انتهای زیرکارت، کم‌پیدا.",
  compete="دو لایهٔ ناوبری با دو مدل (فهرست حوزه‌ها + چیپ‌های گروه)؛ چهار حوزه از هشت‌تا از صفحه بیرون می‌روند (فرم‌ساز، کاربران، باشگاه، رویدادها).",
  cards="سه سطح تو در تو: کارت صفحه → چیپ‌ها → زیرکارت با نوار عنوان («نوشته‌های سامانه») → فیلد → زیرکارت دوم («بدون مصرف‌کنندهٔ سروری») با سه ردیفِ «در دسترس نیست».",
  next="نیمه‌روشن؛ کاربر باید یاد بگیرد کدام لایه چه می‌کند.",
  family="بله. نسبت به قبل (۸ کاشی بزرگ) سبک‌تر؛ ساختار همان است.",
  issues=[("کاربردپذیری","دو مدل ناوبری در یک صفحه و پیوندهای بیرون‌رو؛ «کجا تنظیم می‌شود» نیاز به آزمون‌وخطا دارد.","img/after/settings-1440-top.png"),
          ("کاربردپذیری","در ۳۹۰ هیچ تنظیم واقعی در نمای اول نیست.","img/after/settings-390-top.png"),
          ("سلیقه‌ای","تو در تویی سه‌سطحی کارت‌ها.",None)]),
"account-member": dict(
  first="نوار آبی گرادیانی با دو پیل («حساب بله وصل است»، «حساب امن») و آواتار که روی لبهٔ نوار نشسته: پررنگ‌ترین عنصر صفحه و تزئینی.",
  primary="«ثبت‌نام‌های من» (پر)؛ اما ردیف «رویدادهای من» در فهرست زیر همان مقصد است و «فرم‌های من» هم دکمه است هم ردیف.",
  compete="سه جعبهٔ آمار که همان شمارش‌های چیپِ ردیف‌ها را تکرار می‌کنند («۰ ثبت‌نام»)؛ «خروج» در همان سطر دکمهٔ اصلی؛ زنگ اعلان.",
  cards="کارت هویت + کارت «بخش‌های من»: درست. اما نوار گرادیانی زبان بصری متفاوتی از خانهٔ آرام عمومی و از پنل دارد.",
  next="ردیف‌ها روشن‌اند؛ دکمه‌های تکراری انتخاب را دوگانه می‌کنند.",
  family="نیمه؛ تنها صفحه‌ای است که از گرادیان رنگی پر استفاده می‌کند.",
  issues=[("کاربردپذیری","مسیرهای تکراری: دکمه‌ها در برابر ردیف‌ها، جعبه‌های آمار در برابر چیپ ردیف‌ها.","img/after/account-member-1440-top.png"),
          ("کاربردپذیری","تنها اطلاع قابل‌اقدام («نام هنوز در پروفایل ثبت نشده») کم‌رنگ‌ترین عنصر سربرگ است؛ تزئین بر اقدام غلبه دارد.",None),
          ("کاربردپذیری","«خروج» چسبیده به دکمهٔ اصلی (اقدام مخرب کنار اقدام اصلی).",None)]),
}

def esc(s): return html.escape(s, quote=True)
def m(d, p, w, f):
    r = metrics.get((d, p["role"], p["key"], w)); return "—" if not r else r.get(f, "—")
def fa(x): return str(x).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

css = """
@font-face{font-family:VazirUI;src:url('../../website/nora-ui/fonts/Vazirmatn-UI-FD-Regular.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:VazirUI;src:url('../../website/nora-ui/fonts/Vazirmatn-UI-FD-Bold.woff2') format('woff2');font-weight:700;font-display:swap}
:root{--ink:#1b1f24;--ink2:#4b5563;--ink3:#6b7280;--line:#e5e7eb;--bg:#f7f7f6;--card:#fff;--brand:#1d4ed8;--warn:#b45309;--ok:#047857}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.8 VazirUI,'Vazirmatn',Tahoma,sans-serif}
header.top{padding:28px 24px 8px;max-width:1400px;margin:0 auto}h1{font-size:24px;margin:0 0 6px}h2{font-size:20px;margin:0;scroll-margin-top:12px}h3{font-size:15px;margin:18px 0 8px;color:var(--ink2)}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 18px;font-size:13px;color:var(--ink2);margin:8px 0 0}.meta b{color:var(--ink)}
main{max-width:1400px;margin:0 auto;padding:8px 24px 60px}
nav.toc{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 24px}nav.toc a{font-size:13px;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);text-decoration:none}
section.page{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:0 0 26px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair.m{grid-template-columns:repeat(2,minmax(0,330px));justify-content:start}
figure{margin:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fafafa}figure img{display:block;width:100%;height:auto}
figcaption{font-size:12.5px;color:var(--ink2);padding:8px 10px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:4px 12px;background:#fff}figcaption b{color:var(--ink)}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--ink2)}.tag.before{background:#f3f4f6}.tag.after{background:#e0ecff;border-color:#bfdbfe;color:#1e3a8a}
details.full{margin-top:10px}details.full summary{cursor:pointer;font-size:13.5px;color:var(--brand)}details.full .pair{margin-top:8px;align-items:start}
table.ev{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:6px}table.ev th{width:190px;text-align:start;color:var(--ink3);font-weight:500;vertical-align:top;padding:6px 0 6px 10px;border-top:1px solid var(--line)}table.ev td{padding:6px 0;border-top:1px solid var(--line);vertical-align:top}
ol.issues{margin:6px 0 0;padding-inline-start:20px;font-size:13.5px}ol.issues li{margin:4px 0}.kind{font-size:11.5px;padding:1px 7px;border-radius:999px;margin-inline-end:6px}.kind.u{background:#fef3c7;color:var(--warn)}.kind.t{background:#eef2ff;color:#3730a3}
ol.issues a{color:var(--brand);font-size:12px;margin-inline-start:6px}
.num{font-size:12.5px;color:var(--ink3)}.num b{color:var(--ink2);font-weight:600}
.note{font-size:13px;color:var(--ink2);background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 14px;margin:12px 0}
@media (max-width:900px){.pair,.pair.m{grid-template-columns:1fr}header.top,main{padding-inline:12px}}
"""

def fig(d, p, w, kind):
    tag = f'<span class="tag {d}">{"قبل" if d=="before" else "بعد"} · {BEFORE_SHA if d=="before" else AFTER_SHA}</span>'
    if kind == "top":
        src = f'img/{d}/{p["key"]}-{w}-top.png'; what = f'نمای اولیه ({w}×{900 if w==1440 else 844})'
    else:
        src = f'{EV}/{d}/{p["key"]}-{w}-full.png'; s = sizes[f'{d}/{p["key"]}-{w}']; what = f'نمای کامل ({s["w"]}×{s["h"]})'
    return (f'<figure><a href="{src}" target="_blank" rel="noopener"><img loading="lazy" src="{src}" alt="{esc(p["title"])} {what}"/></a>'
            f'<figcaption>{tag}<span>{what}</span><span>نقش: <b>{esc(p["who"])}</b></span><span>فیکسچر: بازنشانی‌شده</span>'
            f'<span class="num">ارتفاع صفحه <b>{fa(m(d,p,w,"sh"))}</b> · دکمه <b>{fa(m(d,p,w,"btn"))}</b> · چیپ <b>{fa(m(d,p,w,"chips"))}</b> · متن توضیحی <b>{fa(m(d,p,w,"pTextLen"))}</b></span></figcaption></figure>')

parts = [f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>بازبینی بصری نورا · ۱۴۰۵/۰۸/۰۳</title><style>{css}</style></head><body>
<header class="top"><h1>بازبینی بصری نورا — گالری قبل/بعد با دادهٔ یکسان</h1>
<div class="meta"><span>شاخه: <b>arena/840de336-strix</b></span><span>«قبل»: <b>{BEFORE_SHA}</b> (پیش از بازآرایی)</span><span>«بعد»: <b>{AFTER_SHA}</b> = ظاهر HEAD <b>{HEAD_SHA}</b> (کامیت‌های بعدی فقط گزارش/شواهد)</span>
<span>فیکسچر: <b>{FIXTURE}</b></span><span>مرورگر: Chromium headless، فونت‌های خود محصول</span><span>متن ارزیابی: <b>VISUAL-REVIEW-2026-10-25.fa.md</b> (همین پوشه)</span></div>
<div class="note">این صفحه فقط یک سند بازبینی ایستا در <code>Final-Delivery/reports/</code> است و در مسیر اجرایی محصول نیست. تصاویر کامل از پوشهٔ شواهد پذیرش (<code>{EV}</code>) خوانده می‌شوند؛ «نمای اولیه» برش ۹۰۰px/۸۴۴px بالای همان شات کامل است (عناصر ثابت مثل tabbar در شات کامل در جای نمای اول رسم می‌شوند). اعداد زیر هر تصویر از <code>metrics.json</code> همان دور (اولین viewport) است.</div>
</header><main><nav class="toc">""" + "".join(f'<a href="#{p["key"]}">{esc(p["title"])}</a>' for p in PAGES) + "</nav>"]

for p in PAGES:
    e = EVAL[p["key"]]
    parts.append(f'<section class="page" id="{p["key"]}"><h2>{esc(p["title"])} <span class="tag">{esc(p["url"])}</span> <span class="tag">{esc(p["who"])}</span></h2>')
    parts.append('<h3>دسکتاپ ۱۴۴۰ — نمای اولیه (راست: قبل، چپ: بعد)</h3><div class="pair">' + fig("before",p,1440,"top") + fig("after",p,1440,"top") + '</div>')
    parts.append('<details class="full"><summary>نمای کامل ۱۴۴۰ (قبل/بعد)</summary><div class="pair">' + fig("before",p,1440,"full") + fig("after",p,1440,"full") + '</div></details>')
    parts.append('<h3>موبایل ۳۹۰ — نمای اولیه</h3><div class="pair m">' + fig("before",p,390,"top") + fig("after",p,390,"top") + '</div>')
    parts.append('<details class="full"><summary>نمای کامل ۳۹۰ (قبل/بعد)</summary><div class="pair m">' + fig("before",p,390,"full") + fig("after",p,390,"full") + '</div></details>')
    parts.append('<h3>ارزیابی با نگاه کاربر (از شات «بعد»)</h3><table class="ev">')
    for k, lab in (("first","اولین چیزی که توجه را می‌گیرد"),("primary","روشنی اقدام اصلی"),("compete","عناصر رقیب"),("cards","کارت‌ها و کادرها"),("next","پیدا کردن مسیر بعدی"),("family","هم‌خانوادگی با نورا")):
        parts.append(f'<tr><th>{lab}</th><td>{esc(e[k])}</td></tr>')
    parts.append('</table><ol class="issues">')
    for kind, text, ref in e["issues"]:
        parts.append(f'<li><span class="kind {"u" if kind=="کاربردپذیری" else "t"}">{kind}</span>{esc(text)}' + (f'<a href="{ref}" target="_blank" rel="noopener">شاهد</a>' if ref else '') + '</li>')
    parts.append('</ol></section>')
parts.append('</main></body></html>')
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write("\n".join(parts))

# markdown fragment (_eval-fragment.md): merged into VISUAL-REVIEW-2026-10-25.fa.md section 1 and then deleted; regenerate only to re-sync texts
md = []
for p in PAGES:
    e = EVAL[p["key"]]
    md.append(f'### {p["title"]} — `{p["url"]}` · {p["who"]}\n')
    md.append('| پرسش | پاسخ از شات «بعد» |\n|---|---|')
    for k, lab in (("first","اولین چیزی که توجه را می‌گیرد"),("primary","روشنی اقدام اصلی"),("compete","عناصر رقیب"),("cards","کارت‌ها و کادرها"),("next","پیدا کردن مسیر بعدی"),("family","هم‌خانوادگی با نورا")):
        md.append(f'| {lab} | {e[k]} |')
    md.append('\nایرادها (حداکثر سه):\n')
    for i,(kind, text, ref) in enumerate(e["issues"],1):
        md.append(f'{i}. **{kind}** — {text}' + (f' (شاهد: `{ref}`)' if ref else ''))
    md.append('\nسنجه‌های اولین نما (قبل→بعد): ' + ' · '.join(
        f'{w}: ارتفاع {m("before",p,w,"sh")}→{m("after",p,w,"sh")}، دکمه {m("before",p,w,"btn")}→{m("after",p,w,"btn")}، چیپ {m("before",p,w,"chips")}→{m("after",p,w,"chips")}' for w in (1440,390)) + '\n')
open(os.path.join(HERE, "_eval-fragment.md"), "w", encoding="utf-8").write("\n".join(md))
print("ok", len(PAGES))
