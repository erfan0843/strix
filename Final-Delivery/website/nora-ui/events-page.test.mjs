/* آزمون صفحهٔ عمومی رویدادها روی عکس سرور (بدون فیکسچر محلی):
   صافی نوع/شیوه از رکوردهای واقعی، مرتب‌سازی، نمای تقویم از تاریخ ماشین‌خوان (on)،
   هش‌های قدیمی (#cal/#lib/#upcoming) و نبودِ دادهٔ نمایشی در تولید. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import jsdom from 'jsdom';

const { JSDOM } = jsdom;
/* فقط فایل‌های محلی بارگذاری می‌شوند؛ هیچ درخواست شبکه‌ای از صفحه بیرون نمی‌رود. */
const localOnly = {
  interceptors: [jsdom.requestInterceptor(async request => {
    if (new URL(request.url).protocol !== 'file:') return new Response('', { status: 403 });
    return undefined;
  })]
};
const DIR = fileURLToPath(new URL('./', import.meta.url));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

const content = {
  events: [
    { id: 'ev-late', t: 'نشست پاییزی', kind: 'نشست', privacy: 'public', d: 'شرح', when: 'دوشنبه ۲۰ مهر', on: '۱۴۰۵/۰۷/۲۰',
      time: '۱۸:۰۰', place: 'https://meet.example/room', price: 500000, cap: 40, tags: ['پاییز'], forms: [{ id: 'f-late', need: 'reg', n: 'ثبت‌نام' }] },
    { id: 'ev-soon', t: 'کارگاه عکاسی', kind: 'کارگاه', privacy: 'public', d: 'شرح', when: 'جمعه ۱۰ مهر', on: '1405/07/10',
      time: '۱۶:۰۰', place: 'سالن اصلی', mode: 'حضوری', price: 0, cap: 20 },
    { id: 'ev-undated', t: 'پویش بدون تاریخ', kind: 'پویش', privacy: 'public', d: 'شرح', when: 'به‌زودی', price: 1200000 },
    { id: 'ev-past', t: 'کارگاه برگزارشده', kind: 'کارگاه', privacy: 'public', past: true, when: 'شنبه ۵ مهر', on: '۱۴۰۵/۰۷/۰۵',
      place: 'سالن اصلی', price: 300000, media: [{ id: 'm1', k: 'audio', t: 'صوت جلسه', src: 'https://cdn.example/a.mp3' }] },
    { id: 'ev-draft', t: 'پیش‌نویس', kind: 'کارگاه', privacy: 'public', status: 'draft', on: '۱۴۰۵/۰۷/۱۱' },
    { id: 'ev-private', t: 'خصوصی', kind: 'کارگاه', privacy: 'private', on: '۱۴۰۵/۰۷/۱۲' },
    { id: 'ev-aban', t: 'اردوی آبان', kind: 'اردو', privacy: 'public', when: 'آبان', on: '۱۴۰۵/۰۸/۰۳', place: 'طبیعت', price: 900000 }
  ],
  people: [], articles: [], partners: [], banners: [], library: [], cooperation: []
};

async function load(query = '', { events = content.events, fixtureMode = false, file = 'events.html', siteContentStatus = 200 } = {}) {
  const errors = [], network = [];
  const url = pathToFileURL(DIR + file).href + query;
  const dom = await JSDOM.fromFile(DIR + file, {
    url, runScripts: 'dangerously', pretendToBeVisual: true, resources: localOnly,
    beforeParse(w) {
      w.scrollTo = () => {};
      if (w.Element && !w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView = () => {};
      if (!w.matchMedia) w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      w.__NORA_TEST_FIXTURE_MODE__ = fixtureMode;
      w.fetch = async path => {
        network.push(String(path));
        if (String(path) === '/api/public/site-content') return { ok: siteContentStatus === 200, status: siteContentStatus, json: async () => ({ content: { ...content, events } }) };
        throw new Error('network disabled: ' + path);
      };
      w.addEventListener('error', e => errors.push('error: ' + (e.message || '')));
      w.console.error = (...args) => errors.push('console.error: ' + args.join(' '));
    }
  });
  const { window } = dom;
  if (window.document.readyState !== 'complete') await new Promise(resolve => {
    const timer = setTimeout(resolve, 5000);
    window.addEventListener('load', () => { clearTimeout(timer); resolve(); }, { once: true });
  });
  if (window.NORA_PUBLIC_READY) await window.NORA_PUBLIC_READY;
  await wait(40);
  const doc = window.document;
  return {
    window, doc, errors, network,
    all: selector => [...doc.querySelectorAll(selector)],
    ids: () => [...doc.querySelectorAll('#eventsList [data-event-id]')].map(el => el.dataset.eventId),
    click: selector => { const el = doc.querySelector(selector); if (!el) throw new Error('نیست: ' + selector);
      el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })); },
    txt: selector => { const el = doc.querySelector(selector); return el ? el.textContent.replace(/\s+/g, ' ').trim() : ''; }
  };
}

let passed = 0, failed = 0;
function ok(condition, label) {
  if (condition) { passed++; console.log('   ✓ ' + label); }
  else { failed++; console.log('   ✗ ' + label); }
}

/* ۱) فهرست از سرور، بدون فیکسچر؛ پیش‌نویس/خصوصی حذف؛ ترتیب «نزدیک‌ترین» */
{
  const p = await load();
  ok(p.errors.length === 0, 'بدون خطای کنسول: ' + p.errors.join(' | '));
  ok(p.network.includes('/api/public/site-content'), 'داده از /api/public/site-content خوانده شد');
  ok(p.window.NORA_PUBLIC_SOURCE === 'server' && !p.window.NORA.EVENTS?.length === false || p.window.NORA_PUBLIC_SOURCE === 'server',
    'منبع داده سرور است');
  const ids = p.ids();
  ok(!ids.includes('ev-draft') && !ids.includes('ev-private'), 'پیش‌نویس و خصوصی در فهرست عمومی نیستند');
  ok(JSON.stringify(ids) === JSON.stringify(['ev-soon', 'ev-late', 'ev-aban', 'ev-undated', 'ev-past']),
    'ترتیب نزدیک‌ترین: پیش‌روها صعودی به تاریخ، بی‌تاریخ در انتها، سپس برگزارشده‌ها: ' + ids.join(','));
  ok(p.txt('#eventsCount').startsWith('۵ رویداد'), 'شمار نتیجه از رکوردهای واقعی: ' + p.txt('#eventsCount'));
  ok(!p.doc.querySelector('#eventToolbar').hidden, 'نوار ابزار با وجود رکورد نمایان است');
  const kinds = p.all('[data-event-kind]').map(el => el.dataset.eventKind);
  ok(JSON.stringify(kinds) === JSON.stringify(['کارگاه', 'اردو', 'پویش', 'نشست']), 'چیپ‌های نوع از رکوردها و مرتب به شمار: ' + kinds.join(','));
  ok(p.txt('[data-event-kind="کارگاه"]').includes('۲'), 'شمار چیپ نوع واقعی است');
  const modes = p.all('[data-event-mode]').map(el => el.dataset.eventMode);
  ok(modes.includes('حضوری') && modes.includes('آنلاین'), 'شیوهٔ برگزاری از mode یا مکان استخراج شد: ' + modes.join(','));
  ok(p.all('.event-list-card .cover-state').length === 1, 'نشان «برگزارشده» فقط روی رویداد گذشته');
  ok(p.txt('[data-event-id="ev-past"] .event-list-meta').includes('۱ رسانهٔ منتشرشده'), 'شمار رسانهٔ آرشیو از رکورد سرور');
  ok(p.doc.querySelector('[data-event-id="ev-late"] a[href="form.html?fid=f-late&kind=reg"]') !== null, 'دکمهٔ ثبت‌نام به فرم منتشرشده');
  ok(p.txt('[data-event-id="ev-soon"] .event-list-actions').includes('فرم ثبت‌نام منتشر نشده'), 'بدون فرم: پیام صادقانه، نه دکمهٔ مرده');
  p.window.close();
}

/* ۲) صافی نوع و شیوه، برداشتن با کلیک دوباره، ترکیب با وضعیت */
{
  const p = await load();
  p.click('[data-event-kind="کارگاه"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon', 'ev-past']), 'صافی نوع «کارگاه»: ' + p.ids().join(','));
  ok(p.txt('#eventsCount').includes('کارگاه'), 'شمار نتیجه صافی را می‌گوید');
  ok(!p.doc.querySelector('#eventFacetReset').hidden, 'دکمهٔ برداشتن صافی‌ها پیدا شد');
  p.click('[data-event-filter="upcoming"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon']), 'ترکیب نوع + پیش‌رو: ' + p.ids().join(','));
  p.click('[data-event-kind="کارگاه"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon', 'ev-late', 'ev-aban', 'ev-undated']), 'کلیک دوباره صافی را برمی‌دارد');
  p.click('[data-event-mode="آنلاین"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-late']), 'صافی شیوهٔ آنلاین (مکان = پیوند): ' + p.ids().join(','));
  p.click('#eventFacetReset');
  ok(p.ids().length === 4 && p.doc.querySelector('#eventFacetReset').hidden, 'برداشتن همهٔ صافی‌ها');
  p.window.close();
}

/* ۳) مرتب‌سازی */
{
  const p = await load();
  const sort = p.doc.querySelector('#eventSort');
  sort.value = 'cheap'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  ok(p.ids()[0] === 'ev-soon' && p.ids()[p.ids().length - 1] === 'ev-undated', 'ارزان‌ترین: رایگان اول، گران‌ترین آخر: ' + p.ids().join(','));
  sort.value = 'dear'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  ok(p.ids()[0] === 'ev-undated', 'گران‌ترین اول');
  sort.value = 'title'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  const titles = p.all('#eventsList .event-list-title').map(el => el.textContent);
  ok(JSON.stringify(titles) === JSON.stringify(titles.slice().sort((a, b) => a.localeCompare(b, 'fa'))), 'ترتیب نام فارسی');
  p.window.close();
}

/* ۴) نمای تقویم از تاریخ ماشین‌خوان (on)، با ارقام فارسی و لاتین؛ بی‌تاریخ فقط در فهرست */
{
  const p = await load('#cal');
  ok(p.window.NORA_EVENTS_PAGE.state.view === 'cal', 'هش #cal نمای تقویم را باز می‌کند');
  ok(!p.doc.querySelector('#eventCalendar').hidden && p.doc.querySelector('#eventsList').hidden, 'تقویم نمایان، فهرست پنهان');
  const months = p.all('[data-event-month]').map(el => el.dataset.eventMonth);
  ok(JSON.stringify(months) === JSON.stringify(['1405-7', '1405-8']), 'ماه‌ها فقط از تاریخ‌های واقعی: ' + months.join(','));
  /* ماه آغازین تقویم به تاریخ امروز دستگاه وابسته است (ماه جاری یا نخستین ماه آینده)؛ آزمون نباید به تاریخ اجرا وابسته باشد → مهر را صریح انتخاب می‌کنیم */
  p.click('[data-event-month="1405-7"]');
  ok(p.doc.querySelector('[data-event-month="1405-7"]').classList.contains('on'), 'انتخاب صریح ماه مهر');
  ok(p.txt('[data-event-month="1405-7"]').includes('مهر') && p.txt('[data-event-month="1405-7"]').includes('۳'), 'برچسب ماه و شمار (۳ برنامه در مهر)');
  const hasDays = p.all('.event-cal-cell.has').map(el => el.dataset.eventDay);
  ok(JSON.stringify(hasDays) === JSON.stringify(['5', '10', '20']), 'روزهای دارای برنامه در مهر: ' + hasDays.join(','));
  ok(p.all('.event-cal-cell:not(.blank)').length === 30, 'مهر ۳۰ روز دارد');
  ok(p.all('.event-cal-wd').length === 7 && p.txt('.event-cal-wd') === 'ش', 'هفته از شنبه آغاز می‌شود');
  const blanks = p.all('.event-cal-cell.blank').length;
  ok(blanks === 4, '۱ مهر ۱۴۰۵ چهارشنبه است (۴ خانهٔ خالی پیش از آن)، یافت: ' + blanks);
  ok(p.doc.querySelector('.event-cal-cell[data-event-day="5"]').classList.contains('was'), 'روز با برنامهٔ فقط‌برگزارشده نشان was دارد');
  ok(p.txt('#eventCalendarNote').includes('۱ رویداد بدون تاریخ'), 'یادداشت رویداد بی‌تاریخ: ' + p.txt('#eventCalendarNote'));
  p.click('.event-cal-cell[data-event-day="20"]');
  ok(p.txt('#eventDayTitle') === 'دوشنبه ۲۰ مهر ۱۴۰۵', 'عنوان روز با نام روز هفتهٔ درست: ' + p.txt('#eventDayTitle'));
  ok(p.all('#eventDayList [data-event-id]').map(el => el.dataset.eventId).join() === 'ev-late', 'کارت همان روز');
  p.click('[data-event-month="1405-8"]');
  ok(p.all('.event-cal-cell:not(.blank)').length === 30 && p.all('.event-cal-cell.has').length === 1, 'آبان: ۳۰ روز، یک برنامه');
  ok(p.txt('#eventDayTitle').includes('آبان'), 'روز نخستِ دارای برنامه در ماه تازه انتخاب شد');
  p.click('[data-event-view="list"]');
  ok(!p.doc.querySelector('#eventsList').hidden && p.doc.querySelector('#eventCalendar').hidden && p.window.NORA_EVENTS_PAGE.state.view === 'list',
    'بازگشت به فهرست (replaceState روی file:// در jsdom مجاز نیست و بی‌صدا نادیده گرفته می‌شود)');
  p.window.close();
}

/* ۵) هش‌های قدیمی پیوندها: #upcoming و #lib خطا نمی‌دهند و وضعیت درست می‌گیرند */
{
  const up = await load('#upcoming');
  ok(up.errors.length === 0 && !up.ids().includes('ev-past'), '#upcoming فقط پیش‌روها');
  up.window.close();
  const lib = await load('#lib');
  ok(lib.errors.length === 0 && JSON.stringify(lib.ids()) === JSON.stringify(['ev-past']), '#lib (کتابخانه) = آرشیو برگزارشده‌ها');
  lib.window.close();
  const q = await load('?status=past&kind=کارگاه');
  ok(JSON.stringify(q.ids()) === JSON.stringify(['ev-past']) && q.window.NORA_EVENTS_PAGE.state.kind === 'کارگاه', 'پارامترهای status و kind از نشانی');
  const bad = await load('?kind=ناموجود');
  ok(bad.window.NORA_EVENTS_PAGE.state.kind === '', 'kind ناشناخته نادیده گرفته می‌شود');
  q.window.close(); bad.window.close();
}

/* ۶) تولید بدون رویداد: هیچ دادهٔ نمایشی، پیام صادقانه، تقویم خالی بی‌خطا */
{
  const p = await load('#cal', { events: [] });
  ok(p.errors.length === 0, 'بدون خطا با فهرست خالی');
  ok(p.ids().length === 0 && p.doc.querySelector('#eventToolbar').hidden, 'بدون رکورد: نه کارت، نه نوار ابزار');
  ok(p.txt('#eventCalendarNote') === 'هنوز رویدادی منتشر نشده است.', 'یادداشت تقویم خالی');
  p.click('[data-event-view="list"]');
  ok(!p.doc.querySelector('#eventsEmpty').hidden && p.txt('#eventsEmptyMessage').includes('منتشر نشده'), 'حالت خالی فهرست');
  ok(!(p.window.NORA && Array.isArray(p.window.NORA.EVENTS) && p.window.NORA.EVENTS.length), 'data.js نمونه بارگذاری نشده است');
  p.window.close();
}

/* ۷) تجزیهٔ تاریخ و شیوه، مستقیم */
{
  const p = await load();
  const { parseJalali, modeOf } = p.window.NORA_EVENTS_PAGE;
  ok(JSON.stringify(parseJalali('۱۴۰۳/۱۲/۳۰')) === JSON.stringify({ jy: 1403, jm: 12, jd: 30 }), '۱۴۰۳ کبیسه است: ۳۰ اسفند معتبر');
  ok(parseJalali('1404/12/30') === null, '۱۴۰۴ کبیسه نیست: ۳۰ اسفند نامعتبر');
  ok(parseJalali('جمعه ۱۰ مهر') === null && parseJalali('') === null, 'متن آزاد تاریخ ماشینی نیست');
  ok(JSON.stringify(parseJalali('1405-07-10 16:00')) === JSON.stringify({ jy: 1405, jm: 7, jd: 10 }), 'جداکنندهٔ خط تیره و دنبالهٔ ساعت');
  ok(modeOf({ place: 'https://x.example' }) === 'آنلاین' && modeOf({ place: 'سالن' }) === 'حضوری'
    && modeOf({ mode: 'حضوری و آنلاین' }) === 'حضوری و آنلاین' && modeOf({}) === '', 'استخراج شیوهٔ برگزاری');
  p.window.close();
}

/* ۸) صفحهٔ رویداد: «برنامه‌های دیگر» از همان عکس سرور، هم‌وضعیت، اول هم‌نوع، بدون خود رویداد */
{
  const p = await load('?id=ev-soon', { file: 'event.html' });
  ok(p.errors.length === 0, 'صفحهٔ رویداد بدون خطا');
  const related = p.all('[data-related-event]').map(el => el.dataset.relatedEvent);
  ok(JSON.stringify(related) === JSON.stringify(['ev-late', 'ev-undated', 'ev-aban']),
    'پیش‌رو: فقط پیش‌روهای دیگر (ev-past حذف)، بدون خود رویداد: ' + related.join(','));
  ok(p.doc.querySelector('.event-related .back-link')?.getAttribute('href') === 'events.html?status=upcoming', 'پیوند «همهٔ برنامه‌های پیش‌رو»');
  p.window.close();
  const past = await load('?id=ev-past', { file: 'event.html' });
  ok(past.all('[data-related-event]').length === 0 && past.doc.querySelector('.event-related') === null,
    'برگزارشدهٔ تنها: بخش «برنامه‌های دیگر» اصلاً ساخته نمی‌شود (نه فهرست خالی)');
  past.window.close();
  const kindFirst = await load('?id=ev-aban', { file: 'event.html', events: content.events.concat([
    { id: 'ev-aban-2', t: 'اردوی دوم', kind: 'اردو', privacy: 'public', when: 'آذر', on: '۱۴۰۵/۰۹/۰۱' }]) });
  ok(kindFirst.all('[data-related-event]')[0]?.dataset.relatedEvent === 'ev-aban-2', 'هم‌نوع‌ها اول می‌آیند');
  kindFirst.window.close();
}

/* ۹) نسخهٔ فایل‌ها در صفحه */
{
  const html = fs.readFileSync(DIR + 'events.html', 'utf8');
  ok(html.includes('events-page.js?v=105') && html.includes('events-page.css?v=105'), 'نسخهٔ اسکریپت/استایل صفحه جلو رفته است');
  ok(/__NORA_TEST_FIXTURE_MODE__===true\)document\.write/.test(html), 'data.js فقط در حالت آزمون صریح');
  const detail = fs.readFileSync(DIR + 'event.html', 'utf8');
  ok(detail.includes('event-page.js?v=105') && detail.includes('event-interaction.js?v=8') && detail.includes('event-interaction.css?v=5'), 'نسخهٔ اسکریپت صفحهٔ رویداد جلو رفته و ماژول تعامل بارگذاری می‌شود');
}

/* ۱۱) خطای API (مثلاً ۵۰۳): صفحهٔ رویدادها «منتشر نشده» نمی‌گوید؛ نبودِ دسترسی به سرور را روشن می‌گوید */
{
  const p = await load('', { events: [] , siteContentStatus: 503 });
  ok(p.window.NORA_PUBLIC_SOURCE === 'unavailable', 'منبع محتوای عمومی در خطای سرور unavailable است');
  ok(/دسترسی نیست/.test(p.txt('#eventsEmptyMessage')) && !/منتشر نشده/.test(p.txt('#eventsEmptyMessage')), 'پیام خالی‌بودن فهرست، خطای سرور را با «رویدادی منتشر نشده» اشتباه نمی‌گیرد');
  ok(p.errors.length === 0, 'بدون خطای JavaScript');
  p.window.close();
}

/* ۱۰) کلید شب/روز در صفحه‌هایی که initUI را صدا نمی‌زنند هم واقعاً کار می‌کند (ui.js آن را یک‌جا وصل می‌کند) */
for (const file of ['events.html', 'event.html']) {
  const p = await load(file === 'event.html' ? '?id=ev-1' : '', { file });
  const root = p.doc.documentElement;
  const now = () => (root.dataset.theme === 'dark' ? 'dark' : 'light');
  const t0 = now();
  p.click('[data-theme-toggle]');
  const t1 = now();
  p.click('[data-theme-toggle]');
  ok(t1 !== t0 && now() === t0, file + ': هر کلیک روی کلید شب/روز دقیقاً یک بار تم را عوض می‌کند');
  ok(p.doc.querySelector('[data-theme-toggle]').getAttribute('aria-checked') === (t0 === 'dark' ? 'true' : 'false'), file + ': وضعیت aria-checked کلید با تم هم‌گام است');
  p.window.close();
}

/* ۱۲) فاز ۷: وضعیت ثبت‌نام از سرور روی کارت؛ دکمهٔ ثبت‌نام فقط در حالت «باز»؛ پایان‌یافتهٔ سرور = برگزارشده؛ لغوشده هرگز فعال نیست */
{
  const soon = new Date(Date.now() + 3 * 86_400_000).toISOString();
  const start = new Date(Date.now() + 10 * 86_400_000).toISOString();
  const events = [
    { id: 'ev-open', t: 'کارگاه باز', kind: 'کارگاه', privacy: 'public', d: 'شرح', when: 'آبان', on: '۱۴۰۵/۰۸/۰۳', forms: [{ id: 'f-open', need: 'reg', n: 'ثبت‌نام' }], posterUp: '/api/public/media/poster-a4.png',
      startsAt: start, regClosesAt: soon, registration: { state: 'open', reason: '', lifecycle: 'scheduled', closesAt: soon, countdownTo: soon, startsAt: start, startsIn: start } },
    { id: 'ev-closed', t: 'کارگاه بسته', kind: 'کارگاه', privacy: 'public', d: 'شرح', when: 'آبان', on: '۱۴۰۵/۰۸/۰۴', forms: [{ id: 'f-closed', need: 'reg', n: 'ثبت‌نام' }],
      registration: { state: 'closed', reason: 'time', lifecycle: 'scheduled', countdownTo: '' } },
    { id: 'ev-cancel', t: 'نشست لغوشده', kind: 'نشست', privacy: 'public', d: 'شرح', when: 'آبان', on: '۱۴۰۵/۰۸/۰۵', forms: [{ id: 'f-cancel', need: 'reg', n: 'ثبت‌نام' }],
      lifecycle: 'cancelled', registration: { state: 'cancelled', reason: 'cancelled', lifecycle: 'cancelled', countdownTo: '' } },
    { id: 'ev-ended', t: 'کارگاه تمام‌شده', kind: 'کارگاه', privacy: 'public', d: 'شرح', when: 'مهر', on: '۱۴۰۵/۰۷/۰۱', forms: [{ id: 'f-ended', need: 'reg', n: 'ثبت‌نام' }],
      registration: { state: 'ended', reason: 'time', lifecycle: 'scheduled', countdownTo: '' } }
  ];
  const p = await load('', { events });
  const cardOf = id => p.doc.querySelector(`#eventsList [data-event-id="${id}"]`);
  const openCard = cardOf('ev-open');
  /* پوستر A4 عمودی: کارت با پوستر کلاس has-poster می‌گیرد (قاب contain، متن زیر قاب)؛ کارت بی‌پوستر نه */
  ok(!!openCard.querySelector('.event-list-cover.has-poster img[src="/api/public/media/poster-a4.png"]') && !cardOf('ev-closed').querySelector('.event-list-cover.has-poster'),
    'کارت با پوستر has-poster دارد و کارت بدون پوستر ندارد');
  {
    const css = fs.readFileSync(DIR + 'events-page.css', 'utf8');
    ok(/\.event-list-cover\.has-poster img\{[^}]*object-fit:contain/.test(css) && /\.event-list-cover\.has-poster \.cover-shade\{display:none\}/.test(css)
      && /\.event-list-cover\.has-poster \.cover-kind,[^{]*\{position:static/.test(css),
      'استایل پوستر: contain بدون برش، بدون سایهٔ روی تصویر، برچسب‌ها ایستا زیر قاب');
    const detail = fs.readFileSync(DIR + 'event.html', 'utf8');
    ok(/\.event-cover-image\{[^}]*object-fit:contain/.test(detail), 'صفحهٔ رویداد: پوستر سربرگ contain است، نه cover');
    const nora = fs.readFileSync(DIR + 'nora.css', 'utf8');
    ok(/\.evc-cov\.has-poster img\{[^}]*object-fit:contain/.test(nora) && /\.evc-cov\.has-poster \.evc-tags\{position:static/.test(nora), 'کارت خانه: پوستر contain و برچسب‌ها زیر قاب');
  }
  ok(!!openCard.querySelector('.reg-state.live') && /ثبت‌نام باز است/.test(openCard.textContent), 'کارت باز: نشان «ثبت‌نام باز است» از وضعیت سرور');
  ok(/تا پایان ثبت‌نام/.test(openCard.textContent) && !!openCard.querySelector('[data-countdown]'), 'کارت باز: شمارشگر مشترک تا مهلت ثبت‌نام');
  ok(openCard.querySelector('a.btn.primary')?.getAttribute('href') === 'form.html?fid=f-open&kind=reg', 'کارت باز: دکمهٔ ثبت‌نام به همان فرم موجود می‌رود');
  const closedCard = cardOf('ev-closed');
  ok(!closedCard.querySelector('a[href^="form.html"]') && /ثبت‌نام بسته شد/.test(closedCard.textContent), 'کارت بسته: بدون دکمهٔ فرم، با وضعیت صادقانه');
  const cancelCard = cardOf('ev-cancel');
  ok(!cancelCard.querySelector('a[href^="form.html"]') && /لغو شد/.test(cancelCard.querySelector('.cover-state')?.textContent || '') && !cancelCard.querySelector('[data-countdown]'), 'کارت لغوشده: نشان لغو، بدون فرم و بدون شمارشگر');
  ok(!!cardOf('ev-ended') && /برگزارشده/.test(cardOf('ev-ended').querySelector('.cover-state')?.textContent || '') && !cardOf('ev-ended').querySelector('a[href^="form.html"]') && !cardOf('ev-ended').querySelector('[data-countdown]'), 'پایان‌یافته طبق ساعت سرور «برگزارشده» است: بدون فرم و شمارشگر');
  p.click('[data-event-filter="upcoming"]');
  await wait(20);
  ok(!cardOf('ev-ended') && !!cardOf('ev-open'), 'پایان‌یافته طبق سرور در صافی «پیش‌رو» نیست');
  ok(p.errors.length === 0, 'بدون خطای کنسول: ' + p.errors.join(' | '));
  p.window.close();
}

/* ۱۳) فاز ۷: صفحهٔ رویداد؛ وضعیت/شمارشگر/زمان‌ها از سرور، CTA فقط در حالت باز، تقویم فقط با زمان معتبر، اشتراک، پایان مهلت */
{
  const soon = new Date(Date.now() + 90_000).toISOString();           /* ۹۰ ثانیه تا مهلت */
  const start = '2026-11-03T06:30:00Z';                                /* ۱۴۰۵/۰۸/۱۲ ۱۰:۰۰ تهران */
  const base = { kind: 'کارگاه', privacy: 'public', d: 'شرح', when: '۱۲ آبان', on: '۱۴۰۵/۰۸/۱۲', place: 'سالن اصلی', conditions: 'ویژهٔ نوجوانان', forms: [{ id: 'f-x', need: 'reg', n: 'ثبت‌نام' }] };
  const events = [
    { ...base, id: 'd-open', t: 'کارگاه باز', startsAt: start, regClosesAt: soon, registration: { state: 'open', reason: '', lifecycle: 'scheduled', closesAt: soon, countdownTo: soon, startsAt: start, startsIn: start } },
    { ...base, id: 'd-wait', t: 'کارگاه آینده', startsAt: start, registration: { state: 'not_started', reason: 'time', lifecycle: 'scheduled', opensAt: start, countdownTo: start, startsAt: start, startsIn: start } },
    { ...base, id: 'd-full', t: 'کارگاه پر', startsAt: start, registration: { state: 'full', reason: 'capacity', lifecycle: 'scheduled', countdownTo: '', startsAt: start, startsIn: start } },
    { ...base, id: 'd-cancel', t: 'کارگاه لغو', lifecycle: 'cancelled', startsAt: start, registration: { state: 'cancelled', reason: 'cancelled', lifecycle: 'cancelled', countdownTo: '' } },
    { ...base, id: 'd-nodate', t: 'کارگاه بی‌زمان', registration: { state: 'open', reason: '', lifecycle: 'scheduled', countdownTo: '' } }
  ];
  const openPage = await load('?id=d-open', { file: 'event.html', events });
  ok(openPage.errors.length === 0, 'صفحهٔ رویداد باز بدون خطا: ' + openPage.errors.join(' | '));
  ok(openPage.doc.querySelector('.event-register .reg-state.live')?.textContent === 'ثبت‌نام باز است', 'وضعیت «ثبت‌نام باز است» از سرور');
  ok(/تا پایان ثبت‌نام/.test(openPage.txt('[data-reg-timer]')) && openPage.doc.querySelector('[data-reg-timer] [data-countdown]'), 'شمارشگر مشترک تا مهلت');
  ok(openPage.doc.querySelector('#reg')?.getAttribute('href') === 'form.html?fid=f-x&kind=reg' && openPage.doc.querySelector('#ctabar').hidden === false, 'CTA ثبت‌نام به فرم موجود و نوار پایین فعال');
  ok(/۱۲ آبان ۱۴۰۵، ۱۰:۰۰/.test(openPage.txt('.detail-grid')), 'شروع به وقت تهران و تقویم شمسی از startsAt سرور (۱۴۰۵/۰۸/۱۲ ۱۰:۰۰)');
  ok(/ویژهٔ نوجوانان/.test(openPage.txt('.event-conditions')), 'شرایط شرکت نمایش داده می‌شود');
  ok(openPage.doc.querySelector('#addToCalendar') && openPage.doc.querySelector('#shareEvent'), 'دکمه‌های افزودن به تقویم و اشتراک‌گذاری');
  let shared = null; openPage.window.navigator.share = async payload => { shared = payload; };
  openPage.click('#shareEvent'); await wait(10);
  ok(shared && shared.title === 'کارگاه باز' && /event\.html\?id=d-open$/.test(shared.url) && !/نمونه/.test(shared.text), 'اشتراک با عنوان و نشانی واقعی رویداد');
  const timer = openPage.doc.querySelector('[data-reg-timer] [data-countdown]');
  timer.dataset.countdown = new Date(Date.now() - 1000).toISOString();           /* شبیه‌سازی رسیدن مهلت */
  await wait(1100);
  ok(!openPage.doc.querySelector('#reg') && /نوسازی/.test(openPage.txt('[data-reg-action]')) && openPage.doc.querySelector('#ctabar').hidden === true,
    'پس از پایان مهلت: دکمهٔ ثبت‌نام برداشته می‌شود و وضعیت قطعی به عکس تازهٔ سرور واگذار می‌شود');
  openPage.window.close();
  const waitPage = await load('?id=d-wait', { file: 'event.html', events });
  ok(!waitPage.doc.querySelector('#reg') && waitPage.doc.querySelector('.event-register .reg-state.wait') && /تا آغاز ثبت‌نام/.test(waitPage.txt('[data-reg-timer]')) && waitPage.doc.querySelector('#ctabar').hidden,
    'ثبت‌نام آغازنشده: بدون دکمهٔ فرم، شمارش تا آغاز ثبت‌نام');
  waitPage.window.close();
  const fullPage = await load('?id=d-full', { file: 'event.html', events });
  ok(!fullPage.doc.querySelector('#reg') && /ظرفیت تکمیل شد/.test(fullPage.txt('.event-register')) && !fullPage.doc.querySelector('#ctabar:not([hidden])'),
    'ظرفیت تکمیل: بدون دکمهٔ فرم، وضعیت صادقانه');
  fullPage.window.close();
  const cancelPage = await load('?id=d-cancel', { file: 'event.html', events });
  ok(!cancelPage.doc.querySelector('#reg') && /لغو شد/.test(cancelPage.txt('.event-heading')) && !cancelPage.doc.querySelector('[data-countdown]') && !cancelPage.doc.querySelector('#addToCalendar'),
    'لغوشده: نشان لغو، بدون فرم/شمارشگر/تقویم');
  cancelPage.window.close();
  const noDate = await load('?id=d-nodate', { file: 'event.html', events });
  ok(noDate.doc.querySelector('#reg') && !noDate.doc.querySelector('[data-countdown]') && !noDate.doc.querySelector('#addToCalendar'),
    'بدون زمان معتبر: ثبت‌نام باز ولی هیچ شمارشگر یا فایل تقویم ساختگی ساخته نمی‌شود');
  noDate.window.close();
}

console.log(`\nevents-page: ${passed} قبول، ${failed} خطا`);
process.exit(failed ? 1 : 0);
